---
name: marketian-database
description: Use when changing models or migrations, creating a product database, working with PostgreSQL, backups or restores, or deciding where data lives in the Marketian repo.
---

# Marketian databases

## The rule (17 Nov 2026)
- **Own PostgreSQL server:** the portfolio (`marketian-db`), WA (`wa-db`, plus Redis, on the internal
  `wa-data` network) and SMS (`sms-db`).
- **Everyone else** (accounts, metadata, links, tracking, every new product): its own database and
  login on the shared server (`infra/`, service `postgres`, internal network `shared-db`), made with
  `bash scripts/create-db.sh <name>`. `create-db.sh` is safe to rerun: it keeps the data and resets
  only the password, so the product's `.env` must then get the new `POSTGRES_PASSWORD`.
- **No foreign keys or queries across products.** Link only by the Marketian user ID (`sub` claim) and
  organisation UUID. A product never connects to another product's database.

## Migrations
- Change the model, then `python manage.py makemigrations <app>`; read the generated file.
- Before committing: `makemigrations --check` (nothing pending) and the full test suite.
- Migrations run automatically at container start (`docker/entrypoint.sh`, `RUN_MIGRATIONS=1`), so a
  deploy applies them. Make them safe for the live data:
  - Adding a required column to a table with rows: give a default, or add nullable → backfill
    (data migration) → make required in a later migration.
  - Renames: use `RenameField` / `RenameModel`, never drop + add.
  - Never edit or delete a migration that was deployed. Add a new one.
  - Large tables (tracking events, SMS messages): avoid table rewrites; tracking event tables are
    partitioned, so follow its existing pattern.
- Tests run on SQLite locally. Code that relies on PostgreSQL (row locks with `select_for_update`,
  JSON queries, partitions, money in SMS) must also pass on PostgreSQL 17 in Docker (see
  `sites/sms/api/README.md` for the throwaway-container recipe).
- Money: `DecimalField`, `Decimal` in code, never floats.

## Backups and restore
- `scripts/backup.sh` dumps every `*-db` service, every database on the shared server plus its
  roles, and the `/app/media`, `/app/keys`, `/app/sessions` folders into `backups/` (14 days). Not
  scheduled on the server yet (STATUS.md "Open"); off-server copies aren't set up either.
- Restore one shared database (ask the user first; it overwrites):
  ```bash
  gunzip -c backups/shared_<db>_db_<stamp>.sql.gz | docker compose exec -T postgres psql -U postgres -d <db>
  ```
  Own-server site: `gunzip -c backups/<site>_db_<stamp>.sql.gz | docker compose exec -T <site>-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'`.
- Losing `accounts` keys (`/app/keys`) signs everyone out of every product: keep them in backups.

## Looking at live data
Read-only, and only when the user asks: `docker compose exec postgres psql -U postgres -d <db>`.
Never run `UPDATE`/`DELETE` on live data without showing the statement and getting a yes.
