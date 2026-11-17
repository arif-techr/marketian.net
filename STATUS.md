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
