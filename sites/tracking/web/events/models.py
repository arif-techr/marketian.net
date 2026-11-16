"""
Read side of the event data. EventLog and Delivery are written by the engine and
created by SQL in events/partitions.py (partitioned by day on PostgreSQL), so
Django doesn't manage them. DailyStat keeps the per-day counters for good.
"""

from django.db import models


class EventLog(models.Model):
    # The table's real key is (id, received_at); id alone is unique (UUIDv7 from the edge).
    id = models.UUIDField(primary_key=True)
    received_at = models.DateTimeField()
    site_id = models.BigIntegerField()
    event_name = models.CharField(max_length=60)
    event_id = models.CharField(max_length=64)
    source = models.CharField(max_length=6)  # web / server
    page_url = models.TextField(null=True)
    visitor_id = models.CharField(max_length=40, null=True)
    ip_trunc = models.GenericIPAddressField(null=True)
    country = models.CharField(max_length=2, null=True)
    user_agent = models.TextField(null=True)
    is_bot = models.BooleanField(default=False)
    consent = models.JSONField(default=dict)
    user_hashed = models.JSONField(default=dict)  # SHA-256 only, never raw
    data = models.JSONField(default=dict)
    click_ids = models.JSONField(default=dict)

    class Meta:
        managed = False
        db_table = "events_eventlog"
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.event_name} {self.event_id}"


class Delivery(models.Model):
    QUEUED, SENT, FAILED, SKIPPED, RETRYING = "queued", "sent", "failed", "skipped", "retrying"
    STATUSES = [(QUEUED, "Queued"), (SENT, "Sent"), (FAILED, "Failed"), (SKIPPED, "Skipped"), (RETRYING, "Retrying")]

    id = models.BigIntegerField(primary_key=True)
    received_at = models.DateTimeField()
    event_uuid = models.UUIDField()
    site_id = models.BigIntegerField()
    destination_id = models.BigIntegerField()
    status = models.CharField(max_length=8, choices=STATUSES)
    skip_reason = models.CharField(max_length=30, null=True)  # not_mapped, no_consent, bot, disabled, duplicate
    http_status = models.SmallIntegerField(null=True)
    attempts = models.SmallIntegerField(default=0)
    response = models.TextField(null=True)
    sent_at = models.DateTimeField(null=True)

    class Meta:
        managed = False
        db_table = "events_delivery"
        ordering = ["id"]


class DailyStat(models.Model):
    """Counters per site, day (in the site's time zone), destination and event.
    destination_id 0 counts what the edge received. The worker adds to these with
    INSERT … ON CONFLICT DO UPDATE."""

    pk = models.CompositePrimaryKey("site_id", "day", "destination_id", "event_name")
    site_id = models.BigIntegerField()
    day = models.DateField()
    destination_id = models.BigIntegerField()
    event_name = models.CharField(max_length=60)
    received = models.IntegerField(default=0)
    sent = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    bots = models.IntegerField(default=0)

    class Meta:
        ordering = ["-day", "event_name"]

    def __str__(self):
        return f"{self.day} site {self.site_id} {self.event_name}"
