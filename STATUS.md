# Where we left off (17 Nov 2026)

Full status, open issues and history: [Project Planning/02-status.md](Project%20Planning/02-status.md).
Plans: Tracking [05–07](Project%20Planning/07-tracking-build-queue.md), Marketian SMS [08](Project%20Planning/08-sms-plan.md).

## Live

Five sites run on the Hostinger VPS (`201.18.200.226`, repo at `/opt/sites`), all with Let's Encrypt HTTPS:
marketian.net (+ marketain.net), accounts., metadata., links. and wa.marketian.net. DNS is at Namecheap.

**Updating the live sites:** push to `main`, then on the server `cd /opt/sites && bash scripts/deploy.sh`
(or `deploy.sh <service>`). Never start the proxy with `CADDYFILE=` set there, and never run
`scripts/first-deploy.sh` on it (both are explained in 02-status, "Deployment").
SSH from the PC that has the key: `ssh -i ~/.ssh/marketian_vps root@201.18.200.226`. On another PC,
make a new key and add it in hPanel → VPS → SSH keys (keys are per PC; never copy the private key around).

## Continue on another PC

```bash
git clone https://github.com/arif-techr/marketian.net.git
cd marketian.net
```

| To work on | Set up once |
|---|---|
| marketian, accounts, metadata, links, tracking/web | `python -m venv .venv` in the repo root, then `pip install -r sites/<site>/requirements.txt` (on Python 3.15 leave out psycopg; tests use SQLite) |
| sms/api | Python **3.12**: see [sites/sms/api/README.md](sites/sms/api/README.md) |
| wa | Python 3.12 in `sites/wa/backend/.venv`: see [sites/wa/README.md](sites/wa/README.md) |
| Whole server locally | Docker Desktop; copy each `.env.example` to `.env` (`infra/` and every site), then `CADDYFILE=Caddyfile.local docker compose up -d --build` and open `http://<site>.localhost` |

`.env` files are never in git: each PC (and the server) keeps its own.

## Before the next deploy (admin pages now use the Marketian account)

The admin pages (`/admin/`) of the portfolio, metadata and links no longer have a password form. Do this on
the server **before** `deploy.sh`, or nobody can open them until you do:

```bash
cd /opt/sites
docker compose exec accounts python manage.py register_product marketian https://marketian.net
nano sites/marketian/.env   # paste MARKETIAN_CLIENT_ID / MARKETIAN_CLIENT_SECRET, add ACCOUNTS_URL=https://accounts.marketian.net
nano sites/marketian/.env   # ADMIN_EMAILS=<your Marketian account email>
nano sites/metadata/.env    # ADMIN_EMAILS=<same>
nano sites/links/.env       # ADMIN_EMAILS=<same>
bash scripts/deploy.sh
```

## Sign-up fix (18 Nov, not deployed)

Visitors couldn't create a Marketian account: accounts required clicking an email link, and email
doesn't send yet. Now `EMAIL_VERIFICATION=optional` (the default), and a failing mail server is logged
instead of breaking sign-up. Admin pages only accept a **verified** email (`email_verified` claim), so
nobody can become admin by signing up with your address. Deploy: `bash scripts/deploy.sh accounts`.
Before using the admin pages: your own email must be verified on accounts. Until email sends, tick
"Verified" for it at https://accounts.marketian.net/admin/ → Email addresses. When email works, set
`EMAIL_VERIFICATION=mandatory` in `sites/accounts/.env`.

## Databases and sign-in (rule, 17 Nov)

- Own PostgreSQL server: **portfolio, WA, SMS**. Everyone else: own database on the shared server.
- One Marketian account for everything, admin pages included (`ADMIN_EMAILS` per site). WA also keeps
  its username/password sign-in for team members and its admin.

## Being built

- **Marketian SMS** (`sites/sms`, not live): Next.js panel + a new Django API on PostgreSQL with Marketian
  sign-in, replacing the Laravel reference. Done: S0 (source, 248-endpoint contract) and S1.1–S1.2
  (Django foundation, 45 tables). **Next: S1.3** sessions + Marketian sign-in, then S1.4 organisations and roles.
- **Tracking** (`sites/tracking`, not live): dashboard back end W1–W10 done. Next: W11–W17 dashboard pages.

## Open (needs you)

- Mailbox password for `no-reply@marketian.net` (Namecheap) in `sites/marketian/.env` and `sites/accounts/.env`
  on the server, and `EMAIL_HOST=mail.marketian.net` in accounts: email doesn't send until then.
- Link a WhatsApp number at wa.marketian.net (admin password: `grep ADMIN_PASSWORD /opt/sites/sites/wa/.env`).
- Portfolio content on the live site: profile, photo, projects, skills (https://marketian.net/admin/).
- Nightly backups aren't scheduled yet (`crontab`, see README "Backups").
- Metadata: decide what the product does.
