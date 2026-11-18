---
name: marketian-deploy
description: Use when actually deploying, updating, restarting or rolling back a Marketian site on the live Hostinger VPS (SSH, scripts/deploy.sh, server .env changes). Run marketian-predeploy-check first.
---

# Deploying to the live Marketian server

Live server: Hostinger VPS `201.18.200.226`, repo at `/opt/sites`, everything in one Docker Compose
project (`marketian-net`). It serves real users: **ask the user before any command that changes the
server**, and say exactly what will restart.

## Never
- Never run `scripts/first-deploy.sh` on the live server. It generates new passwords and would lock
  every site out of its data (it refuses unless `FORCE=1`; never pass that).
- Never start the proxy with `CADDYFILE=` set (that caused untrusted certificates on 17 Nov 2026).
- Never edit code on the server. Change it on the PC, commit, push, then pull on the server.
- Never print a whole `.env` into the chat. Use `grep KEY file` for the one line you need.
- Never `docker compose down -v` or remove volumes (databases, uploads, sign-in keys, WA sessions).

## Steps
1. On the PC: `marketian-predeploy-check` passes, `git status` clean, pushed to `main`.
2. Read `STATUS.md` → "Before the next deploy". Do those steps first, or say they're pending.
3. Before a big change: ask the user to take a Hostinger snapshot (hPanel → VPS → Snapshots) and/or
   run `bash scripts/backup.sh`.
4. Connect: `ssh -i ~/.ssh/marketian_vps root@201.18.200.226` (the key exists only on the user's PC).
5. Deploy only what changed:
   ```bash
   cd /opt/sites && bash scripts/deploy.sh <service> [<service> ...]   # e.g. accounts links
   cd /opt/sites && bash scripts/deploy.sh                             # everything
   ```
   `deploy.sh` does `git pull --ff-only`, checks each included site has a `.env`, builds, starts,
   reloads Caddy, prunes images, and prints `docker compose ps`. Migrations run in each container's
   entrypoint at start.
6. New `.env` setting: add it on the server with `nano sites/<site>/.env` **before** deploying the code
   that needs it, then deploy that service. `chmod 600` stays on `.env` files.

## Check after
- `docker compose ps`: all healthy. `docker compose logs --since 5m <service>`: no errors.
- `curl -sI https://<site>.marketian.net` answers; the certificate is Let's Encrypt.
- A sign-in round trip through accounts works on one product.
- Update `Project Planning/02-status.md` (Deployment + change log) and `STATUS.md`: commit hash
  deployed, what changed, anything left to do.

## Rollback
```bash
cd /opt/sites && git log --oneline -5
git checkout <previous-commit> -- sites/<site>     # or: git revert on the PC and push
docker compose up -d --build <service>
```
A migration that already ran is not undone by this: check `python manage.py showmigrations` and
ask the user before `migrate <app> <previous>` (it can delete data). Last resort: restore the
Hostinger snapshot or the files in `backups/`.
