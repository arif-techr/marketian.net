#!/usr/bin/env bash
# Start or update everything defined in the root docker-compose.yml.
#
#   scripts/deploy.sh             deploy all sites and the proxy
#   scripts/deploy.sh marketian   deploy only the named service(s)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -d .git ]; then
  echo "==> Pulling latest code"
  git pull --ff-only
fi

# Every included site that ships a .env.example needs its own .env.
for example in sites/*/.env.example; do
  [ -e "$example" ] || continue
  dir=$(dirname "$example")
  grep -Eq "^[[:space:]]*-[[:space:]]*$dir/docker-compose.yml" docker-compose.yml || continue
  if [ ! -f "$dir/.env" ]; then
    echo "Missing $dir/.env  (copy $dir/.env.example and fill it in)" >&2
    exit 1
  fi
done

echo "==> Building and starting"
docker compose up -d --build --remove-orphans "$@"

echo "==> Reloading proxy config"
docker compose exec -T proxy caddy reload --config /etc/caddy/Caddyfile

docker image prune -f >/dev/null
docker compose ps
