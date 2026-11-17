# Marketian SMS API (Django)

The backend of Marketian SMS: Django + Django REST Framework + Celery on PostgreSQL. It replaces
the Laravel API in `../laravel` and must answer the same `/api/v1` contract, so the Next.js panel
in `../web` keeps working unchanged. Plan and task list: [Project Planning/08-sms-plan.md](../../../Project%20Planning/08-sms-plan.md).

**Status:** foundation only. The 45 tables, the response envelope, error codes and `/api/v1/health`
exist; [docs/contract.md](docs/contract.md) lists the 248 endpoints still to build (progress is in
`docs/contract.json`, `"done": true`).

## Layout

```
api/
├── product/       settings (production guard for secrets), urls, wsgi, Celery app
├── common/        response envelope + error codes (envelope.py), request IDs, health, tests
├── accounts/      users (Marketian sign-in, no passwords), sessions, verification tokens, invitations
├── orgs/          organisations, members, roles, permissions
├── contacts/      contacts, groups, suppression and blocklists
├── messaging/     templates, sender IDs, messages and events, campaigns, uploads, inbound webhooks
├── billing/       wallets and their ledger, pricing plans, credit packages, payments, invoices
├── developers/    API keys, API logs, customer webhooks and deliveries, idempotency keys
├── support/       tickets, contact and abuse reports, notifications
├── system/        settings, audit log, counters, rate-limit buckets
├── tools/         generate_models.py (wrote the models from the Laravel schema; see below)
└── docs/          contract.md / contract.json: every endpoint the API must answer
```

## Run the tests on your PC

Python 3.12 (like the WA backend; the PC's default 3.15 has no DRF release):

```bash
cd sites/sms/api
py -3.12 -m venv .venv                       # Linux/macOS: python3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python manage.py test          # SQLite: quick
```

Money and queue code relies on PostgreSQL row locks, so also run the suite on PostgreSQL before
pushing (Docker Desktop running):

```bash
docker build -t sms-api-test .
docker network create sms-test
docker run -d --rm --name sms-pgtest --network sms-test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=sms postgres:17-alpine
docker run --rm --network sms-test -e DEBUG=True -e POSTGRES_DB=sms -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=test -e POSTGRES_HOST=sms-pgtest --entrypoint sh sms-api-test -c "python manage.py test"
docker stop sms-pgtest && docker network rm sms-test
```

The test run prints `[contract] N of 248 endpoints done`.

## Conventions

- **Same contract as Laravel.** Paths, JSON field names (camelCase), status codes and error codes
  match `../laravel` and `../docs/11-laravel-api-reference.md`. Every JSON answer uses the envelope
  in `common/envelope.py` (`ok()`, `fail()`, `raise ApiError(...)`). Error codes are public: only add.
- **Database:** Django names (snake_case columns), the original table names. Money is
  `DECIMAL(14,4)` as in the reference, handled with `Decimal`, never floats. Status values are
  upper case (`ACTIVE`, `SUPER_ADMIN`), as stored by the reference.
- **Models were generated** by `tools/generate_models.py` from `../laravel/database/schema/expected-schema.json`
  plus the baseline SQL (defaults, JSON columns), then edited by hand. Hand edits so far:
  `accounts.User` (Marketian sign-in: no Django password or last_login columns),
  `messaging.Message.campaign` (`related_name="messages"`, because Campaign has a `message` field).
  Don't rerun the generator over edited models; change models directly and make migrations.
- **Porting an endpoint:** read the Laravel controller and service, port its feature tests from
  `../laravel/tests` first, implement until they pass, then set `"done": true` for it in `docs/contract.json`.
