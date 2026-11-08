# Marketian sites

Everything that runs on the Marketian VPS: the portfolio at **marketian.net**, the shared **Marketian account** at accounts.marketian.net, and the SaaS products on their own subdomains: **metadata.marketian.net** and the WhatsApp broadcaster **wa.marketian.net**. One server, one repo, each site in its own folder.

```
Marketian.net/
├── proxy/                 Caddy: HTTPS certificates + sends each domain to the right site
│   ├── Caddyfile          ← the list of every domain on the server
│   └── docker-compose.yml
├── infra/                 shared PostgreSQL for the SaaS products (one database per product)
├── sites/
│   ├── marketian/         marketian.net (+ marketain.net) — Django portfolio, see its README
│   ├── accounts/          accounts.marketian.net — one login (GitHub or email) for every product
│   ├── metadata/          metadata.marketian.net — first SaaS product, signs in with the Marketian account
│   ├── wa/                wa.marketian.net — WhatsApp broadcaster (Django + React + WhatsApp gateway), see its README
│   └── _template/         starter for a plain site (copy it)
├── docker-compose.yml     ← THE root file: lists the proxy and every site; run all Docker commands here
├── scripts/
│   ├── server-setup.sh    one-time VPS preparation
│   ├── deploy.sh          start / update everything
│   ├── create-db.sh       a database + login for one product on the shared PostgreSQL
│   └── backup.sh          daily backup of databases, uploads and sign-in keys
└── README.md              this file
```

## How it fits together

```
                             ┌──────────── VPS ─────────────────────────────────────────────────┐
 marketian.net ──────────┐   │                                                                  │
 marketain.net ──────────┤   │  proxy (Caddy, ports 80/443)                                     │
 accounts.marketian.net ─┼─► │     │  "web-proxy" network                                       │
 metadata.marketian.net ─┤   │     ├──► marketian:8000 (Django) ──► its own PostgreSQL          │
 wa.marketian.net ───────┘   │     ├──► accounts:8000  (Django) ──┐                             │
                             │     ├──► metadata:8000  (Django) ──┴─► shared PostgreSQL (infra) │
                             │     │                                 one database per product   │
                             │     └──► wa:80 (Nginx + React) ──► wa-backend, wa-worker, wa-beat│
                             │            wa-gateway (WhatsApp) ──► its own PostgreSQL + Redis  │
                             └──────────────────────────────────────────────────────────────────┘
```

- **One Docker project for the whole server.** The root `docker-compose.yml` includes `proxy/`, `infra/` and each `sites/<name>/docker-compose.yml`, so `docker compose up -d` starts everything and `docker compose ps` shows everything.
- **Only the proxy is open to the internet.** Sites never publish ports. Each site's main service is named after the site (`marketian`, `accounts`, `metadata`, …); the Caddyfile maps each domain to that name over the shared `web-proxy` network.
- **Each site is self-contained**: its own folder, `.env` and Docker image. Updating one site (`bash scripts/deploy.sh metadata`) never restarts the others, and a site can use any language.
- **Databases:** the portfolio and the WhatsApp broadcaster keep their own PostgreSQL. The SaaS products and the accounts site share one PostgreSQL server (`infra/`), but each gets its own database and login, so no product can read another's data. Only containers on the internal `shared-db` network can reach it.
- **One login for every product.** People sign in once at accounts.marketian.net (GitHub or email + password). Products send people there over OpenID Connect and get them back signed in; a product never sees a password.
- **Fast pages.** The portfolio and Metadata load the next page without a full reload (htmx), and start fetching a page as soon as the pointer rests on its link. No build step: it's one script file in each site's `static/js/vendor/`.
- **HTTPS is automatic.** Caddy gets and renews a certificate for every domain listed in the Caddyfile.

## Hosting on Hostinger VPS

### 1. Create the VPS
In hPanel → **VPS**, choose the **Ubuntu 24.04** operating system (the plain one or "with Docker" both work). Note the server's **IP address** and set a root password or SSH key.

### 2. Point the domains at it
In hPanel → **Domains → DNS / Nameservers** (for each domain):

| Domain | Type | Name | Points to |
|---|---|---|---|
| marketian.net | A | `@` | your VPS IP |
| marketian.net | A | `www` | your VPS IP |
| marketian.net | A | `*` | your VPS IP ← accounts., metadata. and every future subdomain work without new DNS records |
| marketain.net | A | `@` | your VPS IP |
| marketain.net | A | `www` | your VPS IP |

Delete any old A/AAAA records for `@` and `www` that point elsewhere (for example a parking page). Changes can take up to an hour.

### 3. Prepare the server (once)
```bash
ssh root@YOUR_VPS_IP
git clone <your repo URL> /opt/sites      # or upload this folder to /opt/sites with SFTP
cd /opt/sites
bash scripts/server-setup.sh              # Docker, firewall, swap, automatic security updates
```
If you enabled Hostinger's own VPS firewall in hPanel, allow ports 22, 80 and 443 there too.

### 4. Configure and start (first time, in this order)

Generate every secret below with `openssl rand -hex 24`.

**a. The portfolio**
```bash
cp sites/marketian/.env.example sites/marketian/.env
nano sites/marketian/.env                 # SECRET_KEY, email password, uncomment POSTGRES_* and set a password
```

**b. The shared database**
```bash
cp infra/.env.example infra/.env
nano infra/.env                           # POSTGRES_PASSWORD
bash scripts/create-db.sh accounts        # prints 3 POSTGRES_* lines: keep them for step c
bash scripts/create-db.sh metadata        # prints 3 more: keep them for step d
```
(The WhatsApp broadcaster has its own database server; it needs no `create-db.sh`.)

**c. The Marketian account (accounts.marketian.net)**
1. On GitHub → **Settings → Developer settings → OAuth Apps → New OAuth App**:
   - Homepage URL: `https://accounts.marketian.net`
   - Authorization callback URL: `https://accounts.marketian.net/accounts/github/login/callback/`
2. Then:
   ```bash
   cp sites/accounts/.env.example sites/accounts/.env
   nano sites/accounts/.env               # SECRET_KEY, the POSTGRES_* lines from step b, GITHUB_CLIENT_ID/SECRET, email
   ```

**d. Metadata**
```bash
cp sites/metadata/.env.example sites/metadata/.env
nano sites/metadata/.env                  # SECRET_KEY and the POSTGRES_* lines from step b
```

**e. WhatsApp broadcaster**
```bash
cp sites/wa/.env.example sites/wa/.env
nano sites/wa/.env                        # DJANGO_SECRET_KEY, POSTGRES_PASSWORD, GATEWAY_API_KEY, ADMIN_PASSWORD
```

**f. Start everything, then connect the products to the account**
```bash
bash scripts/deploy.sh
docker compose exec marketian python manage.py createsuperuser
docker compose exec accounts python manage.py createsuperuser
docker compose exec accounts python manage.py register_product metadata https://metadata.marketian.net
nano sites/metadata/.env                  # paste the MARKETIAN_CLIENT_ID / MARKETIAN_CLIENT_SECRET it printed
docker compose exec accounts python manage.py register_product wa https://wa.marketian.net
nano sites/wa/.env                        # paste the two lines it printed
bash scripts/deploy.sh metadata wa-backend
```
Open https://marketian.net, https://accounts.marketian.net, https://metadata.marketian.net and https://wa.marketian.net. On the broadcaster only people you add can sign in (see [its README](sites/wa/README.md)), and its admin is `admin` with the `ADMIN_PASSWORD` you set. The first visit to each may take a few seconds while its certificate is issued.

**Email with Hostinger mail:** in each `.env` use `EMAIL_HOST=smtp.hostinger.com`, `EMAIL_PORT=465`, `EMAIL_USE_SSL=True`, `EMAIL_USE_TLS=False`, and a mailbox you created in hPanel → **Emails** as `EMAIL_HOST_USER` / `DEFAULT_FROM_EMAIL`. The accounts site needs working email: new accounts must confirm their address.

### 5. Updating
Change code on your computer, push it, then on the server:
```bash
cd /opt/sites && bash scripts/deploy.sh             # everything
cd /opt/sites && bash scripts/deploy.sh marketian   # just one site
```

### 6. Backups
```bash
bash scripts/backup.sh          # writes everything below to backups/, keeps 14 days
crontab -e                      # then add this line to run it every night at 03:30:
30 3 * * * /opt/sites/scripts/backup.sh >> /var/log/sites-backup.log 2>&1
```

What ends up in `backups/`:

| File | What it is |
|---|---|
| `marketian_db_*.sql.gz` | the portfolio's database |
| `wa_db_*.sql.gz` | the WhatsApp broadcaster's database |
| `shared_roles_*.sql.gz` | the logins of the shared PostgreSQL server |
| `shared_<product>_db_*.sql.gz` | one per database on the shared server (accounts, metadata, …) |
| `marketian_media_*.tar.gz` | uploaded photos and CV |
| `wa-backend_media_*.tar.gz` | the broadcaster's attachments |
| `wa-gateway_sessions_*.tar.gz` | the linked WhatsApp numbers' logins: full access to those numbers, keep it safe |
| `accounts_keys_*.tar.gz` | the key that signs sign-in tokens. Losing it signs everyone out of every product |

The folder holds passwords and private keys, so only root can read it. Download it now and then (SFTP) so a copy lives off the server too.

**Restoring** (from `/opt/sites`; replace the dates with the backup you want):
```bash
# The portfolio's database
gunzip -c backups/marketian_db_DATE.sql.gz | docker compose exec -T marketian-db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'

# A product's database on the shared server (logins first, then the database)
gunzip -c backups/shared_roles_DATE.sql.gz | docker compose exec -T postgres psql -U postgres
docker compose exec -T postgres createdb -U postgres -O accounts accounts 2>/dev/null || true
gunzip -c backups/shared_accounts_db_DATE.sql.gz | docker compose exec -T postgres psql -U postgres accounts

# Uploaded files / sign-in keys / WhatsApp logins
docker compose exec -T marketian tar -xzf - -C /app < backups/marketian_media_DATE.tar.gz
docker compose exec -T accounts tar -xzf - -C /app < backups/accounts_keys_DATE.tar.gz
docker compose exec -T wa-backend tar -xzf - -C /app < backups/wa-backend_media_DATE.tar.gz
docker compose exec -T wa-gateway tar -xzf - -C /app < backups/wa-gateway_sessions_DATE.tar.gz
docker compose restart accounts wa-gateway

# The broadcaster's database works like the portfolio's
gunzip -c backups/wa_db_DATE.sql.gz | docker compose exec -T wa-db sh -c 'psql -U "$POSTGRES_USER" "$POSTGRES_DB"'
```

## Adding a new SaaS product (example: qr.marketian.net)

A product signs in with the Marketian account and keeps its data in its own database on the shared server.

1. **Copy Metadata:** copy `sites/metadata` to `sites/qr`, then rename it inside:
   - `sites/qr/docker-compose.yml`: the service `metadata` → `qr`, the image `metadata-web` → `qr-web`.
   - `sites/qr/.env.example`: `metadata` → `qr` in the names and addresses, and set `PRODUCT_NAME` / `PRODUCT_TAGLINE`.
   - `sites/qr/product/settings.py`: the default `metadata.marketian.net` addresses → `qr.marketian.net`.
2. **Register it:** in the root `docker-compose.yml`, add `- sites/qr/docker-compose.yml`.
3. **Route it:** in `proxy/Caddyfile`, uncomment the `qr.marketian.net` block and point it at `qr:8000`.
4. **Database and login:** on the server,
   ```bash
   bash scripts/create-db.sh qr
   docker compose exec accounts python manage.py register_product qr https://qr.marketian.net
   cp sites/qr/.env.example sites/qr/.env && nano sites/qr/.env     # paste both sets of lines
   ```
5. **Build the product** in `sites/qr/dashboard/` (views, templates, models). Commit, push and run `bash scripts/deploy.sh`.

The wildcard DNS record means there is nothing to change in hPanel. The new product appears on everyone's account page at accounts.marketian.net automatically.

**A plain site without logins** (a landing page, a static tool): copy `sites/_template` instead, replace every `CHANGE-ME` in its `docker-compose.yml` with the site's name, and use `reverse_proxy <name>:80` in the Caddyfile.

## Run everything on your computer (Docker)

The whole server, exactly as on the VPS, on your own computer: every site at a `*.localhost` address over plain http (browsers send `*.localhost` to your computer by themselves).

| Site | Address |
|---|---|
| Portfolio | http://marketian.localhost |
| Marketian account | http://accounts.localhost |
| Metadata | http://metadata.localhost |
| WhatsApp broadcaster | http://wa.localhost |

1. Create every `.env` (the same files as on the server, with local values): `DEBUG=False`, `SECURE_SSL_REDIRECT=False`, and the addresses above instead of the real domains, e.g. `ALLOWED_HOSTS=accounts.localhost` and `CSRF_TRUSTED_ORIGINS=http://accounts.localhost`. Accounts and Metadata also need `SECURE_COOKIES=False`; accounts `PRODUCTS_DOMAIN=localhost`; products `ACCOUNTS_URL=http://accounts.localhost`; the broadcaster `DJANGO_SECURE=false`.
2. Then, from the repo root in Git Bash:
   ```bash
   export CADDYFILE=Caddyfile.local                 # plain http, *.localhost names
   bash scripts/create-db.sh accounts && bash scripts/create-db.sh metadata
   docker compose up -d --build
   docker compose exec accounts python manage.py register_product metadata http://metadata.localhost
   docker compose exec accounts python manage.py register_product wa http://wa.localhost
   docker compose up -d metadata wa-backend wa-worker wa-beat   # after pasting the client IDs into their .env
   ```
3. Stop with `docker compose down` (data stays in Docker volumes); start again with `CADDYFILE=Caddyfile.local docker compose up -d`.

Local `.env` files never go to git. Running the Django tests with them present: add `DEBUG=True POSTGRES_DB= CANONICAL_HOST=` in front of the test command.

## Working on it locally

Each Django site runs on its own with SQLite and prints emails in the terminal. From a site's folder:
```bash
python -m venv ../../.venv && ..\..\.venv\Scripts\activate      # macOS/Linux: source ../../.venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Tests:
```bash
cd sites/marketian && python manage.py test core mailer
cd sites/accounts  && python manage.py test portal
cd sites/metadata  && python manage.py test dashboard
cd sites/wa        && npm test                     # after npm run setup (see sites/wa/README.md)
```

## Everyday commands

| What | Command (from `/opt/sites`) |
|---|---|
| What's running | `docker compose ps` |
| Start / update everything | `bash scripts/deploy.sh` |
| Update one site | `bash scripts/deploy.sh marketian` |
| A site's logs | `docker compose logs -f marketian` (the broadcaster: `wa-backend wa-worker wa-gateway`) |
| Proxy / certificate logs | `docker compose logs -f proxy` |
| Restart one site | `docker compose restart marketian` |
| Django shell / commands | `docker compose exec marketian python manage.py <command>` |
| List products that can sign in | `docker compose exec accounts python manage.py shell -c "from oauth2_provider.models import Application as A; print(list(A.objects.values_list('name', flat=True)))"` |
| Disk space used by Docker | `docker system df` |
