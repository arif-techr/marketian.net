#!/usr/bin/env bash
# Back up every site's PostgreSQL database (services named "<site>-db") and
# uploaded files (any service with /app/media) into backups/. Keeps 14 days.
# Schedule it daily with:  crontab -e
#   30 3 * * * /opt/sites/scripts/backup.sh >> /var/log/sites-backup.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."

stamp=$(date +%Y-%m-%d_%H%M)
mkdir -p backups

for svc in $(docker compose ps --services --status running); do
  case "$svc" in
    proxy) ;;
    *-db)
      echo "==> $svc: database"
      docker compose exec -T "$svc" sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' \
        | gzip > "backups/${svc%-db}_db_${stamp}.sql.gz"
      ;;
    *)
      if docker compose exec -T "$svc" test -d /app/media 2>/dev/null; then
        echo "==> $svc: media"
        docker compose exec -T "$svc" tar -czf - -C /app media > "backups/${svc}_media_${stamp}.tar.gz"
      fi
      ;;
  esac
done

find backups -type f -mtime +14 -delete
echo "Done: $(ls backups | wc -l) files in backups/"
