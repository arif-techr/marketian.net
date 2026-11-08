#!/usr/bin/env bash
# Back up everything on the server that can't be rebuilt from git into backups/.
# Keeps 14 days.
#   - each site's own PostgreSQL database (services named "<site>-db")
#   - every database on the shared PostgreSQL server (service "postgres") and its logins
#   - uploaded files (any service with /app/media)
#   - sign-in keys (any service with /app/keys): losing the accounts key signs
#     everyone out of every product
#   - WhatsApp logins (any service with /app/sessions), so numbers don't need re-scanning
# Schedule it daily with:  crontab -e
#   30 3 * * * /opt/sites/scripts/backup.sh >> /var/log/sites-backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
# Git Bash on Windows would rewrite container paths like /app/media; Linux ignores this.
export MSYS_NO_PATHCONV=1

# Backups hold passwords and private keys: only root may read them.
umask 077
stamp=$(date +%Y-%m-%d_%H%M)
mkdir -p backups
chmod 700 backups

for svc in $(docker compose ps --services --status running); do
  case "$svc" in
    # Workers share their site's uploads volume, which is backed up from the site itself.
    proxy | *-worker | *-beat) ;;
    postgres)
      echo "==> $svc: logins"
      docker compose exec -T postgres pg_dumpall -U postgres --roles-only \
        | gzip > "backups/shared_roles_${stamp}.sql.gz"
      for db in $(docker compose exec -T postgres psql -U postgres -Atc \
          "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname <> 'postgres'"); do
        echo "==> $svc: database $db"
        docker compose exec -T postgres pg_dump -U postgres --clean --if-exists "$db" \
          | gzip > "backups/shared_${db}_db_${stamp}.sql.gz"
      done
      ;;
    *-db)
      echo "==> $svc: database"
      docker compose exec -T "$svc" sh -c 'pg_dump -U "$POSTGRES_USER" --clean --if-exists "$POSTGRES_DB"' \
        | gzip > "backups/${svc%-db}_db_${stamp}.sql.gz"
      ;;
    *)
      for dir in media keys sessions; do
        if docker compose exec -T "$svc" test -d "/app/$dir" 2>/dev/null; then
          echo "==> $svc: $dir"
          docker compose exec -T "$svc" tar -czf - -C /app "$dir" > "backups/${svc}_${dir}_${stamp}.tar.gz"
        fi
      done
      ;;
  esac
done

find backups -type f -mtime +14 -delete
echo "Done: $(ls backups | wc -l) files in backups/"
