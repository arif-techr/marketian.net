import datetime
import uuid

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .models import DailyStat, Delivery, EventLog
from .partitions import create_partitions_sql, partition_name


class PartitionSqlTests(SimpleTestCase):
    def test_partition_names_and_ranges(self):
        day = datetime.date(2026, 12, 31)
        self.assertEqual(partition_name("events_eventlog", day), "events_eventlog_p20261231")
        statements = create_partitions_sql(day, days_ahead=1)
        self.assertEqual(len(statements), 4)  # two days × two tables
        self.assertIn("events_eventlog_p20261231 PARTITION OF events_eventlog", statements[0])
        self.assertIn("FROM ('2026-12-31 00:00:00+00') TO ('2027-01-01 00:00:00+00')", statements[0])
        self.assertIn("events_delivery_p20270101", statements[3])


class EventTableTests(TestCase):
    """The engine writes these tables; here we only check Django can read what it writes."""

    def test_tables_exist_and_read_back(self):
        event_uuid = uuid.uuid4()
        now = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO events_eventlog (id, received_at, site_id, event_name, event_id, source, is_bot, consent, user_hashed, data, click_ids)"
                " VALUES (%s, %s, 1, 'Purchase', 'ord-1', 'server', %s, '{}', '{\"em\": \"abc\"}', '{\"value\": 10}', '{}')",
                [event_uuid.hex if connection.vendor == "sqlite" else event_uuid, now, False],
            )
            cursor.execute(
                "INSERT INTO events_delivery (received_at, event_uuid, site_id, destination_id, status, attempts) VALUES (%s, %s, 1, 7, 'sent', 1)",
                [now, event_uuid.hex if connection.vendor == "sqlite" else event_uuid],
            )
        event = EventLog.objects.get()
        self.assertEqual((event.id, event.event_name, event.data, event.user_hashed), (event_uuid, "Purchase", {"value": 10}, {"em": "abc"}))
        delivery = Delivery.objects.get(event_uuid=event_uuid)
        self.assertEqual((delivery.destination_id, delivery.status), (7, Delivery.SENT))

    def test_daily_stats_have_a_composite_key(self):
        day = datetime.date(2026, 11, 10)
        DailyStat.objects.create(site_id=1, day=day, destination_id=0, event_name="PageView", received=5)
        DailyStat.objects.create(site_id=1, day=day, destination_id=7, event_name="PageView", sent=4)
        stat = DailyStat.objects.get(pk=(1, day, 0, "PageView"))
        self.assertEqual(stat.received, 5)
        self.assertEqual(DailyStat.objects.count(), 2)
