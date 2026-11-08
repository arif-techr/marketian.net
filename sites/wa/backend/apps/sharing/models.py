"""Sharing WhatsApp accounts, contact lists and templates with another user's workspace.

The sharer makes an invitation for a username and picks the items; a one-time code (valid 10 minutes)
appears on their screen. The other user sees the invitation and accepts it by typing that code, which
turns it into Share rows. Shared items can be used (sent from / sent to / used as a message) but not
changed, and the sharer can stop sharing at any time.
"""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

CODE_VALID_FOR = timedelta(minutes=10)
MAX_ATTEMPTS = 5


def _digest(invite_pk: int, code: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), f"{invite_pk}:{code}".encode(), hashlib.sha256).hexdigest()


class ShareInvite(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for the code"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        FAILED = "failed", "Too many wrong codes"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="share_invites_sent")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="share_invites_received")
    accounts = models.ManyToManyField("whatsapp.WhatsAppAccount", blank=True, related_name="+")
    contact_lists = models.ManyToManyField("contacts.ContactList", blank=True, related_name="+")
    templates = models.ManyToManyField("broadcasts.MessageTemplate", blank=True, related_name="+")
    code_digest = models.CharField(max_length=64, editable=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.owner} → {self.to_user} ({self.status})"

    def set_new_code(self) -> str:
        """Give the invitation a fresh 6-digit code and 10 more minutes. Returns the code (shown once)."""
        code = f"{secrets.randbelow(10**6):06d}"
        self.code_digest = _digest(self.pk, code)
        self.expires_at = timezone.now() + CODE_VALID_FOR
        self.save(update_fields=["code_digest", "expires_at"])
        return code

    def code_matches(self, code: str) -> bool:
        return bool(self.code_digest) and hmac.compare_digest(self.code_digest, _digest(self.pk, str(code).strip()))

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.PENDING and self.expires_at > timezone.now()


class Share(models.Model):
    """One item another workspace may use. Exactly one of account / contact_list / template is set."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shares_given")
    grantee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shares_received")
    account = models.ForeignKey("whatsapp.WhatsAppAccount", null=True, blank=True, on_delete=models.CASCADE, related_name="shares")
    contact_list = models.ForeignKey("contacts.ContactList", null=True, blank=True, on_delete=models.CASCADE, related_name="shares")
    template = models.ForeignKey("broadcasts.MessageTemplate", null=True, blank=True, on_delete=models.CASCADE, related_name="shares")
    invite = models.ForeignKey(ShareInvite, null=True, blank=True, on_delete=models.SET_NULL, related_name="shares")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["grantee", "account"], name="unique_account_share"),
            models.UniqueConstraint(fields=["grantee", "contact_list"], name="unique_list_share"),
            models.UniqueConstraint(fields=["grantee", "template"], name="unique_template_share"),
            models.CheckConstraint(
                condition=(models.Q(account__isnull=False, contact_list__isnull=True, template__isnull=True)
                           | models.Q(account__isnull=True, contact_list__isnull=False, template__isnull=True)
                           | models.Q(account__isnull=True, contact_list__isnull=True, template__isnull=False)),
                name="share_exactly_one_item",
            ),
        ]

    @property
    def kind(self) -> str:
        return "account" if self.account_id else "list" if self.contact_list_id else "template"

    @property
    def item(self):
        return self.account or self.contact_list or self.template

    def __str__(self):
        return f"{self.kind} {self.item} → {self.grantee}"
