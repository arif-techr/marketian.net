# Status

As of: 2026-11-10 (audit of 2026-11-09 in [audits/2026-11-09-audit.md](audits/2026-11-09-audit.md), the tracking design, and a quick look at the repo on 2026-11-10)

**Overall:** Five sites are built: portfolio, accounts, Metadata (shell), WA Broadcaster and **Links**. They run together locally in Docker (see the repo's `STATUS.md`). Nothing has been confirmed as deployed yet. A sixth product, **Tracking** (server-side first-party tracking), has a spec and a build task queue, and you'll start building it yourself.

## Sites

| Site | Folder | State | Tests | Notes |
|---|---|---|---|---|
| marketian.net (+ marketain.net) | `sites/marketian` | ✅ Built, committed | 19 (core 11, mailer 8) | Django portfolio + email sender, htmx, Marketing tools page |
| accounts.marketian.net | `sites/accounts` | ✅ Built, committed | 11 | allauth (GitHub/email) + OpenID Connect provider (django-oauth-toolkit) |
| metadata.marketian.net | `sites/metadata` | ✅ Shell built, committed | 8 | Sign-in, landing page and dashboard work. Product features still to build |
| wa.marketian.net | `sites/wa` | ✅ Built, committed (`5a6d4dd`) | 130 | Django + DRF + Celery + React + WhatsApp gateway, signs in with the Marketian account |
| links.marketian.net | `sites/links` | ✅ Built, committed (`1c1746b`) | 47 | Short links + bio pages. Best template for new products |
| tracking.marketian.net | `sites/tracking` (planned) | 📝 Spec + task queue ([05](05-tracking-product.md), [06](06-tracking-build-spec.md), [07](07-tracking-build-queue.md)) | none | Django dashboard (`web/`) + Node edge/worker (`engine/`) + Redis. Client subdomains via Caddy on-demand TLS |
| Proxy / infra / scripts | `proxy`, `infra`, `scripts` | ✅ Committed | none | Caddy (+ `Caddyfile.local`), shared PostgreSQL, deploy/backup/create-db |

## Repo (seen 2026-11-10)
- Branch `main`, latest commit `9f864d9` "Apps Merged and started to do develop everything". Whether it's pushed wasn't checked.
- Untracked: `Project Planning/04-database-design.md`, and now also docs 05–07 (copied in on 2026-11-10, not committed).
- Repo `STATUS.md` (9 Nov) lists what's left for Links (click-through check, README, adding Links to the portfolio's tools) and pushing + deploying.

## Open issues
| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | `wa-broadcaster/` (old copy) with `.venv` and SQL dumps | High | Not seen in the repo root on 2026-11-10. Confirm it's gone |
| 2 | `sites/wa/backend/db.sqlite3-journal` not ignored | Low | Check (`.gitignore` has no `*.sqlite3-journal` yet) |
| 3 | `sites/wa/package.json` `docker:*` scripts | Low | Check |
| 4 | Django sites default to `DEBUG=True` + placeholder `SECRET_KEY` if `.env` lines are missing (Links too) | Medium | Open |
| 5 | Run all test suites before deploying | Medium | Open |

## Deployment
- VPS: Hostinger **KVM 2** (2 vCPU shared, 8 GB RAM, 100 GB NVMe, 8 TB bandwidth), 1-year term. Ubuntu 24.04, repo at `/opt/sites`. **Not yet confirmed as set up.**
- Estimated memory with all products running: ~4.5–5 GB of 8 GB. CPU is the first limit. Server setup to do: 2–4 GB swap, memory limit on every container, firewall open only on 22/80/443, SSH keys only, Hostinger snapshot before big deploys, off-server backup copies. Check the renewal price before the term ends.
- DNS: `@`, `www`, `*` for marketian.net and `@`, `www` for marketain.net → VPS IP. **Not yet confirmed.** The tracking product will also need `edge.marketian.net` (covered by the wildcard).

## Change log (newest first)
- **2026-11-10:** Copied docs 01–03 (updated) and 05–07 (new) from the Claude Project into this folder, and added them to the folder README. The PC folder and the Project copy now match. Not committed.
- **2026-11-10:** Tracking build task queue written ([07-tracking-build-queue.md](07-tracking-build-queue.md)): 42 tasks in 5 phases with "done when" checks, plus 9 adjustments to the spec after reading the repo (build from `sites/links`, app names `tracker`/`workspaces`, Meta `v26.0`, GA4 rules, local Caddy catch-all). No code written. Status updated for the Links site and newer commits.
- **2026-11-10:** Recorded VPS plan (Hostinger KVM 2) and the capacity estimate.
- **2026-11-10:** Tracking build spec written ([06-tracking-build-spec.md](06-tracking-build-spec.md)). Defaults taken: name "Marketian Tracking", 14-day logs.
- **2026-11-10:** Tracking product designed ([05-tracking-product.md](05-tracking-product.md)): Stape-style, own gateway, agency clients first, same VPS.
- `9f864d9` Apps merged, development continued. `1c1746b` Links (short links + bio pages). `0ad3a18` / `804a654` Portfolio: Marketing tools. `f419726` Whole server runs locally in Docker. `5a6d4dd` WA Broadcaster at wa.marketian.net with Marketian sign-in.
- **2026-11-09:** Database design drafted ([04-database-design.md](04-database-design.md)), a proposal. Full audit; created this Project Planning folder.
- Earlier: `e73d271`, `9813ff9`, `2b94efd`, `182fcc5`, `dd36d2e` (first server: portfolio, accounts, products).
