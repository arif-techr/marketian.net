#!/bin/sh
set -e

# Wait for the database, then apply migrations before starting the app.
if [ -n "$POSTGRES_DB" ]; then
  echo "Waiting for PostgreSQL at ${POSTGRES_HOST:-db}:${POSTGRES_PORT:-5432}..."
  python - <<'EOF'
import os, time, psycopg
for attempt in range(60):
    try:
        psycopg.connect(
            dbname=os.environ["POSTGRES_DB"],
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            host=os.getenv("POSTGRES_HOST", "db"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            connect_timeout=3,
        ).close()
        break
    except psycopg.OperationalError:
        time.sleep(2)
else:
    raise SystemExit("PostgreSQL is not reachable")
EOF
fi

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi

exec "$@"
