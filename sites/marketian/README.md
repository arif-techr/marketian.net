# Marketian — Portfolio Website

Personal portfolio for **marketian.net** (and **marketain.net**, which redirects to it), built with Python / Django.

**Pages:** Home · About · Services · Portfolio (with case-study pages) · Contact · custom 404
**Features:** dark/light theme, mobile-friendly, contact form that emails you and stores every message in the admin, a full mail system (branded HTML emails, signatures, reply templates, auto-reply, bulk send, sent log), spam protection (honeypot + rate limit), sitemap.xml and robots.txt for Google, all content editable from `/admin/` without touching code.

---

## 1. Run it on your computer

This site lives in `sites/marketian/` of the server repo. Run these commands from this folder:

```bash
python -m venv ../../.venv           # one virtualenv at the repo root, shared by Python sites
..\..\.venv\Scripts\activate         # Windows   (macOS/Linux: source ../../.venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo           # adds starter content you can edit
python manage.py createsuperuser     # your admin login
python manage.py runserver
```

Open http://127.0.0.1:8000 for the site and http://127.0.0.1:8000/admin/ to edit it.
Locally the site uses SQLite and prints emails in the terminal instead of sending them.

## 2. Make it yours (in `/admin/`)

| Admin section | What it controls |
|---|---|
| **Site profile** | Your name, role, tagline, photo, CV, story, email, phone, WhatsApp, social links, stats |
| **Services** | Service cards (icon, summary, feature list) |
| **Projects** | Portfolio items: cover image, challenge, solution, results, tags, "featured" on home page |
| **Skills / Experience / Testimonials** | About page and home page sections |
| **Contact messages** | Every message visitors send you |

Delete or replace the sample projects and testimonials before going live — they are placeholders.

## 3. Put it online

This site runs in Docker behind the server's shared proxy. The full Hostinger VPS guide is in the [repo README](../../README.md). The parts specific to this site:

| File | Purpose |
|---|---|
| `docker-compose.yml` | The app (service `marketian`, port 8000) and its private PostgreSQL (`marketian-db`). Included by the root `docker-compose.yml` |
| `Dockerfile`, `docker/entrypoint.sh` | Builds the image. On start it waits for the database and runs migrations |
| `.env` | Copy from `.env.example`. Uncomment the `POSTGRES_*` lines and set a strong password |

Useful commands (run from the repo root on the server):

```bash
docker compose exec marketian python manage.py createsuperuser
docker compose exec marketian python manage.py seed_demo   # optional starter content
docker compose logs -f marketian
```

**Moving content from your computer into the server:** locally run
`python manage.py dumpdata --exclude contenttypes --exclude auth.permission > data.json`, upload `data.json`, then on the server:

```bash
docker compose cp data.json marketian:/tmp/data.json
docker compose exec marketian python manage.py loaddata /tmp/data.json
docker compose cp media/. marketian:/app/media/      # uploaded photos and CV
```

The cPanel files (`passenger_wsgi.py`, `Procfile`) are kept in case you ever host it without Docker.

## 4. Mail system

Everything lives in the admin under **Mail** and **Contact messages**.

| What | Where |
|---|---|
| **New message alert** | When a visitor sends the form, you get a branded email at `CONTACT_RECIPIENTS` with a link to reply from the admin. |
| **Automatic reply** | The visitor gets an instant "thanks, I'll reply within 24h" email. Edit or switch it off in **Mail → Email templates** (purpose = *Automatic reply*). |
| **Reply with a template** | Open a contact message → **✉ Reply with template**. Pick a template, edit, **Preview**, **Send**. Their original message is quoted underneath. |
| **Compose to anyone** | **Mail → Sent emails → Compose email**. |
| **Bulk send** | In **Contact messages**, tick several people → action **✉ Send a template email to selected**. Each person gets a personalised copy. |
| **Signatures** | **Mail → Email signatures**: sign-off, name, title, photo, phone, links and colour, with a live preview. Copy the preview into Gmail → Settings → Signature to use it there too. |
| **Templates** | **Mail → Email templates**. Use placeholders like `{{ first_name }}`, `{{ subject }}`, `{{ my_name }}`; the full list is shown on every compose screen. Actions: *send a test to myself*, *duplicate*. |
| **Sent log** | **Mail → Sent emails**: every email with its preview, status, and error message if it failed. |

Messages are always saved, even if email sending fails. To fix failures, check the `EMAIL_*` values in `.env`. Tip: use the same mailbox for `EMAIL_HOST_USER` and `DEFAULT_FROM_EMAIL` (for example `hello@marketian.net`) so emails don't land in spam.

## Tests

```bash
python manage.py test core mailer
```
