# WA Broadcaster

Link WhatsApp accounts by scanning a QR code, then send one message to many **contacts** (individual recipients), shared out across those accounts, safely paced, scheduled and tracked.

> **Important:** this uses an unofficial WhatsApp Web connection (Baileys, or Evolution API, which is built on it). That is against WhatsApp's terms, and numbers can be banned, especially for fast or bulk sending. Only message people who expect it, keep waits between messages at 8 seconds or more, and test with a number you can afford to lose.

## Features

- **Accounts:** link any number of WhatsApp accounts by QR code. Logins are kept and reconnect by themselves. Per-account daily limits.
- **Contacts:** save numbers with names, organise them into lists, import from a pasted list or CSV (Excel / Google Sheets), and export to CSV. Local numbers like `017…` get your default country code. Opted-out contacts are never messaged.
- **WhatsApp check:** imported numbers are checked for WhatsApp in the background through a connected account. Numbers that aren't on WhatsApp are left out of broadcasts, and you can filter by the result or re-check numbers.
- **Recipients:** pick contact lists, single contacts or paste numbers. Each number is checked for WhatsApp before sending. `{name}` (or `{name|friend}` with a fallback) puts each person's name in the message.
- **Composer:** WhatsApp formatting (bold, italic, strike, mono) with a live chat-bubble preview, attachments up to 25 MB (photo, video, GIF, audio, document), attach by link, and templates.
- **Sender rotation:** choose which accounts send. They can take turns (N messages each), be picked at random, or go by fewest sent today. With failover, an account that disconnects or reaches its daily limit is passed over.
- **Safe sending:** one message at a time, a random wait in your range, optional breaks after every N messages, "typing…" before each message, and daily limits per account.
- **Scheduling and queue:** send now or at a set time. Sends queue and run one after another.
- **Live campaign status:** open a campaign to see who is being sent to right now, who's next, a countdown, sent/failed/skipped/waiting counts, and time left.
- **Control:** pause, resume, cancel, and "retry failed" for any campaign. A crash or restart resumes where it stopped, without double-sending.
- **Dashboard:** live progress, today's numbers, and the last 7 days.
- **Reports:** pick a date range to see totals, delivery rate, messages per day, results by account and by campaign, plus the most common failure reasons. Download as CSV, or download one campaign's full recipient report.
- **Separate workspaces:** every user has their own WhatsApp accounts, contacts, lists, campaigns, templates, settings and reports. Nobody sees another user's data. Each workspace sends one campaign at a time; different workspaces send side by side.
- **Team members:** in **Settings → Team**, a user adds employees or support assistants with their own sign-in. They work in that user's workspace and can do all the work, except add people or change passwords (the owner resets theirs).
- **Share resources:** a user can share chosen WhatsApp accounts, contact lists and templates with another user. They type the username and pick the items; a 6-digit code (valid 10 minutes) appears on their screen, and the other user enters it under **Share resources** to accept. Shared items show a **Shared** tag; they can be used (sent from, sent to, used as a message) but not changed, a shared phone's QR code is never shown, and either side can stop sharing any time. A WhatsApp account never runs two campaigns at once, even when shared.
- **Dynamic messages:** import an Excel (.xlsx) or CSV file, choose which columns are the phone, the name, and which to **use in messages** (e.g. Score). Templates then use them as `{score}` (or `{score|N/A}` for people with no value), and each person gets their own values.
- **Sign in with the Marketian account:** owners sign in at accounts.marketian.net (GitHub or email), the same login as every Marketian product. Team members and the admin use the username and password they were given. With `ALLOW_SIGNUP=false` (the default) only people you added in `/admin/` (a user with their email) can get in; `true` lets anyone with a Marketian account start a workspace.

## Architecture

```
 Browser ──► React UI (Vite / Nginx) ──/api──► Django REST API ──► PostgreSQL
                                                   │    ▲
                                    Celery beat ──►│    │ webhooks (connection changes)
                                    Celery worker ─┤    │
                                     (Redis broker)│    │
                                                   ▼    │
                                     WhatsApp provider (WA_PROVIDER)
                                     ├─ builtin:   ./gateway  (Node + Baileys, internal HTTP API)
                                     └─ evolution: Evolution API v2
```

| Folder | What it is |
|---|---|
| `backend/` | Django 5 + Django REST Framework. Apps: `core` (auth, sign-up, team members, per-user settings, dashboard), `whatsapp` (accounts, providers), `contacts` (numbers, lists, import/export), `broadcasts` (campaigns, sending engine, sender rotation, reports, templates, media). |
| `gateway/` | Small Node service that holds the WhatsApp (Baileys) connections. Internal only, protected by `GATEWAY_API_KEY`. |
| `frontend/` | React + TypeScript + Vite single-page app. |
| `docker-compose.yml` | The full stack: Postgres, Redis, Django (gunicorn), Celery worker and beat, gateway, Nginx serving the UI, and optionally Evolution API. Included by the repo's root `docker-compose.yml`. |
| `scripts/` | `setup` and `dev` helpers for running without Docker. |

**How sending works:** Celery beat checks every 5 seconds for a due campaign and hands it to a worker. The worker picks the sending account (following the rotation), sends to one contact, saves the result in the database, waits, and moves to the next contact. All progress lives in Postgres, so pausing, cancelling, a restart or a crash never loses track. A message that was mid-send during a crash is marked "may or may not have arrived" rather than sent twice.

---

## 1. On the Marketian server

This app is the `wa` site of the Marketian server (wa.marketian.net). It starts with everything else from the repo root, behind the shared Caddy proxy, which handles HTTPS. Its services are `wa` (Nginx + the React UI), `wa-backend`, `wa-worker`, `wa-beat`, `wa-gateway`, `wa-db` and `wa-redis`. See the [repo README](../../README.md) for the first-time setup; the parts specific to this site:

```bash
cp sites/wa/.env.example sites/wa/.env
nano sites/wa/.env              # DJANGO_SECRET_KEY, POSTGRES_PASSWORD, GATEWAY_API_KEY, ADMIN_PASSWORD
docker compose exec accounts python manage.py register_product wa https://wa.marketian.net
nano sites/wa/.env              # paste MARKETIAN_CLIENT_ID / MARKETIAN_CLIENT_SECRET
bash scripts/deploy.sh          # or just this site: bash scripts/deploy.sh wa wa-backend wa-worker wa-beat wa-gateway
```

Open https://wa.marketian.net and press **Continue with Marketian account**. To let someone in while `ALLOW_SIGNUP=false`: in https://wa.marketian.net/admin/ (sign in as `admin` with `ADMIN_PASSWORD`) add a user with their email address; they then sign in with their Marketian account.

Useful commands (from the repo root):

```bash
docker compose ps                                   # what's running
docker compose logs -f wa-worker wa-gateway         # watch sending and WhatsApp
docker compose exec wa-backend python manage.py createsuperuser
```

Migrations run by themselves on every deploy. `scripts/backup.sh` backs up the database (`wa_db_*`), uploads (`wa-backend_media_*`) and the WhatsApp logins (`wa-gateway_sessions_*`).

## 2. Run without Docker (quick local development)

Needs **Node.js 20+** and **Python 3.11+**. No Postgres or Redis needed: it uses SQLite and a built-in worker.

```bash
npm run setup     # creates .env with random secrets, Python venv, database, npm packages
npm run dev       # starts gateway, Django, worker and the UI together
```

Open **http://localhost:5173**. `setup` prints the admin password (it's also in `.env` as `ADMIN_PASSWORD`). Locally `MARKETIAN_CLIENT_ID` is empty, so you sign in with that username and password; to try the Marketian account sign-in, run `sites/accounts` too and set `ACCOUNTS_URL` and the client ID/secret.

To use Postgres and Redis locally instead, set `DATABASE_URL` and `REDIS_URL` in `.env`. `npm run dev` then runs a Celery worker instead of the built-in one.

Tests: `npm test` runs the backend test suite.

## 3. Link an account and send

1. **Accounts** → type a name → **Link a new account**.
2. On the phone: WhatsApp → **Settings** → **Linked devices** → **Link a device**, then scan the QR code.
3. After a few seconds it shows **Connected**.
4. **New broadcast** → write the message → pick contacts or lists (or paste numbers) → choose the accounts to send from → check the timing → **Send**.
5. Click the campaign to watch its live status.

To message individuals, first add numbers on the **Contacts** page (or paste them straight into the composer).

> Messaging people who haven't saved your number carries a high ban risk. Only message people who expect it, honour opt-outs, keep waits long, and start with small lists.

---

## Using Evolution API instead of the built-in gateway

Evolution API is a popular, feature-rich WhatsApp server (also Baileys-based). To switch:

1. In `.env`: `WA_PROVIDER=evolution` and a long random `EVOLUTION_API_KEY`.
2. From the repo root: `docker compose --profile evolution up -d --build wa-evolution`, then `bash scripts/deploy.sh wa-backend wa-worker`
3. Link accounts again from the **Accounts** page. Each account becomes an Evolution "instance".

You can stop the built-in gateway (`docker compose stop wa-gateway`) once you no longer use it. Accounts linked under one provider don't move to the other.

> The Evolution provider (`backend/apps/whatsapp/providers/evolution.py`) follows the Evolution API v2 docs, but has not been tested against a live Evolution server. Check it with a test number first.

## Configuration

Everything is in `.env`; `.env.example` documents each value. Sending defaults (waits, breaks, daily limit, typing indicator, sender rotation) are under **Settings** in the app, and each broadcast can change them.

## Keep it safe

- WhatsApp logins (the `wa_sessions` volume, or `gateway/sessions/` locally) give full access to those accounts. Never share or commit them.
- Never expose the gateway port (3100) or Redis/Postgres to the internet. Compose keeps them on private networks; only the UI is reachable, through Caddy.
- Keep `DJANGO_SECURE=true` on the server (Caddy provides HTTPS) and use strong passwords.
- To fully unlink an account, click **Remove**, or on the phone open **Linked devices** and log the device out.

## Troubleshooting

| Problem | Fix |
|---|---|
| QR code never appears / keeps reconnecting | WhatsApp changed its protocol. Update Baileys: `cd gateway && npm install @whiskeysockets/baileys@6`, then rebuild/restart. |
| "WhatsApp service is not reachable" banner | The gateway (or Evolution) isn't running. Check `docker compose logs wa-gateway`. |
| "Not linked" | Nobody scanned the QR in time. Click **Show QR code**. |
| "Logged out from phone" | The device was removed on the phone. Click **Show QR code** and scan again. |
| Contacts stay "Not checked yet" | Checks run through a connected account. Link one and keep the worker running. |
| Campaign stuck on "Scheduled" | The worker or beat isn't running: `docker compose logs wa-worker wa-beat`. Without Docker, keep `npm run dev` open. |
