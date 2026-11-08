"""The sending engine.

Each workspace sends one campaign at a time (like a person working through a list). A WhatsApp account
is used by only one running campaign at a time, even when it is shared with another workspace: the
campaign that started first keeps it, and others use their free accounts or wait. Every account also
keeps a gap since its last message, whichever campaign sent it, so a phone is never hit twice in a row
when one campaign hands it over to the next. All progress lives in the database, which means a crash or restart
resumes where it stopped instead of losing the send. Celery (tasks.py) and the no-Docker
`manage.py run_worker` loop both drive the same two functions: claim_next() and run_campaign().
"""
import logging
import random
import re
import time
from datetime import timedelta

from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.models import AppSettings, Rotation
from apps.whatsapp.models import WhatsAppAccount
from apps.whatsapp.providers import Media, ProviderError, get_provider

from .limits import limit_for, sent_today
from .models import Campaign, CampaignTarget

log = logging.getLogger(__name__)

BUSY = "busy"  # pick_sender: every usable account is busy in another running campaign; wait, don't fail
BUSY_RECHECK = 5  # seconds between checks while waiting for a busy account
STALE_AFTER = timedelta(minutes=5)  # a running campaign without a heartbeat this long is orphaned
HEARTBEAT_EVERY = 10  # seconds
POLL_EVERY = 1  # seconds, how fast pause/cancel is noticed while waiting
S = Campaign.Status
T = CampaignTarget.Status


def recover_stale(force: bool = False) -> int:
    """Put campaigns whose worker died back in the queue. Returns how many.

    force=True re-queues every running campaign; call it only when this is the sole worker and it
    has just started (so nothing can genuinely be running).
    """
    running = Campaign.objects.filter(status=S.RUNNING)
    if not force:
        running = running.filter(heartbeat_at__lt=timezone.now() - STALE_AFTER)
    n = 0
    for c in running:
        with transaction.atomic():
            # A target caught mid-send may or may not have arrived; don't risk a duplicate.
            c.targets.filter(status=T.SENDING).update(
                status=T.FAILED, error="Interrupted while sending; it may or may not have arrived.", finished_at=timezone.now()
            )
            n += Campaign.objects.filter(pk=c.pk, status=S.RUNNING).update(
                status=S.SCHEDULED, note="Resumed after an interruption", next_action_at=None
            )
    if n:
        log.warning("re-queued %s interrupted campaign(s)", n)
    return n


def claim_next() -> Campaign | None:
    """Atomically move the next due campaign to RUNNING. None if nothing is due.
    A campaign waits while its workspace already has one running, or while every one of its sender
    accounts (possibly shared) is busy in another running campaign. Waiting campaigns get a note saying why."""
    if not cache.add("broadcasts:claim-lock", 1, timeout=30):
        return None
    try:
        recover_stale()
        now = timezone.now()
        running = Campaign.objects.filter(status=S.RUNNING)
        busy_owners = set(running.values_list("owner_id", flat=True))
        busy = set(WhatsAppAccount.objects.filter(sender_campaigns__in=running).values_list("pk", flat=True))
        due = (Campaign.objects.filter(status=S.SCHEDULED, scheduled_at__lte=now)
               .prefetch_related("sender_accounts").order_by("scheduled_at", "id")[:50])
        for c in due:
            if c.owner_id in busy_owners:
                _note_waiting(c, "Waiting for your other send to finish")
                continue
            senders = list(c.sender_accounts.all())
            if senders and all(a.pk in busy for a in senders):
                _note_waiting(c, f"Waiting: {_names(senders)} {'is' if len(senders) == 1 else 'are'} busy with another send")
                continue
            if Campaign.objects.filter(pk=c.pk, status=S.SCHEDULED).update(status=S.RUNNING, heartbeat_at=now, claimed_at=now, note=""):
                return Campaign.objects.get(pk=c.pk)
        return None
    finally:
        cache.delete("broadcasts:claim-lock")


def _names(accounts) -> str:
    return ", ".join(a.label or f"+{a.phone}" for a in accounts)


def _note_waiting(campaign, note):
    if campaign.note != note:
        Campaign.objects.filter(pk=campaign.pk, status=S.SCHEDULED).update(note=note[:200])


def busy_accounts(campaign) -> set[int]:
    """Accounts held by another running campaign that started before this one."""
    mine = (campaign.claimed_at or timezone.now(), campaign.pk)
    earlier = [c.pk for c in Campaign.objects.filter(status=S.RUNNING).exclude(pk=campaign.pk).only("pk", "claimed_at")
               if ((c.claimed_at or timezone.now()), c.pk) < mine]
    if not earlier:
        return set()
    return set(WhatsAppAccount.objects.filter(sender_campaigns__in=earlier).values_list("pk", flat=True))


def _status(campaign_id) -> str:
    return Campaign.objects.filter(pk=campaign_id).values_list("status", flat=True).first()


def _wait(campaign: Campaign, seconds: float, note: str) -> bool:
    """Sleep, waking early on pause/cancel. Returns True if the campaign is still running."""
    end = time.monotonic() + seconds
    Campaign.objects.filter(pk=campaign.pk).update(
        next_action_at=timezone.now() + timedelta(seconds=seconds), note=note, heartbeat_at=timezone.now()
    )
    last_beat = time.monotonic()
    still_running = True
    while time.monotonic() < end:
        time.sleep(min(POLL_EVERY, max(0, end - time.monotonic())))
        if _status(campaign.pk) != S.RUNNING:
            still_running = False
            break
        if time.monotonic() - last_beat >= HEARTBEAT_EVERY:
            Campaign.objects.filter(pk=campaign.pk).update(heartbeat_at=timezone.now())
            last_beat = time.monotonic()
    Campaign.objects.filter(pk=campaign.pk).update(next_action_at=None, note="")
    return still_running


def _finish(target: CampaignTarget, status: str, error: str = ""):
    now = timezone.now()
    target.status, target.error, target.finished_at = status, error[:300], now
    if status == T.SENT:
        target.sent_at = now
    target.save(update_fields=["status", "error", "finished_at", "sent_at"])


def _load_media(campaign: Campaign) -> Media | None:
    if not campaign.media_id:
        return None
    m = campaign.media
    with m.file.open("rb") as fh:
        return Media(data=fh.read(), mimetype=m.mime_type, filename=m.original_name)


# {key} or {key|fallback}. Any key text is matched (Bangla included); only known keys are replaced.
TAG = re.compile(r"\{([^\s{}|]{1,40})(?:\|([^}]*))?\}")


def personalize(message: str, name: str, fields: dict | None = None, known=(), phone: str = "") -> str:
    """Fill placeholders for one recipient.

    {name} is their name and {phone} their number; {score} etc. come from the columns imported with the
    contact (fields). "|fallback" is used when the value is empty. Braces that aren't a known placeholder
    (not built in, not one of the workspace's fields in known) are left as they are.
    """
    fields = fields or {}

    def fill(m):
        key, fallback = m.group(1).lower(), (m.group(2) or "").strip()
        if key == "name":
            value = name
        elif key == "phone":
            value = f"+{phone}" if phone else ""
        elif key in fields or key in known:
            value = str(fields.get(key, "") or "")
        else:
            return m.group(0)
        return value or fallback

    return TAG.sub(fill, message or "")


def _resolve_contact(provider, account, target: CampaignTarget) -> tuple[str | None, str | None, str]:
    """(chat id to send to, None, "") or (None, status, reason) if this number must not be sent to.

    Uses the stored validation result when it is fresh; otherwise asks WhatsApp now and stores the answer.
    """
    from apps.contacts.validation import is_fresh, record_results

    phone = target.recipient_jid.split("@")[0]
    contact = target.contact
    if contact is not None:
        contact.refresh_from_db(fields=["opted_out", "on_whatsapp", "wa_jid", "checked_at"])
        if contact.opted_out:
            return None, T.SKIPPED, "This contact opted out."
        if is_fresh(contact):
            if contact.on_whatsapp is False:
                return None, T.FAILED, f"+{phone} is not on WhatsApp."
            return contact.wa_jid or target.recipient_jid, None, ""
    resolved = provider.check_number(account.session_id, phone)  # may raise ProviderError
    # Saved on the contact's owner (a shared list's contacts belong to the sharer).
    record_results({phone: resolved}, owner=contact.owner_id if contact is not None else target.campaign.owner_id)
    if not resolved:
        return None, T.FAILED, f"+{phone} is not on WhatsApp."
    return resolved, None, ""


def _usable(account) -> tuple[bool, str, str]:
    """Can this account send right now? (ok, status if not, reason if not)"""
    if account.status != WhatsAppAccount.Status.CONNECTED:
        return False, T.FAILED, f"{account.label} is not connected."
    limit = limit_for(account)
    if limit and sent_today(account.id) >= limit:
        return False, T.SKIPPED, f"Daily limit of {limit} reached for {account.label}."
    return True, "", ""


def pick_sender(campaign: Campaign):
    """Choose the account that sends the next message, following the campaign's rotation.

    Returns (account, "", "") or (None, status, reason) when no account can send it; status BUSY means
    the usable accounts are all held by another running campaign, so the message should wait, not fail.
    Take turns: the current account sends `rotate_every` messages, then the next one takes over.
    Random: any sender. Balanced: the sender with the fewest messages today.
    With failover, an account that is disconnected or at its daily limit is passed over.
    """
    # Only accounts the campaign's workspace still owns or has shared with it (a share can be stopped mid-send).
    senders = list(campaign.sender_accounts.filter(Q(owner=campaign.owner_id) | Q(shares__grantee=campaign.owner_id))
                   .distinct().order_by("id"))
    if not senders:
        return None, T.FAILED, "None of the chosen accounts can be used any more (removed or no longer shared)."

    mode = campaign.rotation_mode
    if mode == Rotation.RANDOM:
        order = random.sample(senders, len(senders))
    elif mode == Rotation.BALANCED:
        order = sorted(senders, key=lambda a: (sent_today(a.id), a.id))
    else:
        ids = [a.id for a in senders]
        cur = ids.index(campaign.rotation_account_id) if campaign.rotation_account_id in ids else 0
        if campaign.rotation_account_id in ids and campaign.rotation_used >= campaign.rotate_every:
            cur = (cur + 1) % len(ids)  # this account's turn is over
        order = senders[cur:] + senders[:cur]
    if not campaign.failover:
        order = order[:1]

    problems, held = [], []
    busy = busy_accounts(campaign)
    for account in order:
        if account.pk in busy:
            held.append(account)  # another campaign started on it first; it may free up
            continue
        ok, status, reason = _usable(account)
        if ok:
            if mode == Rotation.TURNS:
                used = campaign.rotation_used + 1 if account.id == campaign.rotation_account_id else 1
                Campaign.objects.filter(pk=campaign.pk).update(rotation_account=account, rotation_used=used)
                campaign.rotation_account_id, campaign.rotation_used = account.id, used
            return account, "", ""
        problems.append((status, reason))
        if mode == Rotation.TURNS and not campaign.failover:
            Campaign.objects.filter(pk=campaign.pk).update(rotation_account=account, rotation_used=campaign.rotate_every)
            campaign.rotation_account_id, campaign.rotation_used = account.id, campaign.rotate_every
    if held:
        return None, BUSY, f"Waiting: {_names(held)} {'is' if len(held) == 1 else 'are'} busy with another send"
    if len(problems) > 1:
        # Every sender was tried. Skipped (limits) only if none of them simply failed.
        status = T.SKIPPED if all(st == T.SKIPPED for st, _ in problems) else T.FAILED
        return None, status, "No sender account could send: " + " ".join(r for _, r in problems)
    return None, problems[0][0], problems[0][1]


def run_campaign(campaign_id: int) -> str | None:
    """Send every pending target of a RUNNING campaign. Returns the final status."""
    close_old_connections()
    campaign = Campaign.objects.select_related("media").filter(pk=campaign_id).first()
    if not campaign or campaign.status != S.RUNNING:
        return campaign.status if campaign else None

    Campaign.objects.filter(pk=campaign.pk, started_at__isnull=True).update(started_at=timezone.now())
    provider = get_provider()
    typing = campaign.typing_indicator and AppSettings.load(campaign.owner).typing_indicator
    try:
        media = _load_media(campaign)
    except OSError:
        campaign.targets.filter(status=T.PENDING).update(status=T.FAILED, error="The attached file is missing on the server.")
        media = None

    from apps.contacts.models import ContactField

    known = set(ContactField.objects.filter(owner=campaign.owner_id).values_list("key", flat=True))
    sent_in_batch = 0
    while _status(campaign.pk) == S.RUNNING:
        target = campaign.targets.filter(status=T.PENDING).select_related("account", "contact").order_by("position", "id").first()
        if not target:
            break
        # The sender is chosen now, so rotation and failover see each account's live state.
        account, status, reason = pick_sender(campaign)
        if status == BUSY:
            if not _wait(campaign, BUSY_RECHECK, reason):
                break
            continue
        if account is None:
            _finish(target, status, reason)
            continue
        target.account, target.account_label = account, account.label
        target.save(update_fields=["account", "account_label"])

        try:
            to, skip_status, reason = _resolve_contact(provider, account, target)
        except ProviderError as e:
            to, skip_status, reason = None, T.FAILED, str(e)
        if not to:
            _finish(target, skip_status, reason)
            continue

        # Keep this phone's gap since its last message, even if another campaign (or user) sent it.
        account.refresh_from_db(fields=["last_sent_at"])
        if account.last_sent_at:
            left = campaign.delay_min_seconds - (timezone.now() - account.last_sent_at).total_seconds()
            if left > 0.5 and not _wait(campaign, left, f"Keeping a gap on {account.label}: it sent a message moments ago"):
                break

        target.status, target.attempts = T.SENDING, target.attempts + 1
        target.save(update_fields=["status", "attempts"])
        label = (target.recipient_name or target.recipient_jid.split("@")[0])[:150]
        Campaign.objects.filter(pk=campaign.pk).update(heartbeat_at=timezone.now(), note=f"Sending to {label}")
        fields = target.contact.fields if target.contact_id and target.contact else {}
        text = personalize(campaign.message, target.recipient_name, fields, known, target.recipient_jid.split("@")[0])
        try:
            WhatsAppAccount.objects.filter(pk=account.pk).update(last_sent_at=timezone.now())
            provider.send_message(account.session_id, to, text, media=media, typing=typing)
        except ProviderError as e:
            _finish(target, T.FAILED, str(e))
        except Exception as e:  # never let one bad recipient kill the whole send
            log.exception("send to %s failed", to)
            _finish(target, T.FAILED, f"Unexpected error: {e}")
        else:
            _finish(target, T.SENT)
            sent_in_batch += 1

        if not campaign.targets.filter(status=T.PENDING).exists():
            break
        if campaign.batch_size and sent_in_batch >= campaign.batch_size:
            sent_in_batch = 0
            ok = _wait(campaign, campaign.batch_pause_minutes * 60, f"Break after {campaign.batch_size} messages")
        else:
            lo, hi = sorted((campaign.delay_min_seconds, campaign.delay_max_seconds))
            ok = _wait(campaign, random.uniform(lo, hi), "Pause before the next message")
        if not ok:
            break

    Campaign.objects.filter(pk=campaign.pk, status=S.RUNNING).update(
        status=S.COMPLETED, finished_at=timezone.now(), next_action_at=None, note=""
    )
    final = _status(campaign.pk)
    log.info("campaign %s finished with status %s", campaign.pk, final)
    return final


def cleanup_unused_media(older_than=timedelta(days=1)) -> int:
    """Delete uploads that no campaign uses (e.g. attached and then removed from the composer).
    Files with a public link are kept: the link may be in messages people already received."""
    from .models import MediaFile

    n = 0
    stale = MediaFile.objects.filter(created_at__lt=timezone.now() - older_than, campaigns__isnull=True, public_token__isnull=True)
    for m in stale:
        m.file.delete(save=False)
        m.delete()
        n += 1
    return n
