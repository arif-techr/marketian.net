# Plan: what we're doing

## The goal
**Marketian** is a set of marketing tools that make marketing smoother. They run on one Hostinger VPS:

- **marketian.net**: portfolio and agency site (services, portfolio, contact, built-in email sender).
- **accounts.marketian.net**: one Marketian account (GitHub or email + password) that signs people in to every product.
- **SaaS products on subdomains**, each one its own app with its own database:
  - **metadata.marketian.net**: the first product.
  - **wa.marketian.net**: WA Broadcaster. It links WhatsApp numbers by QR code and sends one message to many contacts, paced and scheduled, with tracking.
  - More to come (for example **qr.marketian.net**). Each one is copied from `sites/metadata`.

One server, one repo, one `docker compose up`. Caddy handles HTTPS for every domain, and only the proxy is reachable from the internet.

## Roadmap

### Now: finish and ship the WA Broadcaster integration
1. Remove the old `wa-broadcaster/` copy from the repo folder, or ignore it in git. It holds a `.venv` and SQL dumps that may contain contact phone numbers.
2. Add `*.sqlite3-journal` to `.gitignore`.
3. Fix or remove the `docker:up` / `docker:down` / `docker:logs` scripts in `sites/wa/package.json`. The compose file now has to be started from the repo root.
4. Run every test suite locally (see the README's "Tests" section) and fix anything that fails.
5. Commit the Marketian sign-in work for the broadcaster, then push. Four earlier commits are also waiting to be pushed.
6. On the server, follow README steps 4e/4f: create `sites/wa/.env`, `register_product wa`, then `deploy.sh`.
7. Smoke-test in production:
   - sign in with a Marketian account
   - sign in as an admin-added user (matched by email)
   - sign out, which also signs you out of accounts
   - link a test WhatsApp number
   - send a small campaign
   - run `scripts/backup.sh` and check that `wa-*` files appear

### Next: harden and operate
- Schedule `backup.sh` with cron (03:30 nightly) and download a copy off the server now and then.
- Make the Django sites refuse to start in production with the placeholder `SECRET_KEY`, so a missing `.env` line can't leave a site in debug mode.
- Add basic uptime monitoring for the four domains.
- Write down how to roll back a deploy (which image or commit to go back to).

### Later: grow the product line
- Next SaaS product (`qr.marketian.net` or similar), copied from `sites/metadata`.
- Build out Metadata's actual product features in `sites/metadata/dashboard/`.
- Billing/plans on the Marketian account, if products become paid.

## How we work
- Write code on the PC (`D:\AI-Projects\marketian.net`), push to GitHub (`arif-techr/marketian.net`), and deploy on the VPS with `bash scripts/deploy.sh [site]`.
- Each site runs locally on its own with SQLite. Emails print to the terminal.
- After every work session, update [02-status.md](02-status.md).
