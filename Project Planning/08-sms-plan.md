# Marketian SMS: plan

As of: 2026-11-17. Status: **approved 2026-11-17, S0 in progress.** Source in `sites/sms` (in the repo, not live).

## What and why
**Marketian SMS** at `sms.marketian.net`: the bulk SMS platform from the `hivesms-lab` repo ("SMSFlow BD", our own code), rebuilt to run like every other Marketian site.

Source: `hivesms-lab-main.zip`, now in `sites/sms` (see S0.1). It is a Next.js 16 panel (33k lines) + a Laravel API (23.5k lines PHP, 246 endpoints, 46 tables, 5.2k lines of tests) + MariaDB. Features: multi-tenant organisations with roles, contacts and groups, suppression and blocklists, templates, sender-ID approval, a Bangla-aware composer (segments and cost), campaigns incl. dynamic per-recipient SMS, scheduling, delivery reports, prepaid wallet with VAT invoices, manual top-ups and payment methods, a REST API with scoped keys, idempotency and signed webhooks, support tickets, and a full operator admin console. SMS goes out through the Automas gateway.

## Decisions (2026-11-17)
| Topic | Decision |
|---|---|
| Name | **Marketian SMS** everywhere (UI, emails, invoices). Marketian colours, font and logo |
| Backend | **Django + Django REST Framework** replaces Laravel. The Next.js panel stays |
| Database | **PostgreSQL** on the shared server (`create-db.sh sms`). No MariaDB |
| Sign-in | **Marketian account from day one** (OpenID Connect, like Links). Personal organisation at first sign-in, invitations by email |
| Gateway | Automas (Bangladesh). Needs the API key and an approved sender ID before go-live |
| Ownership | Our code: free to reuse |

## How it fits the server
```
sites/sms/
├── docker-compose.yml   sms-web, sms-api, sms-worker, sms-beat, sms-redis
├── api/                 Django + DRF (product/, apps per domain), Celery for the queue and schedules
└── web/                 the Next.js panel from hivesms-lab, rebranded, Prisma removed
```
- `sms-web` (Next.js, port 3000) is the only service the proxy reaches: `sms.marketian.net → sms-web:3000`. The panel already forwards `/api/v1` to its backend (today Laravel, then Django) with a shared secret, so customers' servers use `https://sms.marketian.net/api/v1/...`.
- `sms-api` (gunicorn) on `shared-db` + a private network. `sms-worker` / `sms-beat` (Celery) send queued SMS, launch campaigns, poll delivery, retry webhooks and clean up, as WA does. `sms-redis` on an internal network.
- Marketian sign-in callback goes through the panel to `sms-api` (`/accounts/oidc/marketian/...`).
- No published ports, memory limits on each service, `backup.sh` covers the `sms` database (already automatic for the shared server) and uploaded files.
- Estimated memory: ~600–900 MB more. The VPS has ~5.9 GB free (checked 2026-11-17).

## The key rule
**Django answers the same `/api/v1` contract as Laravel**: same paths, JSON shapes, error codes and session behaviour. The contract is documented in the source (`docs/11-laravel-api-reference.md`) and pinned by the Laravel feature tests, which are ported to Django as the acceptance tests. That way the 33k-line panel keeps working with small, known changes (sign-in, branding, removing Prisma), instead of being rewritten.

## Task queue
Legend: ⬜ to do · 🟡 in progress · ✅ done

### S0: preparation (½ day)
| ID | Task | Done when |
|---|---|---|
| ✅ S0.1 | Source into the repo: panel → `sites/sms/web`, Laravel API → `sites/sms/laravel` (reference until Django passes its tests), docs → `sites/sms/docs`. Left out: agent folders, its CI, its MariaDB compose. Not in the root compose; Caddy block commented out | Done 2026-11-17 |
| ⬜ S0.2 | Contract list: every endpoint with method, auth, permission, request and response shape (from the API reference + routes + tests) | `sites/sms/api/docs/contract.md` |
| ⬜ S0.3 | `register_product sms https://sms.marketian.net`, `create-db.sh sms` (local first) | Credentials in `.env` |

### S1: Django foundation (≈ 4 days)
| ID | Task | Done when |
|---|---|---|
| ⬜ S1.1 | Scaffold `sites/sms/api` from `sites/links` conventions: settings with production guard, DRF, Celery, health endpoint, Dockerfile, entrypoint | Starts, `/api/v1/health` answers |
| ⬜ S1.2 | Models for the 46 tables on PostgreSQL (IDs, money as integer poisha, enums, indexes, constraints) | Migrations apply on Postgres 17 |
| ⬜ S1.3 | Sessions + panel cookie contract, Marketian sign-in (OIDC), personal organisation, invitations | Sign-in from the panel works |
| ⬜ S1.4 | Organisations, members, roles, permissions (RBAC), audit log, settings (encrypted), rate limits, idempotency keys | Ported tests pass |

### S2: sending (≈ 7 days)
| ID | Task | Done when |
|---|---|---|
| ⬜ S2.1 | Phone normalisation, GSM-7 / Unicode segmentation, pricing | Ported unit tests pass |
| ⬜ S2.2 | Contacts, groups, CSV import, suppression, blocklist, consent | Ported tests pass |
| ⬜ S2.3 | Templates, sender IDs + approval, sender catalog | Ported tests pass |
| ⬜ S2.4 | Wallet, billing (reserve, charge, refund), low-balance alerts | Ported tests pass, balances never go negative under concurrency (row locks) |
| ⬜ S2.5 | Send API + messages, dispatcher queue, Automas and mock providers, delivery reports and polling, inbound webhooks | A mock send is delivered end to end |
| ⬜ S2.6 | Campaigns incl. dynamic SMS (CSV with per-recipient fields), scheduling, runner, quiet hours, review | Ported campaign tests pass |
| ⬜ S2.7 | API keys (scopes, one-time display, pepper), outbound webhooks (signed, retries), API logs | Ported tests pass |
| ⬜ S2.8 | Reports and customer dashboard numbers (Postgres versions of the MySQL-only queries) | Numbers match the seeded test data |

### S3: money and account (≈ 4 days)
| ID | Task | Done when |
|---|---|---|
| ⬜ S3.1 | Payments, payment methods, manual top-up requests and approval, invoices with VAT | Ported tests pass |
| ⬜ S3.2 | Team, profile, notifications and preferences, support tickets, email (via the Marketian mailbox) | Ported tests pass |

### S4: admin console (≈ 4 days)
| ID | Task | Done when |
|---|---|---|
| ⬜ S4.1 | Customers, users, staff, sender catalog, pricing plans and credit packages, settings, readiness | Ported tests pass |
| ⬜ S4.2 | Finance, costs, usage, campaigns/messages review, abuse reports, API and audit logs, platform dashboard | Ported tests pass |

### S5: panel (≈ 3 days)
| ID | Task | Done when |
|---|---|---|
| ⬜ S5.1 | Point the panel at Django, remove Prisma and the MySQL connection | `npm run build` with no database |
| ⬜ S5.2 | Sign-in pages → "Continue with Marketian account"; remove password, Google and phone sign-in screens | Sign-in round trip works |
| ⬜ S5.3 | Rebrand to Marketian SMS: colour tokens, font, logo, names in pages, emails and invoices, contact details | No "SMSFlow" left |
| ⬜ S5.4 | Unit tests + Playwright journeys against Django | All green |

### S6: go live (≈ 2 days)
| ID | Task | Done when |
|---|---|---|
| ⬜ S6.1 | `sites/sms/docker-compose.yml`, root include, Caddy blocks (`Caddyfile` + `.local`), `.env.example`s, README section, backups | Whole stack runs locally |
| ⬜ S6.2 | Deploy, Automas key + sender ID, real test SMS to our own number, Tools entry on marketian.net | First real SMS delivered |

**Total: ≈ 4–5 weeks of focused work.**

## Needed from you before go-live
- Mailbox password fixed on the server (sign-up emails, receipts): see 02-status.
- Automas account: API key, approved sender ID (masking or non-masking), its per-SMS cost.
- Real prices, VAT number, company and contact details for invoices and legal pages; legal pages reviewed.

## Risks
- **Contract drift:** a Django answer that differs slightly from Laravel breaks a panel screen. Mitigation: ported tests + Playwright journeys before go-live.
- **Money logic:** wallet, billing and refunds must match to the poisha. Mitigation: port every billing test first; row locks on wallet updates.
- **Automas adapter is unverified** in the source. Mitigation: test with real SMS to our own numbers before opening sign-ups.
