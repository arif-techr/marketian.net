# Status

As of: 2026-11-09 (from the audit in [audits/2026-11-09-audit.md](audits/2026-11-09-audit.md))

**Overall:** All four sites are built. The WA Broadcaster's sign-in with the Marketian account is coded but **not committed**. Nothing has been confirmed as deployed yet.

## Sites

| Site | Folder | State | Tests | Notes |
|---|---|---|---|---|
| marketian.net (+ marketain.net) | `sites/marketian` | ✅ Built, committed | 19 (core 11, mailer 8) | Django portfolio + email sender, htmx page loading |
| accounts.marketian.net | `sites/accounts` | ✅ Built, committed | 11 | allauth (GitHub/email) + OpenID Connect provider (django-oauth-toolkit) |
| metadata.marketian.net | `sites/metadata` | ✅ Shell built, committed | 8 | Sign-in, landing page and dashboard work. Product features still to build |
| wa.marketian.net | `sites/wa` | 🟡 Built. Marketian sign-in **uncommitted** | 130 (incl. 11 new for Marketian sign-in) | Django + DRF + Celery + React + WhatsApp gateway (Baileys / Evolution) |
| Proxy / infra / scripts | `proxy`, `infra`, `scripts` | 🟡 Committed. wa additions uncommitted | none | Caddy, shared PostgreSQL, deploy/backup/create-db |

## Repo
- Branch `main`, 8 commits. As of the last fetch, `origin/main` was at `dd36d2e`, so **4 local commits are unpushed**.
- **Uncommitted:** 21 modified files and 3 new ones (`apps/core/marketian.py`, `backend/templates/`, `tests/test_marketian.py`). This is all the Marketian sign-in for the broadcaster, plus the matching changes to the Caddyfile, root compose file and backup script.

## Checks (2026-11-09)
- ✅ 175 Python files parse with no syntax errors.
- ✅ WA frontend type-checks cleanly (`tsc --noEmit`, 0 errors).
- ✅ Sign-in wiring is consistent end to end: the callback URL matches, Nginx forwards `/accounts/`, the logout redirect to `*.marketian.net` is allowed, and the `email_verified` claim is sent.
- ⚠️ The test suites haven't been run in this audit (Django not available in the audit environment). Run them locally.

## Open issues
| # | Issue | Severity | Status |
|---|---|---|---|
| 1 | `wa-broadcaster/` (old copy) is untracked and not ignored. It contains `.venv` and `backups/*.sql` with likely contact data | High (data leak if `git add .`) | Open |
| 2 | `sites/wa/backend/db.sqlite3-journal` is untracked and not ignored | Low | Open |
| 3 | `sites/wa/package.json` `docker:*` scripts no longer work standalone | Low | Open |
| 4 | Django sites default to `DEBUG=True` + placeholder `SECRET_KEY` if `.env` lines are missing | Medium (config mistake → exposure) | Open |
| 5 | Test suites not yet run after the WA integration | Medium | Open |

## Deployment
- VPS: Hostinger, Ubuntu 24.04, repo at `/opt/sites`. **Not yet confirmed as set up.**
- DNS: `@`, `www`, `*` for marketian.net and `@`, `www` for marketain.net → VPS IP. **Not yet confirmed.**

## Change log (newest first)
- **2026-11-09:** Full audit. Created this Project Planning folder.
- **2026-11-09:** `e73d271` WA Broadcaster: sharing, dynamic message fields, phone pacing.
- `9813ff9` Added WA Broadcaster (with its repo history) under `sites/wa`.
- `2b94efd` Backups of the shared database and sign-in key, tests for accounts and Metadata, README.
- `182fcc5` Pages load without a full reload (htmx) on the portfolio and Metadata.
- `dd36d2e` Marketian server: portfolio, accounts (GitHub login) and SaaS products. ← last pushed
