"""
SQL for the two high-volume tables. On PostgreSQL they're partitioned by day on
received_at, so old days are dropped in an instant (EVENT_RETENTION_DAYS); a
DEFAULT partition catches events with a strange clock. On SQLite (local tests)
they're plain tables with the same columns.

The engine writes these tables with plain SQL and the worker creates/drops the
daily partitions (task E11); the names come from partition_name() on both sides.
"""

import datetime

PARTITIONED = ("events_eventlog", "events_delivery")

POSTGRES_CREATE = """
CREATE TABLE events_eventlog (
    id uuid NOT NULL,
    received_at timestamptz NOT NULL,
    site_id bigint NOT NULL,
    event_name varchar(60) NOT NULL,
    event_id varchar(64) NOT NULL,
    source varchar(6) NOT NULL,
    page_url text NULL,
    visitor_id varchar(40) NULL,
    ip_trunc inet NULL,
    country char(2) NULL,
    user_agent text NULL,
    is_bot boolean NOT NULL DEFAULT false,
    consent jsonb NOT NULL DEFAULT '{}',
    user_hashed jsonb NOT NULL DEFAULT '{}',
    data jsonb NOT NULL DEFAULT '{}',
    click_ids jsonb NOT NULL DEFAULT '{}',
    PRIMARY KEY (id, received_at)
) PARTITION BY RANGE (received_at);
CREATE INDEX events_eventlog_site_time ON events_eventlog (site_id, received_at DESC);
CREATE INDEX events_eventlog_site_name_time ON events_eventlog (site_id, event_name, received_at DESC);
CREATE INDEX events_eventlog_site_event_id ON events_eventlog (site_id, event_id);
CREATE TABLE events_eventlog_default PARTITION OF events_eventlog DEFAULT;

CREATE SEQUENCE events_delivery_id_seq AS bigint;
CREATE TABLE events_delivery (
    id bigint NOT NULL DEFAULT nextval('events_delivery_id_seq'),
    received_at timestamptz NOT NULL,
    event_uuid uuid NOT NULL,
    site_id bigint NOT NULL,
    destination_id bigint NOT NULL,
    status varchar(8) NOT NULL,
    skip_reason varchar(30) NULL,
    http_status smallint NULL,
    attempts smallint NOT NULL DEFAULT 0,
    response text NULL,
    sent_at timestamptz NULL,
    PRIMARY KEY (id, received_at)
) PARTITION BY RANGE (received_at);
ALTER SEQUENCE events_delivery_id_seq OWNED BY events_delivery.id;
CREATE INDEX events_delivery_event ON events_delivery (event_uuid);
CREATE INDEX events_delivery_dest_status_time ON events_delivery (destination_id, status, received_at DESC);
CREATE TABLE events_delivery_default PARTITION OF events_delivery DEFAULT;
"""

SQLITE_CREATE = """
CREATE TABLE events_eventlog (
    id char(36) NOT NULL PRIMARY KEY,
    received_at datetime NOT NULL,
    site_id bigint NOT NULL,
    event_name varchar(60) NOT NULL,
    event_id varchar(64) NOT NULL,
    source varchar(6) NOT NULL,
    page_url text NULL,
    visitor_id varchar(40) NULL,
    ip_trunc varchar(39) NULL,
    country char(2) NULL,
    user_agent text NULL,
    is_bot bool NOT NULL DEFAULT 0,
    consent text NOT NULL DEFAULT '{}',
    user_hashed text NOT NULL DEFAULT '{}',
    data text NOT NULL DEFAULT '{}',
    click_ids text NOT NULL DEFAULT '{}'
);
CREATE INDEX events_eventlog_site_time ON events_eventlog (site_id, received_at DESC);
CREATE INDEX events_eventlog_site_name_time ON events_eventlog (site_id, event_name, received_at DESC);
CREATE INDEX events_eventlog_site_event_id ON events_eventlog (site_id, event_id);

CREATE TABLE events_delivery (
    id integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    received_at datetime NOT NULL,
    event_uuid char(36) NOT NULL,
    site_id bigint NOT NULL,
    destination_id bigint NOT NULL,
    status varchar(8) NOT NULL,
    skip_reason varchar(30) NULL,
    http_status smallint NULL,
    attempts smallint NOT NULL DEFAULT 0,
    response text NULL,
    sent_at datetime NULL
);
CREATE INDEX events_delivery_event ON events_delivery (event_uuid);
CREATE INDEX events_delivery_dest_status_time ON events_delivery (destination_id, status, received_at DESC);
"""


def partition_name(table, day):
    return f"{table}_p{day:%Y%m%d}"


def create_partitions_sql(day, days_ahead=3):
    """CREATE statements for `day` and the next `days_ahead` days (UTC), for both tables."""
    statements = []
    for offset in range(days_ahead + 1):
        start = day + datetime.timedelta(days=offset)
        end = start + datetime.timedelta(days=1)
        for table in PARTITIONED:
            statements.append(
                f"CREATE TABLE IF NOT EXISTS {partition_name(table, start)} PARTITION OF {table} "
                f"FOR VALUES FROM ('{start:%Y-%m-%d} 00:00:00+00') TO ('{end:%Y-%m-%d} 00:00:00+00')"
            )
    return statements


def _run(schema_editor, script):
    with schema_editor.connection.cursor() as cursor:
        for statement in script.split(";"):
            if statement.strip():
                cursor.execute(statement)


def create_tables(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        _run(schema_editor, POSTGRES_CREATE)
        today = datetime.datetime.now(datetime.UTC).date()
        _run(schema_editor, ";".join(create_partitions_sql(today)))
    else:
        _run(schema_editor, SQLITE_CREATE)


def drop_tables(apps, schema_editor):
    # Dropping a partitioned table drops its partitions and the owned sequence too.
    _run(schema_editor, "DROP TABLE IF EXISTS events_delivery; DROP TABLE IF EXISTS events_eventlog")
