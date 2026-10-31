#!/usr/bin/env bash
# Create a database and its own login on the shared PostgreSQL server.
#
#   scripts/create-db.sh metadata
#
# Prints the POSTGRES_* lines to paste into sites/<name>/.env. Safe to run
# again: an existing database is kept and only its password is reset.
set -euo pipefail
cd "$(dirname "$0")/.."

name="${1:-}"
if ! [[ "$name" =~ ^[a-z][a-z0-9_]*$ ]]; then
  echo "Usage: scripts/create-db.sh <name>   (lowercase letters, digits, _)" >&2
  exit 1
fi

password=$(openssl rand -hex 24)

docker compose up -d --wait postgres >/dev/null
docker compose exec -T postgres psql -U postgres -v ON_ERROR_STOP=1 -q <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$name') THEN
    CREATE ROLE "$name" LOGIN PASSWORD '$password';
  ELSE
    ALTER ROLE "$name" PASSWORD '$password';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE "$name" OWNER "$name"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$name')\gexec
REVOKE CONNECT ON DATABASE "$name" FROM PUBLIC;
SQL

cat <<EOF
Database "$name" is ready. Put these lines in sites/$name/.env:

POSTGRES_DB=$name
POSTGRES_USER=$name
POSTGRES_PASSWORD=$password
EOF
