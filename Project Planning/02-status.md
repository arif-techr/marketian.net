# Status

As of: 2026-11-16 (full check of repo and tests; audit of 2026-11-09 in [audits/2026-11-09-audit.md](audits/2026-11-09-audit.md), the tracking design, and a quick look at the repo on 2026-11-10)

**Overall:** Five sites are built and pushed: portfolio, accounts, Metadata (shell), WA Broadcaster and **Links**. All 321 tests pass. Nothing is deployed yet. The sixth product, **Tracking**, is being built on branch `tracking` (dashboard back end W1–W10 done, uncommitted). The local `.env` files are missing (see Repo).

## Sites

| Site | Folder | State | Tests | Notes |
|---|---|---|---|---|
| marketian.net (+ marketain.net) | `sites/marketian` | ✅ Built, committed | 19 (core 11, mailer 8) | Django portfolio + email sender, htmx, Marketing tools page |
| accounts.marketian.net | `sites/accounts` | ✅ Built, committed | 11 | allauth (GitHub/email) + OpenID Connect provider (django-oauth-toolkit) |
| metadata.marketian.net | `sites/metadata` | ✅ Shell built, committed | 8 | Sign-in, landing page and dashboard work. Product features still to build |
| wa.marketian.net | `sites/wa` | ✅ Built, committed (`5a6d4dd`) | 130 | Django + DRF + Celery + React + WhatsApp gateway, signs in with the Marketian account |
| links.marketian.net | `sites/links` | ✅ Built, committed (`1c1746b`) | 47 | Short links + bio pages. Best template for new products |
| tracking.marketian.net | `sites/tracking` | 🟡 Building on branch `tracking`: dashboard tasks W1–W10 done ([07](07-tracking-build-queue.md)) | 70 | Django dashboard (`web/`) + Node edge/worker (`engine/`) + Redis. Client subdomains via Caddy on-demand TLS |
| Proxy / infra / scripts | `proxy`, `infra`, `scripts` | ✅ Committed | none | Caddy (+ `Caddyfile.local`), shared PostgreSQL, deploy/backup/create-db |

## Repo (checked 2026-11-16)
- 2026-11-16: everything merged into `main`: the portfolio Postgres fix, Tracking W1–W10 (from branch `tracking`), and the 9 Nov evening session that had been left in a git stash (issues 2–4 fixes, README section for Links). Push `main` so the server can pull it.
- Untracked `marketian.net/` folder in the repo root: a second clone at `0573c00`. Delete it or move it out.
- No `.env` file exists in this folder (only `sites/accounts/keys/` and old SQLite files). `docker compose up` needs `infra/.env` and each site's `.env` again, so the logins in `STATUS.md` won't work until they're recreated.

## Tests (run 2026-11-16, all green)
| Suite | Tests |
|---|---|
| marketian | 22 ✅ |
| accounts | 11 ✅ |
| metadata | 8 ✅ |
| links | 47 ✅ |
| wa (pytest, `DJANGO_DEBUG=true`, `sites/wa/backend/.venv`) | 163 ✅ |
| tracking/web (SQLite; also PostgreSQL 17 on 2026-11-10) | 70 ✅ |
| **Total** | **321** |

## Open issues
| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | `wa-broadcaster/` (old copy) with `.venv` and SQL dumps | High | ✅ Gone from the repo root |
| 2 | `*.sqlite3-journal` not ignored | Low | ✅ Fixed (in `main`) |
| 3 | `sites/wa/package.json` `docker:*` scripts | Low | ✅ Fixed (in `main`) |
| 4 | Django sites start with `DEBUG=False` and the placeholder `SECRET_KEY` | Medium | ✅ Fixed (in `main`; Tracking has its own guard) |
| 5 | Run all test suites before deploying | Medium | ✅ 321 pass (2026-11-16) |
| 6 | Links not clicked through in the browser in Docker | Medium | Open. Needs the `.env` files and Docker Desktop |
| 7 | Links missing from the portfolio's Marketing tools on the local install | Low | Open |
| 8 | Local `.env` files missing | Medium | Open. Recreate from each `.env.example` |
| 9 | Metadata: product not decided (empty dashboard) | — | Open |
| 10 | Portfolio fell back to SQLite in Docker if `POSTGRES_DB` was left commented out in its `.env` | Medium | ✅ Fixed 2026-11-16 (`sites/marketian/docker-compose.yml` always sets it; `.env.example` uncommented) |
| 11 | No memory limits on any container | Low | Open (planned in Deployment below) |
| 12 | With the optional WA `evolution` profile, its database and `wa-evolution-instances` volume aren't in `backup.sh` | Low | Open. The default `builtin` gateway is covered |

## Deployment
- **Live since 2026-11-16** on the Hostinger VPS `srv2097136` (201.18.200.226), repo at `/opt/sites` on `b51bc02`. All 14 containers run. DNS for every name points at the VPS (records at Namecheap).
- 2026-11-17: HTTPS fixed. The deploy had started the proxy with a temporary `proxy/Caddyfile.preview` (`tls internal`, hidden through `.git/info/exclude`), so browsers got untrusted "Caddy Local Authority" certificates. The proxy now runs the real `proxy/Caddyfile`; Let's Encrypt certificates for all 8 names. The preview file and its exclude entry are deleted. Never start the proxy with `CADDYFILE=` set on the server.
- 2026-11-17: the live portfolio database was empty. Added the 3 Marketing tools and 6 services from `seed_demo`. Still empty: profile (name, bio, photo), projects, skills, experience, testimonials: fill in at https://marketian.net/admin/.
- Deploy access from the PC: `ssh -i ~/.ssh/marketian_vps root@201.18.200.226`.
- VPS: Hostinger **KVM 2** (2 vCPU shared, 8 GB RAM, 100 GB NVMe, 8 TB bandwidth), 1-year term. Ubuntu 24.04, repo at `/opt/sites`. **Not yet confirmed as set up.**
- Estimated memory with all products running: ~4.5–5 GB of 8 GB. CPU is the first limit. Server setup to do: 2–4 GB swap, memory limit on every container, firewall open only on 22/80/443, SSH keys only, Hostinger snapshot before big deploys, off-server backup copies. Check the renewal price before the term ends.
- DNS (checked 2026-11-16): **both domains' DNS is at Namecheap**, not Hostinger. marketian.net uses Namecheap hosting nameservers and currently serves the old site from Namecheap hosting (LiteSpeed, 162.0.232.25). marketain.net uses Namecheap's default DNS (parking page). No subdomain records exist yet. To go live: in Namecheap set `@`, `www`, `*` for marketian.net and `@`, `www` for marketain.net → VPS IP (or point the nameservers to Hostinger and add the records there). The tracking product will also need `edge.marketian.net` (covered by the wildcard).

## Change log (newest first)
- **2026-11-17:** Live site fixes: trusted HTTPS on every domain (proxy was on a `tls internal` preview config), Marketing tools and services added to the live portfolio.
- **2026-11-16 (deploy):** Deployed `main` to the Hostinger VPS srv2097136 (KVM 2, Ubuntu 26.04, IPv4 201.18.200.226, IPv6 2a02:4780:63:8d94::1) via the hPanel web console: Docker + `server-setup.sh` (ufw 22/80/443, 2 GB swap), repo at `/opt/sites`, every `.env` created with random secrets (`scripts/first-deploy.sh`), databases created, products registered with accounts. All 14 containers healthy; all 5 sites answer on the internal network. Waiting on: DNS at Namecheap → VPS, then HTTPS issues itself. Still placeholders: SMTP passwords (marketian, accounts) and GitHub OAuth (accounts). No superusers created yet.
- **2026-11-16:** Build and start check of `main` in Docker (isolated test project, throwaway secrets): all 7 images build; all 14 containers start (every healthcheck healthy); marketian, accounts, metadata, links and wa answer through the proxy; tables created on PostgreSQL for every site (portfolio: 21 tables, no SQLite). Found the domains' DNS is at Namecheap.
- **2026-11-16:** Merged branch `tracking` and the stashed 9 Nov evening session into `main`.
- **2026-11-16:** Infrastructure check before deploying. `docker compose config` validates all 14 services; only the proxy publishes ports; every Caddy block (and `Caddyfile.local`) matches a service; each site is on PostgreSQL (shared `postgres` 17 for accounts/metadata/links, own `marketian-db` 17 and `wa-db` 16); every Django site migrates on start; `backup.sh` covers all databases and volumes. Fixed issue 10.
- **2026-11-16:** Full status check. All 321 tests pass. Found the 9 Nov evening session parked in `stash@{0}` (issues 2–4 fixes, README for Links), no local `.env` files, and the stray `marketian.net/` clone.
- **2026-11-10 (evening):** Tracking W6–W10: destinations (Meta, GA4, TikTok, webhook; encrypted secrets), partitioned event tables, config publishing to Redis, the Caddy `ask` endpoint and domain verification. 70 tests pass on SQLite and on PostgreSQL 17 (Docker). Not committed. Next: W11–W17 (dashboard pages).
- **2026-11-10 (later):** Started building Tracking on branch `tracking`: `sites/tracking/web` with sign-in, production guard, workspaces (roles, tenancy helpers, audit log), AES-GCM secret encryption + test vector, and Site/Domain/ApiKey models. 37 tests pass on SQLite. Not committed. Next: W6 destinations, W7 event tables, W8 Redis publisher.
- **2026-11-10:** Copied docs 01–03 (updated) and 05–07 (new) from the Claude Project into this folder, and added them to the folder README. The PC folder and the Project copy now match. Not committed.
- **2026-11-10:** Tracking build task queue written ([07-tracking-build-queue.md](07-tracking-build-queue.md)): 42 tasks in 5 phases with "done when" checks, plus 9 adjustments to the spec after reading the repo (build from `sites/links`, app names `tracker`/`workspaces`, Meta `v26.0`, GA4 rules, local Caddy catch-all). No code written. Status updated for the Links site and newer commits.
- **2026-11-10:** Recorded VPS plan (Hostinger KVM 2) and the capacity estimate.
- **2026-11-10:** Tracking build spec written ([06-tracking-build-spec.md](06-tracking-build-spec.md)). Defaults taken: name "Marketian Tracking", 14-day logs.
- **2026-11-10:** Tracking product designed ([05-tracking-product.md](05-tracking-product.md)): Stape-style, own gateway, agency clients first, same VPS.
- `9f864d9` Apps merged, development continued. `1c1746b` Links (short links + bio pages). `0ad3a18` / `804a654` Portfolio: Marketing tools. `f419726` Whole server runs locally in Docker. `5a6d4dd` WA Broadcaster at wa.marketian.net with Marketian sign-in.
- **2026-11-09:** Database design drafted ([04-database-design.md](04-database-design.md)), a proposal. Full audit; created this Project Planning folder.
- Earlier: `e73d271`, `9813ff9`, `2b94efd`, `182fcc5`, `dd36d2e` (first server: portfolio, accounts, products).
