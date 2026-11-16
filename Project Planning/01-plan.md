# Plan: what we're doing

## The goal
**Marketian** is a set of marketing tools that make marketing smoother. They run on one Hostinger VPS:

- **marketian.net**: portfolio and agency site (services, portfolio, contact, built-in email sender).
- **accounts.marketian.net**: one Marketian account (GitHub or email + password) that signs people in to every product.
- **SaaS products on subdomains**, each one its own app with its own database:
  - **metadata.marketian.net**: the first product.
  - **wa.marketian.net**: WA Broadcaster. It links WhatsApp numbers by QR code and sends one message to many contacts, paced and scheduled, with tracking.
  - **links.marketian.net**: short links with click stats and QR codes, plus Linktree-style bio pages.
  - **tracking.marketian.net**: server-side first-party tracking, Stape-style. Each client site sends its events through its own subdomain, and we forward them to Meta CAPI, GA4, TikTok and others. Design: [05-tracking-product.md](05-tracking-product.md).
  - More to come (for example **qr.marketian.net**). Each one is copied from `sites/metadata`.

One server, one repo, one `docker compose up`. Caddy handles HTTPS for every domain (including client tracking subdomains, via on-demand TLS), and only the proxy is reachable from the internet.

## Roadmap

### Now: check locally, then ship
Done 2026-11-09: old `wa-broadcaster/` copy removed, `*.sqlite3-journal` ignored, WA `docker:*` scripts fixed, all test suites pass (251), WA sign-in committed and pushed.

1. Start Docker Desktop and click through Links end to end (see [STATUS.md](../STATUS.md)).
2. ✅ 2026-11-16: everything merged into `main` (9 Nov fixes, portfolio Postgres fix, Tracking W1–W10).
3. On the server, follow the README's "Hosting on Hostinger VPS" (steps 4a–4g). That covers `.env` files for every site, `create-db.sh` and `register_product` for metadata, links and wa, then `deploy.sh`.
4. Smoke-test in production:
   - sign in with a Marketian account
   - sign in as an admin-added user (matched by email)
   - sign out, which also signs you out of accounts
   - Links: make a short link, open it, and check the click shows; publish a bio page
   - link a test WhatsApp number
   - send a small campaign
   - run `scripts/backup.sh` and check that `wa-*` and `links_media_*` files appear

### Next: harden and operate
- Schedule `backup.sh` with cron (03:30 nightly) and download a copy off the server now and then.
- Add basic uptime monitoring for the domains (including tracking once live).
- Set a memory limit on every container.
- Write down how to roll back a deploy (which image or commit to go back to).

### Then: Tracking product (see [05-tracking-product.md](05-tracking-product.md) §7)
- **T0:** answer the open questions in 05 §8, `register_product tracking`, DNS record `edge.marketian.net`.
- **T1 (MVP):** `sites/tracking` (Django dashboard + Node edge/worker + Redis), custom subdomains with on-demand TLS, `mt.js` loader, Meta CAPI + GA4, live event log. Go live on one real client site.
- **T2:** TikTok, server events API, cookie keeper, bot filter, geo, consent rules, retention.
- **T3:** same-origin path mode (for Safari), WordPress/Woo plugin, more destinations, stats and alerts.
- **T4:** self-serve, plans and billing.

### Later: grow the product line
- Next SaaS product (`qr.marketian.net` or similar), copied from `sites/metadata`.
- Build out Metadata's actual product features in `sites/metadata/dashboard/`.
- Billing/plans on the Marketian account, if products become paid.

## How we work
- Write code on the PC (`D:\AI-Projects\marketian.net`), push to GitHub (`arif-techr/marketian.net`), and deploy on the VPS with `bash scripts/deploy.sh [site]`.
- Each site runs locally on its own with SQLite. Emails print to the terminal.
- After every work session, update [02-status.md](02-status.md).
