"""
Writes the Django models for Marketian SMS from the Laravel reference schema, so the 45 tables
match the original exactly (columns, types, enums, defaults, keys, indexes) instead of being retyped.

    python tools/generate_models.py          (from sites/sms/api)

Sources, all in ../laravel/database:
  schema/expected-schema.json   the final structure: columns, types, enum values, indexes, foreign keys
  sql/baseline_*.sql            defaults and JSON columns of the original 42 tables
  migrations/2026_11_11_*.php   defaults and JSON columns of what that migration added

Run once to create the models, then edit the models by hand: this is a starting point, not a
build step. Field names become snake_case (organizationId → organization), tables keep their names.
Already applied by hand afterwards (rerunning would undo them): accounts.User (no password /
last_login columns, sign-in helpers) and messaging.Message.campaign (related_name="messages").
"""

import json
import re
from collections import defaultdict
from pathlib import Path

API = Path(__file__).resolve().parent.parent
DB = API.parent / "laravel" / "database"

APPS = {
    "accounts": ["users", "sessions", "verification_tokens", "invitations"],
    "orgs": ["organizations", "organization_members", "roles", "permissions", "role_permissions"],
    "contacts": ["contacts", "contact_groups", "contact_group_members", "suppression_entries", "blocklist_entries"],
    "messaging": ["templates", "sender_ids", "provider_sender_ids", "messages", "message_events", "campaigns",
                  "campaign_recipients", "campaign_uploads", "inbound_webhook_events"],
    "billing": ["wallets", "wallet_transactions", "pricing_plans", "credit_packages", "payments", "payment_methods", "invoices"],
    "developers": ["api_keys", "api_logs", "webhooks", "webhook_deliveries", "idempotency_keys"],
    "support": ["support_tickets", "support_messages", "contact_requests", "abuse_reports", "notifications",
                "notification_preferences"],
    "system": ["settings", "audit_logs", "counters", "rate_limit_buckets"],
}
MODEL_NAMES = {"webhooks": "WebhookEndpoint"}  # Laravel's name for that table
APP_OF = {table: app for app, tables in APPS.items() for table in tables}
ON_DELETE = {"CASCADE": "models.CASCADE", "SET NULL": "models.SET_NULL", "RESTRICT": "models.RESTRICT",
             "NO ACTION": "models.DO_NOTHING"}


def model_name(table):
    if table in MODEL_NAMES:
        return MODEL_NAMES[table]
    words = table.split("_")
    last = words[-1]
    last = last[:-3] + "y" if last.endswith("ies") else last[:-1] if last.endswith("s") else last
    return "".join(w.capitalize() for w in words[:-1] + [last])


def snake(name):
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", name).lower()


def column_hints():
    """{table: {column: (default_sql or None, is_json)}} from the baseline SQL and the later migration."""
    hints = defaultdict(dict)
    texts = [p.read_text("utf-8") for p in sorted((DB / "sql").glob("baseline_*.sql"))]
    texts += [p.read_text("utf-8") for p in sorted((DB / "migrations").glob("2026_11_11_*.php"))]
    # One column per line; its definition can hold commas (ENUM('a', 'b'), DECIMAL(14, 4)).
    col = re.compile(r"^\s*`(\w+)`\s+([A-Z].*?),?\s*$", re.M)
    for text in texts:
        for table, body in re.findall(r"CREATE TABLE `(\w+)` \((.*?)\n\s*\)\s*DEFAULT CHARACTER", text, re.S):
            for name, definition in col.findall(body):
                if definition.startswith(("INDEX", "UNIQUE", "PRIMARY", "CONSTRAINT")):
                    continue
                hints[table][name] = parse_hint(definition)
        for table, name, definition in re.findall(r"addColumn\('(\w+)', '(\w+)', [\"'](.*?)[\"']\);", text):
            hints[table][name] = parse_hint(definition)
    return hints


def parse_hint(definition):
    m = re.search(r"DEFAULT\s+('(?:[^']*)'|[\w.()-]+)", definition)
    return (m.group(1) if m else None, definition.strip().upper().startswith("JSON"))


def python_default(raw, kind):
    if raw is None or raw.upper().startswith("CURRENT_TIMESTAMP"):
        return None
    if raw.startswith("'"):
        return repr(raw.strip("'"))
    if kind == "bool":
        return "True" if raw.lower() in ("true", "1") else "False"
    if kind == "decimal":
        return f'Decimal("{raw}")'
    return raw


def parse_fks(table_spec):
    fks = {}
    for spec in (table_spec["fks"] or {}).values():
        m = re.match(r"(\w+) -> (\w+)\((\w+)\) ON DELETE ([A-Z ]+?) ON UPDATE", spec)
        column, target, _, on_delete = m.groups()
        fks[column] = (target, on_delete)
    return fks


def index_fields(spec):
    return [c.strip() for c in re.search(r"\((.*)\)", spec).group(1).split(",")]


def generate():
    schema = json.loads((DB / "schema" / "expected-schema.json").read_text("utf-8"))["tables"]
    assert set(schema) == set(APP_OF), set(schema) ^ set(APP_OF)
    hints = column_hints()
    out = {app: [] for app in APPS}
    stats = defaultdict(int)

    for table in sorted(schema):
        spec, app = schema[table], APP_OF[table]
        name = model_name(table)
        fks = parse_fks(spec)
        primary = index_fields(spec["indexes"]["PRIMARY"])
        uniques_single = {index_fields(v)[0] for k, v in spec["indexes"].items()
                          if k != "PRIMARY" and v.startswith("UNIQUE") and len(index_fields(v)) == 1}
        # Several foreign keys to one table need distinct reverse names.
        targets = defaultdict(int)
        for target, _ in fks.values():
            targets[target] += 1

        is_user = table == "users"
        lines = [f"class {name}({'AbstractBaseUser' if is_user else 'models.Model'}):"]
        field_of = {}
        for column, sql_type in spec["columns"].items():
            null = " NULL" in sql_type and "NOT NULL" not in sql_type
            base = sql_type.split(" NOT NULL")[0].split(" NULL")[0]
            default_raw, is_json = hints.get(table, {}).get(column, (None, False))
            opts = []
            if null:
                opts += ["null=True", "blank=True"]
            field = snake(column)
            if column in fks:
                target, on_delete = fks[column]
                field = snake(column[:-2]) if column.endswith("Id") else field
                ref = "settings.AUTH_USER_MODEL" if target == "users" else (
                    f'"{model_name(target)}"' if APP_OF[target] == app else f'"{APP_OF[target]}.{model_name(target)}"')
                if targets[target] > 1:
                    opts.append(f'related_name="{table}_as_{field}"')
                if column in uniques_single:
                    opts.append("unique=True")
                if snake(column) != field + "_id":
                    opts.append(f'db_column="{snake(column)}"')
                kind = "OneToOneField" if column in uniques_single else "ForeignKey"
                if kind == "OneToOneField":
                    opts.remove("unique=True")
                definition = f"models.{kind}({ref}, {ON_DELETE[on_delete]}, {', '.join(opts)})".replace(", )", ")")
                field_of[column] = field
                lines.append(f"    {field} = {definition}")
                stats["fk"] += 1
                continue

            field_of[column] = field
            if column in primary and len(primary) == 1 and base == "char(36)":
                lines.append(f"    {field} = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)")
                continue
            if column in primary and len(primary) == 1:
                opts.append("primary_key=True")
            elif column in uniques_single:
                opts.append("unique=True")

            kind = None
            if is_json or (base == "longtext" and default_raw is None and column in ("scopes", "ipAllowlist")):
                cls = "JSONField"
                if not null:
                    opts.append("default=dict" if column not in ("scopes", "ipAllowlist", "headers", "events") else "default=list")
            elif base.startswith("enum("):
                # The schema file lower-cases types; the stored values are upper case (as in the SQL).
                values = [v.upper() for v in re.findall(r"'([^']*)'", base)]
                cls = "CharField"
                opts.insert(0, f"max_length={max(len(v) for v in values)}")
                opts.append("choices=[" + ", ".join(f'("{v}", "{v}")' for v in values) + "]")
            elif base == "char(36)":
                cls = "UUIDField"
            elif base.startswith(("varchar(", "char(")):
                cls = "CharField"
                opts.insert(0, f"max_length={re.search(r'\((\d+)\)', base).group(1)}")
            elif base in ("text", "longtext"):
                cls = "TextField"
            elif base.startswith("decimal("):
                digits, places = re.search(r"\((\d+),(\d+)\)", base).groups()
                cls, kind = "DecimalField", "decimal"
                opts.insert(0, f"max_digits={digits}, decimal_places={places}")
            elif base == "int":
                cls = "IntegerField"
            elif base == "bigint":
                cls = "BigIntegerField"
            elif base == "tinyint":
                cls, kind = "BooleanField", "bool"
            elif base.startswith("datetime"):
                cls = "DateTimeField"
                if column == "createdAt":
                    opts.append("auto_now_add=True")
                elif column == "updatedAt":
                    opts.append("auto_now=True")
            else:
                raise ValueError(f"{table}.{column}: unknown type {base}")
            default = python_default(default_raw, kind)
            if default is not None and not any(o.startswith("default=") for o in opts):
                opts.append(f"default={default}")
            lines.append(f"    {field} = models.{cls}({', '.join(opts)})")

        meta = [f'        db_table = "{table}"']
        constraints, indexes = [], []
        if len(primary) > 1:
            lines.insert(1, "    pk = models.CompositePrimaryKey(" + ", ".join(f'"{field_of[c]}"' for c in primary) + ")")
        for key, value in spec["indexes"].items():
            if key == "PRIMARY":
                continue
            cols = index_fields(value)
            fields = [field_of[c] for c in cols]
            if value.startswith("UNIQUE"):
                if len(cols) > 1:
                    constraints.append(f'models.UniqueConstraint(fields={fields}, name="{key[:63]}")')
            elif not (len(cols) == 1 and cols[0] in fks):  # Django indexes foreign keys itself
                short = re.sub(r"[^a-z0-9]", "", table)[:14] + "_" + "_".join(f[:4] for f in fields)
                indexes.append(f'models.Index(fields={fields}, name="{short[:30]}")')
        if constraints:
            meta.append("        constraints = [" + ", ".join(constraints) + "]")
        if indexes:
            meta.append("        indexes = [" + ", ".join(indexes) + "]")
        lines += ["", "    class Meta:"] + meta
        if is_user:
            lines += ["", "    USERNAME_FIELD = \"email\"", "    REQUIRED_FIELDS = [\"name\"]", "    objects = UserManager()"]
        out[app].append("\n".join(lines))
        stats["tables"] += 1

    for app, classes in out.items():
        header = ['"""Generated by tools/generate_models.py from the Laravel reference schema, then edited by hand."""', "",
                  "import uuid", "from decimal import Decimal", "", "from django.conf import settings", "from django.db import models"]
        if app == "accounts":
            header += ["from django.contrib.auth.base_user import AbstractBaseUser", "", "from .managers import UserManager"]
        body = "\n".join(header) + "\n\n\n" + "\n\n\n".join(classes) + "\n"
        (API / app).mkdir(exist_ok=True)
        (API / app / "models.py").write_text(body, "utf-8")
    print(dict(stats))


if __name__ == "__main__":
    generate()
