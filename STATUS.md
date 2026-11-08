# Where we left off (9 Nov 2026)

## Start everything again (Docker, on this PC)

1. Open **Docker Desktop** and wait until it says it's running.
2. In Git Bash, from this folder:
   ```bash
   CADDYFILE=Caddyfile.local docker compose up -d
   ```
3. Open the sites (data and logins are kept in Docker volumes):

| Site | Address | Sign in |
|---|---|---|
| Portfolio | http://marketian.localhost | `/admin/`: admin / marketian-local-123 |
| Marketian account | http://accounts.localhost | demo@marketian.net / marketian-local-123 |
| Metadata | http://metadata.localhost | Continue with Marketian account |
| WA Broadcaster | http://wa.localhost | Continue with Marketian account (admin / marketian-local-123 by username) |
| Links | http://links.localhost | Continue with Marketian account |

Stop with `docker compose down`. The local `.env` files and passwords above are for this PC only.

## Done

- Portfolio with Marketing tools page, menu button and home section
- Marketian account (one sign-in for every product)
- WA Broadcaster at wa.marketian.net (moved in from its own repo)
- **Links** at links.marketian.net (new, all 47 tests pass):
  - short links: random or custom names, click stats (per day, unique, referrers, devices, browsers, systems),
    QR codes (PNG/SVG), UTM builder, passwords, expiry dates, turn off, edit, delete, search, CSV export,
    `+` preview, bots and link previews not counted, daily limit per person
  - Linktree-style bio pages at /@name: photo, bio, buttons, section titles, YouTube videos, reorder,
    hide, schedule, social icons, 6 themes + own colours, 5 button styles, live phone preview,
    page views and clicks per button, email sign-ups with CSV export, QR code, sensitive-content warning

## Not finished yet (next session)

- Links: check it in the browser end to end in Docker (it builds, starts and answers; not clicked through yet)
- Add Links to the portfolio's Marketing tools on this PC: in http://marketian.localhost/admin/ → Tools → Add
  (name Links, link http://links.localhost). New installs get it automatically from `seed_demo`.
- README: add Links (tree, first-time setup steps, local addresses table)
- Metadata: decide what it does (it's still an empty dashboard)
- Push to GitHub (`git push`) and deploy to the VPS (README, "Hosting on Hostinger VPS")
