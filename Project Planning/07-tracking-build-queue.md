# Tracking: build task queue

As of: 2026-11-10. Status: **in progress** on branch `tracking` (W1–W10 written; 70 tests pass on SQLite and on PostgreSQL 17 in Docker). Work through the tasks top to bottom. Each one lists what it needs first, what to make, and how to know it's done.
Spec: [06-tracking-build-spec.md](06-tracking-build-spec.md). Overview: [05-tracking-product.md](05-tracking-product.md).

Legend: ⬜ to do · 🟡 in progress · ✅ done · ⛔ blocked

---

## Adjustments from reading the repo (2026-11-10)

The repo has moved on since the audit. **`sites/links` is now the newest and best template**: it has Marketian sign-in, htmx, a Dockerfile, an entrypoint that waits for the DB, and tests. Build the dashboard from it, not from `sites/metadata`. These changes to spec 06 follow from that:

| # | Spec 06 says | Use instead | Why |
|---|---|---|---|
| A1 | `web/config/` + `web/apps/<app>/` | `web/product/` (settings, urls, wsgi) + apps at `web/` root, as in `sites/links` | Same layout as every other site |
| A2 | App named `sites` | App named **`tracker`** (tables `tracker_site`, `tracker_domain`, `tracker_apikey`) | `sites` clashes with Django's own `django.contrib.sites` label |
| A3 | App `core` for workspaces | App **`workspaces`** | Clearer name |
| A4 | Postgres-only local dev | The partition migration checks the DB engine. On SQLite it creates plain tables, so `manage.py test` still runs on SQLite like the other sites. The engine always needs Postgres + Redis (Docker) | Keeps the "SQLite locally" convention for Django tests |
| A5 | Fastify + BullMQ + zod | Optional. A smaller choice: Node's built-in `http`, Redis lists/sorted sets for the retry queue, and hand-written validation. Then the only dependencies are `ioredis` + `pg`. Node 22.18+ runs `.ts` files directly (type stripping), so there's no build step | Fewer dependencies to keep updated. Decide at task E1 |
| A6 | `META_GRAPH_VERSION` empty | Default `v26.0` (released 29 July 2026). Keep it in env and check Meta's changelog every 6 months | Meta retires each version 2 years after the next one ships |
| A7 | GA4 hashed user data always | GA4 `user_data` only when there's a `user_id` (`external_id`). Phone hashed in E.164 **with `+`** for GA4 and TikTok, digits only for Meta. Send `ip_override` | GA4 Measurement Protocol rules |
| A8 | Caddyfile only | Also `proxy/Caddyfile.local`: `http://tracking.localhost` + a catch-all `http://` → `tracking-edge`, so a fake client host can be tested with `curl -H "Host: data.shop.test" http://localhost/...` | Local testing without real DNS |
| A9 | DNS verify always | Setting `DOMAIN_VERIFY_MODE=dns` (prod) / `trust` (local `.env` only) | Fake local domains can't pass a DNS check |

**Environment note:** the Claude workspace and the PC's Claude shell can't download packages. Django/Node tests must be run in Docker on the PC (`docker compose run --rm tracking-web python manage.py test`, `docker compose run --rm tracking-worker node --test`).

---

**Progress notes (2026-11-10):**
- T0.2: branch `tracking` made. Not committed yet. An untracked `marketian.net/` folder (a second clone of the repo) sits in the repo root: delete it or move it out.
- W1: `sites/tracking/web` exists and its tests pass on SQLite; sign-in through the Marketian account in Docker still to check (needs T0.4 and I1). The landing page sends signed-in people to `/sites/`, a bare list until W11.
- W2: the guard lives in `common/crypto.py` (`check_production_secrets`) and runs from settings. The Docker build's `collectstatic` sets `BUILD_ONLY=1` to skip it. A local `dev:` key is used only when `DEBUG` is on, and production refuses it.
- W3: models in `workspaces/models.py`; `request.workspace` / `request.membership` from `workspaces/middleware.py`; `for_workspace`, `get_for_workspace_or_404`, `WorkspaceScopedMixin`, `role_required`, `audit` in `workspaces/access.py`. Each model names its path to the workspace in `WORKSPACE_FIELD`.
- W4: test vector at `sites/tracking/web/docs/crypto-test-vector.json` (no AAD; base64 with padding).
- W6: `destinations/registry.py` holds each type's fields (with patterns and help text), secret fields, default event map and consent. `Destination.set_secret()` / `get_secret()` / `masked_secret`; `event_map` stores overrides only, `effective_event_map()` merges them with the defaults. Webhook URLs must be https unless `DEBUG`.
- W7: SQL in `events/partitions.py` (also gives the worker `partition_name()` / `create_partitions_sql()` for E11). `events_delivery.id` uses a sequence, not an identity column. Tested on postgres:17-alpine: partitions today…+3 + DEFAULT, indexes, and `migrate events zero`.
- W8: `common/publish.py`; signals connect in `common/apps.py`. Every change bumps `config_version`, then publishes after commit; a Redis failure is logged and never breaks the save. `cfg:site:{id}` also carries `api_keys` (prefix → SHA-256, for the edge's `/s` route) and `verify_tokens` (same-origin `_v`). `cfg:dest:{id}` is the whole destination (settings + secret) encrypted as one value. Old hosts/destinations are found from the previous `cfg:site` value. Checked against a real Redis.
- W9: `/internal/caddy-ask` and `/internal/healthz` (the Docker healthcheck now uses it). `/internal/` is exempt from the HTTPS redirect, because Caddy calls it over plain HTTP inside Docker.
- W10: `tracker/verify.py` `verify_domain()`. A verified domain becomes `failing` after 3 failed checks in a row, but keeps serving.
- Running the tests on PostgreSQL: build `web/` as an image and run `python manage.py test` in it next to a `postgres:17-alpine` container (psycopg has no wheel for the PC's Python 3.15).
- W5: tables are `tracker_site`, `tracker_domain`, `tracker_apikey`. `ApiKey.issue()` returns the full key once. `config_version` exists but nothing bumps it yet (W8).

---

## Phase T0: preparation (≈ 30 min)

| ID | Task | Needs | Done when |
|---|---|---|---|
| ⬜ T0.1 | Answer the open questions: product name, first client site + platform, log retention (default 14 days) | — | Written in 02-status.md |
| 🟡 T0.2 | Commit or ignore the current loose file (`Project Planning/04-database-design.md` is untracked). Start a branch `tracking` | — | `git status` clean, on branch `tracking` |
| ✅ T0.3 | Copy Project docs 05, 06, 07 into the PC's `Project Planning/` folder | — | Files in the repo |
| ⬜ T0.4 | Local: `docker compose exec accounts python manage.py register_product tracking http://tracking.localhost`. Keep the client ID/secret | accounts running | Credentials saved in `sites/tracking/web/.env` |
| ⬜ T0.5 | Local: `scripts/create-db.sh tracking` | postgres running | `POSTGRES_*` lines in `.env` |

## Phase T1-W: dashboard (`sites/tracking/web`, Django)

| ID | Task | Needs | Done when |
|---|---|---|---|
| 🟡 W1 | **Scaffold** from `sites/links`: `manage.py`, `product/`, `dashboard/` (landing, login, logout, context processor, middleware), `Dockerfile`, `docker/entrypoint.sh`, `static/`, `templates/base.html`. Rename to Tracking. Remove shortener/bio. Add `redis`, `cryptography`, `dnspython` to requirements | T0.2 | Site starts, sign-in with the Marketian account works, landing test passes |
| ✅ W2 | **Production guard:** refuse to start when `DEBUG=False` and `SECRET_KEY` or `TRACKING_ENC_KEYS` is missing or a placeholder | W1 | Test: settings raise `ImproperlyConfigured` |
| ✅ W3 | **`workspaces` app:** `Workspace`, `WorkspaceMember` (roles owner/admin/member/viewer), `AuditLog`. Middleware: `request.workspace` (creates a personal workspace at first sign-in). `WorkspaceScopedMixin` / helper `get_for_workspace_or_404`. `@role_required` | W1 | Tests: first sign-in creates a workspace + owner row; another user's object gives 404 |
| ✅ W4 | **`common/crypto.py`:** AES-256-GCM, format `v1:<key_id>:<base64(nonce‖ciphertext‖tag)>`, key list `TRACKING_ENC_KEYS` (first one encrypts, all can decrypt). Publish a **test vector** (fixed key, nonce, plaintext → ciphertext) in `docs/crypto-test-vector.json` for the Node side | W1 | Round-trip test + vector test pass |
| ✅ W5 | **`tracker` app models:** `Site` (public_key, path_prefix, loader_name, consent_mode, bot_filter, cookie_keeper, status, config_version, timezone, default_currency), `Domain` (hostname, mode, status, verify_token, dns_seen, fail_count…), `ApiKey` (prefix, SHA-256 hash, revoked_at). Random generators avoid block-list words | W3 | Migrations made; model tests (hostname must sit under primary_domain; prefix unique and not a blocked word) |
| ✅ W6 | **`destinations` app:** `Destination` model (type, label, config, secret_enc, secret_hint, event_map, consent_required, send_pii, enabled, health, last_error, last_success_at). `registry.py`: per type, its config fields, secret fields, default event map and default consent (Meta, GA4, TikTok, webhook) | W4, W5 | Tests: secret stored encrypted, never shown; defaults applied |
| ✅ W7 | **`events` app:** migration that creates partitioned `events_eventlog` + `events_delivery` (Postgres: `PARTITION BY RANGE (received_at)` + DEFAULT partition + today…+3; SQLite: plain tables). `managed=False` read models. `DailyStat` with `CompositePrimaryKey` (Django 5.2) | W5 | `migrate` works on both SQLite and Postgres; partitions listed in `\d+` |
| ✅ W8 | **Config publisher** (`common/publish.py`): on save/delete of Site/Domain/Destination (inside `transaction.on_commit`), write `cfg:host:*`, `cfg:site:{id}`, `cfg:dest:{id}` (still encrypted) and publish `cfg:changed`. Command `manage.py publish_all` | W6 | Tests with a fake Redis: keys written, removed domain disappears, paused site published |
| ✅ W9 | **`internal` app:** `GET /internal/caddy-ask?domain=` (200 only for verified/failing domains, 404 otherwise) and `/internal/healthz` | W5 | Tests: verified → 200, pending/unknown → 404 |
| ✅ W10 | **Domain verify:** service resolves the CNAME/A with dnspython and compares it to `EDGE_CNAME_TARGET` / `EDGE_PUBLIC_IP`. Same-origin mode fetches `https://<host>/<prefix>/_v` and compares the token. `DOMAIN_VERIFY_MODE=trust` for local | W5 | Tests with a mocked resolver: right target → verified, wrong → error message shown |
| ⬜ W11 | **Pages: sites** list (health dots), new, overview, settings (consent mode, bot filter, cookie keeper, pause, delete with confirm) | W5, W8 | Clicked through locally; tenancy tests |
| ⬜ W12 | **Page: setup.** Add domain, DNS instructions card (record type, name, target, Cloudflare grey-cloud note, "avoid the word tracking"), Verify button, install snippets (plain HTML, GTM custom HTML, WordPress) with copy buttons | W10, W11 | A test site shows a correct snippet with its own prefix and loader name |
| ⬜ W13 | **Page: destinations.** Add by type (forms from the registry), edit, event map table, enable/disable, delete, **Send test event** (puts a synthetic event with `test=true` on `ev:in`) | W6, W8 | Meta/GA4 can be added; secret shows only `••••1234` |
| ⬜ W14 | **Page: API keys.** Create (key shown once), revoke, `curl` example for server events | W5 | Test: only the hash is stored |
| ⬜ W15 | **Page: logs.** Live list from Redis `live:{site}` (htmx poll every 3 s), search the last N days in Postgres by event name / event_id, event detail with each delivery's status and response | W7 | Shows events written by the engine (after E-tasks) |
| ⬜ W16 | **Workspace pages:** members (invite by email of an existing Marketian user, change role, remove) and the audit log | W3 | Role tests: viewer can't edit, admin can't delete the workspace |
| ⬜ W17 | **Overview stats:** today / 7 / 30 days from `events_dailystat` per destination (sent, failed, skipped), top events | W7 | Numbers match the seeded data in a test |

## Phase T1-E: engine (`sites/tracking/engine`, Node)

| ID | Task | Needs | Done when |
|---|---|---|---|
| ⬜ E1 | **Scaffold:** `package.json` (Node ≥ 22.18, `"type": "module"`), `tsconfig.json` (type-check only), `Dockerfile` (one image, two commands), JSON logger, env config. Decide adjustment A5 (Fastify/BullMQ or built-ins) | — | `node --test` runs an empty suite in Docker |
| ⬜ E2 | **Shared libs:** crypto (reads the W4 test vector), PII normalise + SHA-256 (email, phone with BD `880` default, names, city, zip, country), UUIDv7, random IDs, Redis key names, event validation (v1 format in spec §5.2) | E1, W4 | Unit tests incl. the cross-language vector |
| ⬜ E3 | **Edge: site lookup.** In-memory cache from `cfg:host:*` / `cfg:site:*`, 60 s TTL, cleared on `cfg:changed` | E2, W8 | Test with a fake Redis |
| ⬜ E4 | **Edge: routes.** `GET /{p}/{loader}`, `POST /{p}/e`, `GET /{p}/e.gif`, `POST /{p}/s` (Bearer API key → hash lookup), `GET /{p}/_v`, `GET /healthz`. 404 unknown host, 413 too big, 429 rate limit, 204 paused | E3 | Tests for every status code |
| ⬜ E5 | **Edge: enrichment + cookies.** IP from `X-Real-IP`, truncated copy for storage, UA, bot flag (UA list; empty UA = bot), click IDs from the URL, `_mt_id` (HttpOnly, 400 d), `_fbc` from `fbclid`, keep `_fbp`. CORS only for the site's domain family | E4 | Tests: cookie flags and domain; wrong Origin gets no CORS headers |
| ⬜ E6 | **Edge → queue:** `XADD ev:in` (MAXLEN ~1M), counter `stat:{site}:{day}` received | E5 | Event appears in the stream |
| ⬜ E7 | **Loader `mt.js`:** queue stub, `track` (returns event_id), `identify`, `consent` (holds events in `basic` mode), auto PageView + SPA option, sendBeacon → fetch keepalive. ≤ 4 KB gzip | E4 | Browser test page sends PageView; size check passes |
| ⬜ E8 | **Worker: ingest.** `XREADGROUP` batches of 200 → multi-row insert into `events_eventlog` (`ON CONFLICT DO NOTHING`) → one `events_delivery` row per enabled destination (queued, or skipped with a reason: not_mapped / no_consent / bot / disabled) → delivery jobs → `XACK`. Claims stuck messages on start-up | E6, W7 | Restarting mid-batch makes no duplicate rows |
| ⬜ E9 | **Worker: deliver.** Job → adapter → HTTP (10 s timeout) → result. Retry 30 s, 2 m, 10 m, 30 m, 2 h on network/429/5xx; other 4xx final. Dedup `dedup:{site}:{dest}:{event_id}` 48 h. Update destination health / last_error / last_success_at. Push to `live:{site}` | E8 | Tests with a mock HTTP server: retry, final failure, dedup |
| ⬜ E10 | **Adapters:** Meta CAPI (`graph.facebook.com/{ver}/{pixel}/events`, `action_source`, fbc/fbp/IP/UA, hashed user_data, custom_data, `test_event_code`), GA4 MP (`client_id` from `_ga` or `_mt_id`, `user_id` + user_data rule A7, `ip_override`, test via `/debug/mp/collect`), webhook (HMAC signature). TikTok can wait for T2 | E9 | Request bodies match saved fixtures |
| ⬜ E11 | **Worker: maintenance.** Hourly: create partitions today…+3, drop ones older than `EVENT_RETENTION_DAYS`, alert if the DEFAULT partition has rows. Every 60 s: flush `stat:*` into `events_dailystat`. Daily: re-check domains (3 fails → `failing`) | E8 | SQL tested on a real Postgres in Docker |

## Phase T1-I: infrastructure

| ID | Task | Needs | Done when |
|---|---|---|---|
| ⬜ I1 | `sites/tracking/docker-compose.yml`: `tracking-web`, `tracking-edge`, `tracking-worker`, `tracking-redis` (internal network `tracking-private`, AOF, `maxmemory 256mb`, `noeviction`), memory limits, healthchecks | W1, E1 | `docker compose up` starts all four, healthy |
| ⬜ I2 | Root `docker-compose.yml` include. `proxy/Caddyfile`: `tracking.marketian.net` (blocks `/internal/*`), `edge.marketian.net`, `on_demand_tls { ask … }` and the catch-all `https://` block. `Caddyfile.local` per A8 | I1, W9 | Local: `curl -H "Host: data.shop.test" http://localhost/<p>/<loader>` returns mt.js |
| ⬜ I3 | `scripts/backup.sh`: dump `tracking` **without** `events_eventlog*` / `events_delivery*` data (`--exclude-table-data`). Skip `tracking-edge` / `tracking-redis` for file backups | I1 | Backup file is small and restores |
| ⬜ I4 | `.env.example` files (web + engine), README section (tree, first-time setup, local address, adding a client), STATUS.md | I2 | Someone new can follow it |
| ⬜ I5 | Smoke script `scripts/tracking-smoke.sh`: start stack → create site/domain/destination (webhook to a mock) → load the loader → send Purchase → wait for delivery `sent` | all above | Script ends with "OK" |

## Phase T1-L: go live

| ID | Task | Needs | Done when |
|---|---|---|---|
| ⬜ L1 | Run every test suite + smoke script. Fix failures | I5 | All green |
| ⬜ L2 | Commit, push, deploy (`register_product tracking https://tracking.marketian.net` on the server, `create-db.sh tracking`, `.env`, `deploy.sh tracking`) | L1 | `https://tracking.marketian.net` signs in |
| ⬜ L3 | First client: add `data.<client>.com` (CNAME → `edge.marketian.net`), verify, HTTPS works, install snippet + `eventID` on their Meta pixel | L2, T0.1 | Loader loads over HTTPS from the client's subdomain |
| ⬜ L4 | Meta destination with `test_event_code` → events visible in Events Manager test tab and **deduplicated** with the browser pixel. GA4 Realtime shows them. Then remove the test code | L3 | **T1 done** (spec 06 §11) |

---

## After T1 (queued, not detailed yet)
- **T2:** TikTok adapter, cookie keeper endpoint `/{p}/c` (+ `_ga` refresh), GeoLite2 country, consent rules per destination in the UI, failure e-mails, Meta/TikTok batching.
- **T2 or earlier if clients sell mostly on iPhone:** same-origin path mode (Cloudflare Worker + Nginx snippet generator, `_v` verification).
- **T3:** WordPress/WooCommerce plugin, Snapchat/Pinterest/LinkedIn, stats charts, staff metrics page.
- **T4:** self-serve signup, plans with event quotas, billing.

## Rough size
| Part | Tasks | Estimate |
|---|---|---|
| T0 | 5 | 0.5 day |
| Dashboard | 17 | 4–5 days |
| Engine | 11 | 4–5 days |
| Infra | 5 | 1 day |
| Go live | 4 | 1 day + client time |
| **T1 total** | **42** | **≈ 2 working weeks** |
