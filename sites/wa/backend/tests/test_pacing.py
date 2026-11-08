"""Phones shared between campaigns: who gets a phone, waiting instead of failing, and the gap per phone."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.broadcasts import runner
from apps.broadcasts.models import Campaign, CampaignTarget
from apps.contacts.models import Contact
from apps.sharing.models import Share
from apps.whatsapp.models import WhatsAppAccount
from tests.helpers import me

pytestmark = pytest.mark.django_db


def phone(owner, label, n, shared_with=None):
    acc = WhatsAppAccount.objects.create(owner=owner, label=label, provider="fake", status="connected", phone=f"880100000000{n}")
    if shared_with:
        Share.objects.create(owner=owner, grantee=shared_with, account=acc)
    return acc


def campaign(owner, senders, *, status="scheduled", delay=0, targets=0, **kw):
    c = Campaign.objects.create(owner=owner, message="hi", status=status, delay_min_seconds=delay, delay_max_seconds=delay,
                                batch_size=0, **kw)
    c.sender_accounts.set(senders)
    for i in range(targets):
        ct = Contact.objects.create(owner=owner, phone=f"88017{c.pk:03d}{i:05d}")
        CampaignTarget.objects.create(campaign=c, contact=ct, recipient_jid=f"{ct.phone}@s.whatsapp.net", position=i, account_label="")
    return c


@pytest.fixture
def other(db):
    return get_user_model().objects.create_user("other", password="a-long-test-password")


def test_starts_on_its_free_phone_while_the_shared_one_is_busy(other):
    x, y = phone(me(), "X", 1, shared_with=other), phone(other, "Y", 2)
    a = campaign(me(), [x])
    b = campaign(other, [x, y])
    assert runner.claim_next().pk == a.pk
    assert runner.claim_next().pk == b.pk  # Y is free, so B doesn't wait for X
    b.refresh_from_db()
    account, status, _ = runner.pick_sender(b)
    assert account == y and status == ""  # ...and B leaves X to A


def test_the_campaign_that_started_first_keeps_the_phone(other):
    x = phone(me(), "X", 1, shared_with=other)
    now = timezone.now()
    a = campaign(me(), [x], status="running", claimed_at=now - timedelta(minutes=1))
    b = campaign(other, [x], status="running", claimed_at=now)
    assert runner.busy_accounts(a) == set()
    assert runner.busy_accounts(b) == {x.pk}
    assert runner.pick_sender(a)[0] == x
    assert runner.pick_sender(b)[:2] == (None, runner.BUSY)


def test_waits_instead_of_failing_while_its_phones_are_busy(provider, other, monkeypatch):
    x = phone(me(), "Shop phone", 1, shared_with=other)
    campaign(me(), [x], status="running", claimed_at=timezone.now() - timedelta(minutes=1))
    b = campaign(other, [x], status="running", claimed_at=timezone.now(), targets=1)
    waits = []

    def fake_wait(c, seconds, note):
        waits.append((seconds, note))
        Campaign.objects.filter(pk=c.pk).update(status="paused")  # stop the loop after one wait
        return False

    monkeypatch.setattr(runner, "_wait", fake_wait)
    runner.run_campaign(b.pk)
    assert waits == [(runner.BUSY_RECHECK, "Waiting: Shop phone is busy with another send")]
    assert b.targets.get().status == "pending" and provider.sent == []


def test_waiting_campaigns_say_why(other):
    x = phone(me(), "Shop phone", 1, shared_with=other)
    a = campaign(me(), [x])
    mine_too = campaign(me(), [phone(me(), "Other phone", 2)])
    b = campaign(other, [x])
    assert runner.claim_next().pk == a.pk
    assert runner.claim_next() is None
    b.refresh_from_db()
    mine_too.refresh_from_db()
    assert b.note == "Waiting: Shop phone is busy with another send"
    assert mine_too.note == "Waiting for your other send to finish"
    Campaign.objects.filter(pk=a.pk).update(status="completed")
    claimed = runner.claim_next()
    assert claimed.note == ""  # cleared once it starts


def test_keeps_a_gap_after_another_campaign_used_the_phone(provider, account, monkeypatch):
    WhatsAppAccount.objects.filter(pk=account.pk).update(last_sent_at=timezone.now() - timedelta(seconds=5))
    c = campaign(me(), [account], status="running", delay=25, targets=1, claimed_at=timezone.now())
    waits = []
    monkeypatch.setattr(runner, "_wait", lambda camp, seconds, note: waits.append((round(seconds), note)) or True)
    runner.run_campaign(c.pk)
    assert len(waits) == 1 and 18 <= waits[0][0] <= 20 and "Keeping a gap on Office" in waits[0][1]
    assert len(provider.sent) == 1


def test_no_extra_wait_when_the_gap_has_passed(provider, account, monkeypatch):
    WhatsAppAccount.objects.filter(pk=account.pk).update(last_sent_at=timezone.now() - timedelta(minutes=5))
    c = campaign(me(), [account], status="running", delay=25, targets=1, claimed_at=timezone.now())
    waits = []
    monkeypatch.setattr(runner, "_wait", lambda camp, seconds, note: waits.append(note) or True)
    runner.run_campaign(c.pk)
    assert waits == [] and len(provider.sent) == 1


def test_sending_records_when_the_phone_last_sent(provider, account):
    c = campaign(me(), [account], status="running", targets=1, claimed_at=timezone.now())
    before = timezone.now()
    runner.run_campaign(c.pk)
    account.refresh_from_db()
    assert account.last_sent_at >= before
