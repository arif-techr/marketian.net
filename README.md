# Marketian sites

Everything that runs on the Marketian VPS: the portfolio at **marketian.net** and every subdomain added later (for example **qr.marketian.net**). One server, one repo, each site in its own folder.

```
Marketian.net/
├── proxy/                 Caddy: HTTPS certificates + sends each domain to the right site
│   ├── Caddyfile          ← the list of every domain on the server
│   └── docker-compose.yml
├── sites/
│   ├── marketian/         marketian.net (+ marketain.net) — Django portfolio, see its README
│   ├── metadata/          metadata.marketian.net — placeholder "Coming soon" page for now
│   └── _template/         starter for a new site (copy it)
├── docker-compose.yml     ← THE root file: lists the proxy and every site; run all Docker commands here
├── scripts/
│   ├── server-setup.sh    one-time VPS preparation
│   ├── deploy.sh          start / update everything
│   └── backup.sh          daily database + uploads backup
└── README.md              this file
```

## How it fits together

```
                             ┌──────────── VPS ──────────────────────────────────────────┐
 marketian.net ──────────┐   │                                                           │
 marketain.net ──────────┤   │  proxy (Caddy, ports 80/443)                              │
 metadata.marketian.net ─┼─► │     │  "web-proxy" network                                │
 qr.marketian.net ───────┘   │     ├──► marketian:8000 (Django) ──► its own PostgreSQL   │
                             │     ├──► metadata:80   (placeholder for now)              │
                             │     └──► qr:80         (next site) ──► its own DB, if any │
                             └───────────────────────────────────────────────────────────┘
```

- **One Docker project for the whole server.** The root `docker-compose.yml` includes `proxy/` and each `sites/<name>/docker-compose.yml`, so `docker compose up -d` starts everything and `docker compose ps` shows everything.
- **Only the proxy is open to the internet.** Sites never publish ports. Each site's main service is named after the site (`marketian`, `qr`, …); the Caddyfile maps each domain to that name over the shared `web-proxy` network.
- **Each site is self-contained**: its own folder, `.env`, Docker image and database, on a private network no other site can reach. Updating one site (`docker compose up -d --build marketian`) never restarts the others, and a site can use any language (Django, Node, PHP, plain HTML).
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
| marketian.net | A | `*` | your VPS IP ← every future subdomain (qr., …) works without new DNS records |
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

### 4. Configure and start
```bash
cp sites/marketian/.env.example sites/marketian/.env
nano sites/marketian/.env                 # secret key, email password, uncomment POSTGRES_* and set a password
bash scripts/deploy.sh                    # starts the proxy and every site
docker compose exec marketian python manage.py createsuperuser
```
Open https://marketian.net. The first visit may take a few seconds while the certificate is issued.

**Email with Hostinger mail:** in `.env` use `EMAIL_HOST=smtp.hostinger.com`, `EMAIL_PORT=465`, `EMAIL_USE_SSL=True`, `EMAIL_USE_TLS=False`, and a mailbox you created in hPanel → **Emails** as `EMAIL_HOST_USER` / `DEFAULT_FROM_EMAIL`.

### 5. Updating
Change code on your computer, push it, then on the server:
```bash
cd /opt/sites && bash scripts/deploy.sh             # everything
cd /opt/sites && bash scripts/deploy.sh marketian   # just one site
```

### 6. Backups
```bash
bash scripts/backup.sh          # writes databases + uploaded files to backups/, keeps 14 days
crontab -e                      # then add this line to run it every night at 03:30:
30 3 * * * /opt/sites/scripts/backup.sh >> /var/log/sites-backup.log 2>&1
```
Download `backups/` now and then (SFTP) so a copy lives off the server too.

## Adding a new site (example: qr.marketian.net)

1. **Copy the starter:** copy `sites/_template` to `sites/qr`.
2. **Name it:** in `sites/qr/docker-compose.yml`, replace every `CHANGE-ME` with `qr`.
3. **Register it:** in the root `docker-compose.yml`, uncomment (or add) `- sites/qr/docker-compose.yml`.
4. **Build it:** the template serves the plain page in `public/` (a "Coming soon" page). Replace the `Dockerfile` and files with the real app whenever it's ready. The only rule is that it listens on the port you name in step 5.
5. **Route it:** in `proxy/Caddyfile`, uncomment the `qr.marketian.net` block (`reverse_proxy qr:80`).
6. **Ship it:** commit, push, and run `bash scripts/deploy.sh` on the server.

The wildcard DNS record means there is nothing to change in hPanel.

For a site that needs a database, copy the `marketian-db` service, `marketian-pgdata` volume and `marketian-private` network from `sites/marketian/docker-compose.yml`, renaming `marketian` to the new site's name (names must be unique across the whole server). A new Django site can start as a copy of `sites/marketian`, which brings the mail system, admin and design along.

## Everyday commands

| What | Command (from `/opt/sites`) |
|---|---|
| What's running | `docker compose ps` |
| Start / update everything | `bash scripts/deploy.sh` |
| Update one site | `bash scripts/deploy.sh marketian` |
| A site's logs | `docker compose logs -f marketian` |
| Proxy / certificate logs | `docker compose logs -f proxy` |
| Restart one site | `docker compose restart marketian` |
| Django shell / commands | `docker compose exec marketian python manage.py <command>` |
| Disk space used by Docker | `docker system df` |
