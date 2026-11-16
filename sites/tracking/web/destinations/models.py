"""
A Destination is one place a site's events are sent: a Meta pixel, a GA4 stream,
a TikTok pixel or the client's own webhook. Its secret (access token, API secret)
is stored encrypted and never shown again: only its last four characters.
"""

import json

from django.core.exceptions import ValidationError
from django.db import models

from common import crypto
from tracker.models import Site

from . import registry


class Destination(models.Model):
    WORKSPACE_FIELD = "site__workspace"

    OK, WARN, ERROR = "ok", "warn", "error"

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="destinations")
    type = models.CharField(max_length=20, choices=registry.CHOICES)
    label = models.CharField(max_length=60, default="Main")
    config = models.JSONField(default=dict, blank=True)
    secret_enc = models.TextField(null=True, blank=True, editable=False)
    secret_hint = models.CharField(max_length=8, blank=True, editable=False)
    # Overrides only: {"PageView": null} stops page views; missing events use the type's defaults.
    event_map = models.JSONField(default=dict, blank=True)
    consent_required = models.JSONField(null=True, blank=True)  # None → the type's default when saved
    send_pii = models.BooleanField(default=True, help_text="Send hashed email and phone, so the platform can match more visitors.")
    enabled = models.BooleanField(default=True)
    health = models.CharField(max_length=8, choices=[(OK, "OK"), (WARN, "Warning"), (ERROR, "Error")], default=OK)
    last_error = models.TextField(null=True, blank=True)
    last_success_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["type", "label"]
        constraints = [models.UniqueConstraint(fields=["site", "type", "label"], name="unique_destination_label_per_site")]

    def __str__(self):
        return f"{self.kind.label}: {self.label}"

    @property
    def kind(self):
        return registry.get_type(self.type)

    def clean(self):
        kind = self.kind
        self.config = registry.clean_fields(kind.config_fields, self.config)
        self.event_map = registry.clean_event_map(self.type, self.event_map)
        if self.consent_required is not None:
            unknown = set(self.consent_required) - set(registry.CONSENT_KEYS)
            if unknown:
                raise ValidationError({"consent_required": f"Unknown consent types: {', '.join(sorted(unknown))}."})

    def save(self, *args, **kwargs):
        if self.consent_required is None:
            self.consent_required = list(self.kind.default_consent)
        super().save(*args, **kwargs)

    # --- Secret ---------------------------------------------------------------
    def set_secret(self, values):
        """Check and encrypt the secret fields ({"access_token": "..."}). Call save() afterwards."""
        cleaned = registry.clean_fields(self.kind.secret_fields, values)
        self.secret_enc = crypto.encrypt(json.dumps(cleaned))
        first = cleaned[self.kind.secret_fields[0].name]
        self.secret_hint = first[-4:]

    def get_secret(self):
        """The decrypted secret fields. Only for sending: never put this in a page, log or audit entry."""
        if not self.secret_enc:
            return {}
        return json.loads(crypto.decrypt(self.secret_enc))

    @property
    def has_secret(self):
        return bool(self.secret_enc)

    @property
    def masked_secret(self):
        return f"••••{self.secret_hint}" if self.secret_hint else ""

    # --- Events ---------------------------------------------------------------
    def effective_event_map(self):
        """{our event: their event or None}: the type's defaults with this destination's overrides."""
        return self.kind.default_event_map | self.event_map
