# Tracking: build spec

As of: 2026-11-10. Status: **ready to build** (T1 starts 2026-11-11).
Product overview and reasoning: [05-tracking-product.md](05-tracking-product.md). This doc is the technical source of truth. Where the two differ, this one wins.

Defaults taken for the open questions in 05 §8 (change any time):
- Display name **"Marketian Tracking"**, slug `tracking`.
- Raw event logs kept **14 days** (`EVENT_RETENTION_DAYS`).
- The first client's platform is still unknown, so T1 ships a generic snippet plus a server-events `curl` example.

---

## 1. Repository layout

```
sites/tracking/
├── docker-compose.yml          # included by the root compose
├── .env.example
├── README.md                   # run locally, deploy, add a client
├── web/                        # Django dashboard: tracking.marketian.net
│   ├── Dockerfile
│   ├── manage.py
│   ├── requirements.txt
│   ├── config/                 # settings/, urls.py, wsgi.py
│   ├── apps/
│   │   ├── core/               # Workspace, WorkspaceMember, AuditLog, tenancy mixin, Marketian sign-in adapter
│   │   ├── sites/              # Site, Domain, ApiKey, DNS verify, snippet builder
│   │   ├── destinations/       # Destination, adapters' form schemas, "send test event"
│   │   ├── events/             # EventLog, Delivery, DailyStat (read side), live log, stats
│   │   ├── internal/           # caddy-ask, config publisher (→ Redis)
│   │   └── common/             # crypto.py (AES-GCM), redis.py, phones.py, utils
│   ├── templates/  static/
│   └── tests/
└── engine/                     # Node 20 + TypeScript: edge + worker (one image, two commands)
    ├── Dockerfile
    ├── package.json  tsconfig.json  vitest.config.ts
    ├── loader/                 # mt.js source → esbuild → dist/mt.min.js (budget ≤ 4 KB gzip)
    │   └── src/index.ts
    ├── src/
    │   ├── shared/             # event schema (zod), types, redis keys, crypto, hashing, logger (pino)
    │   ├── edge/
    │   │   ├── server.ts       # Fastify app
    │   │   ├── routes/         # loader.ts, collect.ts, server-events.ts, verify.ts, health.ts
    │   │   └── lib/            # config-cache.ts, cookies.ts, enrich.ts, geo.ts, bot.ts,
    │   │                       # consent.ts, ratelimit.ts, cors.ts, ids.ts (UUIDv7)
    │   └── worker/
    │       ├── index.ts        # starts ingest consumer, delivery workers, maintenance jobs
    │       ├── ingest.ts       # Redis stream → Postgres batch insert → delivery jobs
    │       ├── deliver.ts      # BullMQ processor, retries, result recording
    │       ├── maintenance.ts  # partitions, retention, stats flush, domain re-check
    │       ├── db.ts           # pg pool, prepared statements
    │       └── adapters/
    │           ├── adapter.ts  # Destination interface
    │           ├── mapping.ts  # standard event → platform event table
    │           ├── meta.ts  ga4.ts  tiktok.ts  webhook.ts
    │           └── index.ts    # registry
    └── test/
```

**Ownership rule:** Django migrations own **every** table. The engine only reads config from Redis, and writes `event_log`, `delivery` and `daily_stat` with plain SQL. The engine never runs migrations.

---

## 2. Services and networks

| Service | Image / command | Port (internal) | Networks | Memory limit |
|---|---|---|---|---|
| `tracking-web` | `web/` → gunicorn, 2 workers | 8000 | `web-proxy`, `shared-db`, `tracking-private` | 256 MB |
| `tracking-edge` | `engine/` → `node dist/edge/server.js` | 8080 | `web-proxy`, `tracking-private` | 192 MB |
| `tracking-worker` | `engine/` → `node dist/worker/index.js` | none | `shared-db`, `tracking-private` | 256 MB |
| `tracking-redis` | `redis:7-alpine`, AOF on, `maxmemory 256mb`, `noeviction` | 6379 | `tracking-private` (internal) | 300 MB |

The database is the shared Postgres, with database `tracking` and role `tracking` (`scripts/create-db.sh tracking`).

### Caddy (`proxy/Caddyfile`) additions
```caddy
{
    on_demand_tls {
        ask http://tracking-web:8000/internal/caddy-ask
    }
}

tracking.marketian.net {
    @internal path /internal/*
    respond @internal 404
    reverse_proxy tracking-web:8000
}

edge.marketian.net {
    reverse_proxy tracking-edge:8080
}

# Every verified client host (subdomain or same-origin forwarder).
https:// {
    tls { on_demand }
    request_body { max_size 64KB }
    reverse_proxy tracking-edge:8080 {
        header_up X-Real-IP {remote_host}
    }
}
```
Specific site blocks always win over the catch-all, so the existing sites are unaffected.

---

## 3. Database (`tracking`)

Conventions are those in [04-database-design.md](04-database-design.md) §5: `bigint` IDs, `timestamptz` in UTC, `created_at`/`updated_at`, constraint names `unique_<what>_per_<scope>`. Every business row hangs off `workspace_id`, and every query goes through the tenancy mixin.

### 3.1 Tenancy (`core`)

**`core_workspace`**
| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| marketian_org_id | uuid NULL UNIQUE | Filled once accounts issues the `orgs` claim (04 Phase 2). Until then, each user gets a personal workspace at first sign-in |
| name | varchar(120) | |
| slug | varchar(60) UNIQUE | |
| status | varchar(12) | `active` / `suspended` |
| limits | jsonb | `{"sites": 10, "events_per_month": 1000000}`. Copied from the plan later; manual for now |
| created_at, updated_at | timestamptz | |

**`core_workspacemember`**: id, workspace_id FK CASCADE, user_id FK CASCADE, role (`owner`/`admin`/`member`/`viewer`), created_at. `UNIQUE(workspace_id, user_id)` = `unique_member_per_workspace`.

| Role | Can |
|---|---|
| owner | everything, including deleting the workspace and managing members |
| admin | sites, domains, destinations, API keys |
| member | view everything, send test events |
| viewer | view stats and logs only |

**`core_auditlog`** (append-only): id bigserial, workspace_id, actor_id NULL (SET_NULL), action varchar(60) (`destination.create`, `destination.secret_update`, `apikey.create`, `domain.verify`, `site.delete`…), target_type, target_id, details jsonb (never secrets), ip inet, created_at. Index `(workspace_id, created_at DESC)`.

### 3.2 Configuration (`sites`, `destinations`)

**`sites_site`**
| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| workspace_id | FK CASCADE | |
| name | varchar(120) | |
| primary_domain | varchar(253) | `shop.com`, lower-case, no scheme. Used for the cookie domain and CORS |
| public_key | varchar(24) UNIQUE | `mt_pk_` + 18 random base62 chars, shown in the snippet |
| path_prefix | varchar(8) UNIQUE | random `[a-z0-9]{4,6}`. Never a word on block lists |
| loader_name | varchar(12) | random file name, e.g. `q8r.js` |
| timezone | varchar(40) | default `Asia/Dhaka`, for daily stats |
| default_currency | char(3) | `BDT` |
| consent_mode | varchar(12) | `off` (treat as granted) / `basic` (wait for signal) / `advanced` (GA4 cookieless pings) |
| bot_filter | bool | default true |
| cookie_keeper | bool | default true |
| status | varchar(10) | `active` / `paused` (paused: edge accepts and drops) |
| config_version | int | +1 on every change to the site or its children. Edge cache key |
| created_by | FK user SET_NULL | |
| created_at, updated_at | timestamptz | |

`UNIQUE(workspace_id, name)`.

**`sites_domain`**
| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| site_id | FK CASCADE | |
| hostname | varchar(253) UNIQUE | `data.shop.com` (subdomain) or `shop.com` (same-origin) |
| mode | varchar(12) | `subdomain` / `same_origin` |
| status | varchar(10) | `pending` / `verified` / `failing` / `disabled` |
| verify_token | varchar(32) | same-origin check: `GET https://shop.com/<prefix>/_v` must return it |
| dns_seen | jsonb | last lookup: `{"cname": "...", "a": ["..."]}` |
| verified_at, last_checked_at | timestamptz NULL | |
| fail_count | smallint | 3 failed daily checks → `failing` and an e-mail |
| created_at | timestamptz | |

`hostname` must equal the site's `primary_domain` or end with `.` + `primary_domain`. This is checked in the model's `clean()` and the form, because a database CHECK constraint can't look at another table.

**`sites_apikey`** (for server events)
| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| site_id | FK CASCADE | |
| name | varchar(60) | "WooCommerce", "Backend" |
| prefix | varchar(12) | `mtk_ab12cd` (shown) |
| key_hash | char(64) | SHA-256 of the full key. The key is shown once |
| last_used_at, revoked_at | timestamptz NULL | |
| created_by | FK SET_NULL | |
| created_at | timestamptz | |

Index on `prefix`. The key format is `mtk_<6>_<32 base62>`.

**`destinations_destination`**
| Column | Type | Notes |
|---|---|---|
| id | bigserial PK | |
| site_id | FK CASCADE | |
| type | varchar(20) | `meta`, `ga4`, `tiktok`, `webhook` (later: `snapchat`, `pinterest`, `linkedin`) |
| label | varchar(60) | "Main pixel" |
| config | jsonb | non-secret settings, validated per type (see §6) |
| secret_enc | text NULL | AES-256-GCM, format `v1:<key_id>:<base64(nonce‖ciphertext‖tag)>` |
| secret_hint | varchar(8) | last 4 chars, for display |
| event_map | jsonb | `{"Purchase": "Purchase", "PageView": null}`. `null` = don't send. Missing keys use the adapter's defaults |
| consent_required | jsonb | defaults per type, e.g. Meta `["ad_storage","ad_user_data"]` |
| send_pii | bool | default true. Hashed user data sent only if true |
| enabled | bool | |
| health | varchar(8) | `ok` / `warn` / `error`, updated by the worker from the last 100 deliveries |
| last_error | text NULL | |
| last_success_at | timestamptz NULL | |
| created_at, updated_at | timestamptz | |

`UNIQUE(site_id, type, label)`.

### 3.3 Event data (`events`): high volume

**`events_eventlog`**: **native Postgres partitioned table, `PARTITION BY RANGE (received_at)`, one partition per day.** It's created by a `RunSQL` migration. The Django model is `managed = False`, read-only.

| Column | Type | Notes |
|---|---|---|
| id | uuid | UUIDv7 made by the edge (time-ordered) |
| received_at | timestamptz | partition key |
| site_id | bigint | no FK (partitioned tables + volume), checked by the app |
| event_name | varchar(60) | standard or custom name |
| event_id | varchar(64) | from the browser/client, for dedup with the pixel |
| source | varchar(6) | `web` / `server` |
| page_url | text NULL | query string kept, `email=` style params stripped |
| visitor_id | varchar(40) NULL | `_mt_id` |
| ip_trunc | inet NULL | IPv4 last octet → 0, IPv6 → /48 |
| country | char(2) NULL | |
| user_agent | text NULL | |
| is_bot | bool | |
| consent | jsonb | `{"ad_storage":"granted",…}` |
| user_hashed | jsonb | `{"em":"<sha256>","ph":"<sha256>",…}`. **Never raw** |
| data | jsonb | value, currency, items, order_id, custom params |
| click_ids | jsonb | fbclid/fbc, gclid, ttclid, utm_* |

`PRIMARY KEY (id, received_at)`. Indexes per partition: `(site_id, received_at DESC)`, `(site_id, event_name, received_at DESC)`, `(site_id, event_id)`.

**`events_delivery`**: also partitioned by `received_at` (copied from the event), daily.
| Column | Type | Notes |
|---|---|---|
| id | bigint identity | |
| received_at | timestamptz | partition key |
| event_uuid | uuid | → eventlog.id (no FK) |
| site_id | bigint | |
| destination_id | bigint | |
| status | varchar(8) | `queued` / `sent` / `failed` / `skipped` / `retrying` |
| skip_reason | varchar(30) NULL | `not_mapped`, `no_consent`, `bot`, `disabled`, `duplicate` |
| http_status | smallint NULL | |
| attempts | smallint | |
| response | text NULL | trimmed to 2 KB, tokens masked |
| sent_at | timestamptz NULL | |

`PRIMARY KEY (id, received_at)`. Indexes: `(event_uuid)`, `(destination_id, status, received_at DESC)`.

**`events_dailystat`** (normal table, kept forever)
| Column | Type |
|---|---|
| site_id | bigint |
| day | date (in the site's timezone) |
| destination_id | bigint (0 = received at edge) |
| event_name | varchar(60) |
| received, sent, failed, skipped, bots | int |

`PRIMARY KEY (site_id, day, destination_id, event_name)`. The worker writes it with `INSERT … ON CONFLICT DO UPDATE SET x = x + EXCLUDED.x`.

### 3.4 Partition maintenance (worker job, hourly)
- Make sure partitions exist for **today + 3 days ahead** (`events_eventlog_p20261111` …).
- Drop partitions older than `EVENT_RETENTION_DAYS` (dropping is instant and makes no bloat).
- A `DEFAULT` partition catches anything with a strange clock. It's alerted on if it isn't empty.

**Local development** uses Docker Postgres (not SQLite) for this product, because partitioning is Postgres-only. `docker compose -f sites/tracking/docker-compose.dev.yml up db redis`.

---

## 4. Redis layout

| Key | Type | Written by | Purpose |
|---|---|---|---|
| `cfg:host:{hostname}` | string → site_id | web | edge finds the site by Host header |
| `cfg:site:{id}` | string (JSON) | web | compact site config: prefix, loader, domains, consent, destinations **with decrypted secrets removed** (the worker fetches secrets separately) |
| `cfg:dest:{id}` | string (encrypted JSON) | web | destination config + secret, still AES-encrypted. Only the worker decrypts |
| `cfg:changed` | pub/sub channel | web | message = site_id. The edge/worker drop that entry from their in-memory cache (TTL 60 s anyway) |
| `ev:in` | stream (`MAXLEN ~ 1,000,000`) | edge | raw enriched events. Consumer group `ingest` |
| `bull:deliver:*` | BullMQ | worker | one job per (event, destination) |
| `live:{site_id}` | list (LTRIM 200) | worker | dashboard live log (summary + delivery states) |
| `stat:{site}:{day}` | hash | edge/worker | counters `{dest}:{event}:{field}`, flushed to `events_dailystat` every 60 s |
| `rl:ip:{ip}` / `rl:site:{id}` | string + EXPIRE 60 | edge | rate limits: 120/min per IP, `limits.rps × 60` per site |
| `dedup:{site}:{event_id}` | string, EX 48 h | worker | stops the same server/web event being sent twice |

Config publishing is a Django `post_save`/`post_delete` signal → `apps.internal.publish.publish_site(site_id)` (inside `transaction.on_commit`). There's also a `manage.py publish_all` for deploys and recovery. **Collection works even if Postgres is down**, because the edge only needs Redis.

---

## 5. HTTP interfaces

### 5.1 Edge (on every client host). `{p}` = the site's `path_prefix`

| Method & path | Auth | Does |
|---|---|---|
| `GET /{p}/{loader_name}` | none | Serves `mt.js` with the site config inlined. `Cache-Control: public, max-age=3600`, ETag = config_version |
| `POST /{p}/e` | site public key in the body + allowed Origin | Web events, batch of up to 20. Answers **204** + `Set-Cookie`. `text/plain` body (no CORS preflight) |
| `GET /{p}/e.gif?…` | same | `<noscript>` and email-open fallback, one event, 1×1 gif |
| `POST /{p}/s` | `Authorization: Bearer mtk_…` | Server events (orders, refunds, leads), batch of up to 100. Answers `202 {"accepted": n, "rejected": [...]}` |
| `GET /{p}/_v` | none | Same-origin verification: returns the domain's `verify_token` |
| `GET /{p}/c` | none | Cookie keeper: refreshes `_mt_id`, `_fbp`, `_fbc`, `_ga` server-side (T2) |
| `GET /healthz` | none | `{"ok":true}` + Redis ping |

Unknown host → `404`. Paused site → `204` and drop. Body > 64 KB → `413`. Rate limited → `429`.

**CORS:** `Access-Control-Allow-Origin` echoes the Origin only if it's `https://` + `primary_domain` or one of its subdomains. `Allow-Credentials: true`.

**Cookies set by the edge** (on `Domain=.{primary_domain}`, `Secure`, `SameSite=Lax`, `Path=/`):
| Cookie | HttpOnly | Max-Age | Value |
|---|---|---|---|
| `_mt_id` | yes | 400 d | `v1.<UUIDv7>` visitor ID |
| `_fbc` | no | 90 d | `fb.1.<ms>.<fbclid>` when `fbclid` is in the URL |
| `_fbp` | no | 90 d | re-set with the same value (kept alive) |
| `_ga` | no | 400 d | re-set with the same value if present (T2, cookie keeper) |

### 5.2 Incoming event format (v1)
```json
{
  "v": 1,
  "k": "mt_pk_8Hk2…",
  "events": [{
    "name": "Purchase",
    "id": "a3f1c9e0-…",
    "ts": 1762790400000,
    "url": "https://shop.com/checkout/thank-you",
    "ref": "https://www.google.com/",
    "title": "Thank you",
    "user": { "em": "x@y.com", "ph": "8801711000000", "fn": "Arif", "ln": "Rahman",
              "ct": "dhaka", "zp": "1207", "country": "bd", "external_id": "cust_991" },
    "data": { "value": 2450, "currency": "BDT", "order_id": "10024",
              "items": [{ "id": "SKU1", "name": "T-shirt", "price": 1225, "qty": 2, "category": "Apparel" }],
              "custom": { "coupon": "WINTER" } },
    "consent": { "ad_storage": "granted", "analytics_storage": "granted",
                 "ad_user_data": "granted", "ad_personalization": "denied" }
  }]
}
```
- The edge adds: `received_at`, IP, UA, country, `visitor_id`, `fbc`/`fbp`/`ga_client_id` from cookies, click IDs from `url`, and `is_bot`.
- `user` values can arrive raw (hashed by the worker, never stored raw) or already SHA-256 hex (passed through).
- Server events use the same shape. For server events, `ts` may be up to 7 days old; Meta rejects anything older.
- Validated with zod. A bad event is rejected alone, not the whole batch.

**Standard event names:** `PageView, ViewContent, Search, AddToCart, AddToWishlist, InitiateCheckout, AddPaymentInfo, Purchase, Refund, Lead, CompleteRegistration, Contact, Subscribe, StartTrial`. Any other name is a custom event (sent to destinations only if mapped).

### 5.3 Loader API (`mt.js`)
```html
<script async src="https://data.shop.com/k7q2/q8r.js"></script>
<script>
  window.mt = window.mt || function(){(mt.q = mt.q || []).push(arguments)};
  mt('consent', { ad_storage: 'granted', analytics_storage: 'granted' }); // optional
  mt('track', 'PageView');
</script>
```
- `mt('track', name, data?, user?)` returns the `event_id`, which the snippet passes to `fbq('track', name, data, {eventID})` and to `ttq` for dedup.
- `mt('identify', {em, ph, external_id})` remembers user data in memory for later events on the page (never in localStorage).
- `mt('consent', {...})`: if `consent_mode = basic`, events queue until the first consent call.
- Auto: PageView on load (setting), SPA history changes (setting), click-ID capture.
- Sends with `navigator.sendBeacon`, falling back to `fetch(…, {keepalive: true})`.

### 5.4 Dashboard routes (`tracking.marketian.net`)
```
/                                   landing (signed out) / workspace home (signed in)
/sites/                             list + health
/sites/new/
/sites/<id>/                        overview: today's numbers, destination health
/sites/<id>/setup/                  domains (add, DNS instructions, verify), install snippets
/sites/<id>/destinations/           list, add (by type), edit, mapping, test
/sites/<id>/logs/                   live log (htmx poll 3 s) + search last 14 days
/sites/<id>/logs/<uuid>/            one event + deliveries
/sites/<id>/keys/                   server API keys
/sites/<id>/settings/               consent, bot filter, cookie keeper, pause, delete
/workspace/members/                 members and roles
/workspace/audit/                   audit log
/internal/caddy-ask                 (blocked publicly by Caddy)
/internal/healthz
```

---

## 6. Destination adapters (worker)

```ts
interface DestinationAdapter<C, S> {
  type: 'meta' | 'ga4' | 'tiktok' | 'webhook';
  configSchema: ZodType<C>;           // also drives the Django form (exported as JSON schema)
  secretSchema: ZodType<S>;
  defaultEventMap: Record<StdEvent, string | null>;
  defaultConsent: ConsentKey[];
  build(ev: EnrichedEvent, c: C, s: S): OutboundRequest | null; // null = skip
  classify(res: HttpResult): { ok: boolean; retry: boolean; message?: string };
  test(c: C, s: S): Promise<TestResult>;  // "Send test event" button
}
```

| Type | Config (`config`) | Secret | Endpoint | Notes |
|---|---|---|---|---|
| `meta` | `pixel_id`, `test_event_code?`, `graph_version` (setting, default from env `META_GRAPH_VERSION`) | `access_token` | `POST graph.facebook.com/{ver}/{pixel_id}/events` | `action_source` `website`/`system_generated`; `fbc`, `fbp`, IP, UA, hashed `user_data`; `event_id` for dedup |
| `ga4` | `measurement_id` | `api_secret` | `POST www.google-analytics.com/mp/collect` | `client_id` from `_ga` or derived from `_mt_id`; always answers 2xx, so `test()` uses `/debug/mp/collect` |
| `tiktok` | `pixel_code`, `test_event_code?` | `access_token` | `POST business-api.tiktok.com/open_api/v1.3/event/track/` | `ttclid`, `_ttp`, hashed email/phone |
| `webhook` | `url`, `events[]` | `signing_secret` | `POST <url>` | body = our event JSON, header `X-MT-Signature: sha256=<hmac>` |

**Default mapping (excerpt)**
| Ours | Meta | GA4 | TikTok |
|---|---|---|---|
| PageView | PageView | page_view | Pageview |
| ViewContent | ViewContent | view_item | ViewContent |
| AddToCart | AddToCart | add_to_cart | AddToCart |
| InitiateCheckout | InitiateCheckout | begin_checkout | InitiateCheckout |
| AddPaymentInfo | AddPaymentInfo | add_payment_info | AddPaymentInfo |
| Purchase | Purchase | purchase | CompletePayment |
| Refund | (none) | refund | (none) |
| Lead | Lead | generate_lead | SubmitForm |
| CompleteRegistration | CompleteRegistration | sign_up | CompleteRegistration |
| Search | Search | search | Search |

**Retry policy:** network error, 429 or 5xx → retry with exponential backoff (30 s, 2 m, 10 m, 30 m, 2 h), then `failed`. Other 4xx → `failed` at once, the message is saved, and destination `health` updates. 20 consecutive failures → health `error` + an e-mail to workspace admins (at most once an hour).

**PII normalisation before hashing:** email trimmed + lower-cased. Phone digits only, international, with the BD default country code `880` if 11 local digits (same rules as `sites/wa` `phones.py`, ported). Names lower-case, no punctuation. City lower-case, no spaces. Country ISO-2 lower-case. Zip as given, lower-case. Then SHA-256 hex.

---

## 7. Configuration (`.env.example`)
```
# web
DJANGO_SECRET_KEY=
DEBUG=False
ALLOWED_HOSTS=tracking.marketian.net
DATABASE_URL=postgres://tracking:***@postgres:5432/tracking
REDIS_URL=redis://tracking-redis:6379/0
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
MARKETIAN_ACCOUNTS_URL=https://accounts.marketian.net
EDGE_CNAME_TARGET=edge.marketian.net
EDGE_PUBLIC_IP=
EMAIL_URL=

# shared by web + engine
TRACKING_ENC_KEYS=k1:<base64 32 bytes>        # comma list; first = active, others decrypt-only (rotation)
EVENT_RETENTION_DAYS=14

# engine
PG_URL=postgres://tracking:***@postgres:5432/tracking
META_GRAPH_VERSION=
GEOIP_DB=/data/GeoLite2-Country.mmdb
EDGE_RATE_PER_IP=120
LOG_LEVEL=info
```
In production the web app **refuses to start** if `DJANGO_SECRET_KEY` or `TRACKING_ENC_KEYS` is missing or a placeholder (fixes audit issue 4 for this site from day one).

---

## 8. Security checklist
- [ ] Caddy `ask` allows only `verified` hostnames. `/internal/*` isn't reachable from the internet.
- [ ] Destination secrets: AES-256-GCM at rest. Write-only in the UI (only the hint is shown). Never in logs, `live:*`, audit details or error messages.
- [ ] API keys stored only as SHA-256. Shown once. Revocable.
- [ ] Raw email/phone never stored. IP truncated before storing.
- [ ] zod validation on every incoming event. 64 KB body limit. Batch limits. Rate limits per IP and per site.
- [ ] CORS only for the site's own domain family. No `*`.
- [ ] Tenancy: every Django queryset goes through `WorkspaceScopedMixin`. Tests prove that user A can't read site B (404, not 403).
- [ ] Role checks on every write view. Destructive actions need a confirm step and are audited.
- [ ] Engine runs as non-root, read-only file system, no published ports.
- [ ] Dependency audit (`pip-audit`, `npm audit`) in the test script.
- [ ] Privacy page + DPA template for clients (the client collects consent; we process on their behalf).

---

## 9. Observability
- JSON logs (pino in the engine, structlog-style in Django) with `site_id` and `event_uuid`, never PII.
- `/healthz` on web and edge, for uptime checks.
- The dashboard shows per-destination health and the last error. An internal `/internal/metrics` page (staff only) shows queue depth, stream lag and partition sizes.

---

## 10. Tests (minimum for T1)
| Area | Tool | Must cover |
|---|---|---|
| Django | pytest-django | sign-in creates workspace; tenancy isolation; domain add/verify (DNS mocked); caddy-ask yes/no; secret encrypt/decrypt round-trip with the Node format; config published to Redis |
| Edge | vitest + Fastify inject | unknown host 404; CORS; cookies set; bad event rejected alone; rate limit; paused site |
| Worker | vitest + nock | Meta/GA4/TikTok request bodies match fixtures; hashing/normalising; retry vs. final failure; dedup; partition maintenance SQL |
| Loader | vitest + happy-dom | queue before load; event_id returned; sendBeacon fallback; size budget |
| End to end | `scripts/tracking-smoke.sh` | real stack in Docker: load loader → send Purchase → delivery row `sent` against a mock server |

---

## 11. Build order (T1) — tomorrow's checklist
1. `register_product tracking` in accounts (local), and `create-db.sh tracking`.
2. Copy `sites/metadata` → `sites/tracking/web`, rename, keep the Marketian sign-in. Add `docker-compose.dev.yml` (Postgres + Redis).
3. Models + migrations: `core`, `sites`, `destinations`, `events` (`RunSQL` partitions). Tenancy mixin. Tests.
4. `common/crypto.py` (AES-GCM `v1:` format) and the config publisher to Redis. Tests.
5. Dashboard pages: sites, setup (domain + verify + snippet), destinations (Meta, GA4), keys, settings.
6. `internal/caddy-ask` + Caddyfile changes.
7. `engine/` scaffold: TypeScript, Fastify, zod schema, shared crypto (Node side of the same format) + cross-language test vector.
8. Edge routes: loader, collect, server events, verify, health. Cookies, enrich (UA, GeoLite2), bot flag, rate limit.
9. `loader/` → `mt.js` with esbuild, size budget.
10. Worker: ingest (stream → batch insert), deliver (BullMQ), adapters Meta + GA4, maintenance (partitions, retention, stats flush).
11. Live log + daily stats on the dashboard.
12. Root compose + Caddy + `backup.sh` (exclude `events_eventlog*` / `events_delivery*`).
13. Run all tests + smoke script. Update README, [02-status.md](02-status.md).

T1 is done when a real client site sends Purchase through its own subdomain, Meta Events Manager shows it **deduplicated** with the browser pixel, and GA4 Realtime shows it.
