---
name: marketian-new-product
description: Use when adding a new SaaS product or site to the Marketian server (a new sites/<name>, a new *.marketian.net subdomain), from copying the template to its first sign-in and deploy.
---

# Adding a new Marketian product

A product is a Django site in `sites/<name>`, served at `<name>.marketian.net`, signing in with the
Marketian account, with its own database on the shared PostgreSQL. **Copy `sites/links`**: it is the
most complete template (sign-in, admin sign-in, production guard, htmx, Dockerfile, entrypoint, tests).
`sites/_template` is only for a plain static site.

Read `Project Planning/03-decisions.md` first. Going against a decision (own database server, own
login, a public port, a JS build step) needs the user's yes.

## Steps (each has a "done when")

1. **Copy and rename.** `cp -r sites/links sites/<name>`, then remove Links' own apps (`bio`,
   `shortener`) and keep `product/`, `dashboard/`, `templates/base.html`, `templates/admin/`,
   `static/js/vendor/htmx-*.min.js`, `docker/entrypoint.sh`, `Dockerfile`. Rename the image
   (`image: <name>-web`), the service, the volume, `PRODUCT_NAME`, `ALLOWED_HOSTS`,
   `CSRF_TRUSTED_ORIGINS`. Delete `__pycache__`, `db.sqlite3`, `media/`.
   *Done when* `grep -ri "links" sites/<name>` only finds things you meant to keep.
2. **Keep the shared pieces identical.** `dashboard/admin_signin.py` must stay byte-identical to the
   copies in links, metadata and tracking (`diff -q`). Fix it in all of them or none.
3. **Settings.** Keep `SOCIALACCOUNT_ONLY = True`, the `marketian` OpenID Connect app pointing at
   `{ACCOUNTS_URL}/o` with PKCE, `ADMIN_EMAILS`, and the production guard (`SECRET_KEY` placeholder
   refused when `DEBUG=False`). Every page with user data uses `@login_required`.
4. **Compose and proxy.**
   - `sites/<name>/docker-compose.yml`: networks `shared-db` + `web-proxy`, **no `ports:`**,
     `POSTGRES_HOST: postgres`, a memory limit.
   - Root `docker-compose.yml`: add `- sites/<name>/docker-compose.yml` under `include:`
     (`deploy.sh` only checks `.env` files of included sites).
   - `proxy/Caddyfile` **and** `proxy/Caddyfile.local`: a block `<name>.marketian.net` →
     `reverse_proxy <name>:8000`. DNS needs nothing: `*.marketian.net` is a wildcard.
   *Done when* `docker compose config -q` passes.
5. **`.env.example`.** Every setting the code reads, with a comment saying where its value comes from
   (see `sites/links/.env.example`). Never commit `.env`.
6. **Tests first.** Start from `sites/links/dashboard/tests.py` (sign-in redirect, admin sign-in).
   Run `python manage.py test`, `check`, `makemigrations --check`.
7. **Backups.** Uploads go in `/app/media`, keys in `/app/keys`: `scripts/backup.sh` finds those by
   path, so use them, or extend the script.
8. **Docs.** Add the site to `README.md` (tree, diagram, steps 4b/4g), `STATUS.md` and
   `Project Planning/02-status.md` (site table + change log).

## Going live (on the server, with the user's go-ahead; see marketian-deploy)

```bash
cd /opt/sites && git pull --ff-only
bash scripts/create-db.sh <name>                     # 3 POSTGRES_* lines
docker compose exec accounts python manage.py register_product <name> https://<name>.marketian.net
cp sites/<name>/.env.example sites/<name>/.env && chmod 600 sites/<name>/.env
nano sites/<name>/.env                               # SECRET_KEY, POSTGRES_*, MARKETIAN_CLIENT_*, ADMIN_EMAILS
bash scripts/deploy.sh <name> proxy
```
*Done when* `https://<name>.marketian.net` loads with a real certificate and a Marketian sign-in
round trip works. The product shows up on accounts.marketian.net by itself.
