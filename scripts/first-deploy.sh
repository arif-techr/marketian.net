#!/usr/bin/env bash
# First deploy on a fresh VPS, after server-setup.sh. Run as root from /opt/sites:
#   nohup bash scripts/first-deploy.sh > /root/first-deploy.log 2>&1 &
# Creates every .env from its .env.example with random secrets, creates the product
# databases, starts everything, and connects metadata/links/wa to the accounts site.
# Email and GitHub sign-in values are left as placeholders: fill them in afterwards.
# Safe to stop and rerun only before the first successful run (it regenerates secrets).
set -euo pipefail
cd "$(dirname "$0")/.."

# New random passwords on a server that already has databases would lock every site out of its data.
if docker volume inspect marketian-net_infra-pgdata >/dev/null 2>&1 && [ "${FORCE:-}" != "1" ]; then
  echo "This server already has databases: use scripts/deploy.sh to update it." >&2
  echo "(Only on a server whose data you mean to throw away: FORCE=1 bash scripts/first-deploy.sh)" >&2
  exit 1
fi

r() { openssl rand -hex 24; }
setv() {  # setv FILE KEY VALUE
  if grep -q "^$2=" "$1"; then sed -i "s|^$2=.*|$2=$3|" "$1"; else echo "$2=$3" >> "$1"; fi
}

echo "==> .env files"
for d in infra sites/marketian sites/accounts sites/metadata sites/links sites/wa; do
  [ -f "$d/.env" ] || cp "$d/.env.example" "$d/.env"
  chmod 600 "$d/.env"
done
setv infra/.env POSTGRES_PASSWORD "$(r)"
setv sites/marketian/.env SECRET_KEY "$(r)$(r)"
setv sites/marketian/.env POSTGRES_PASSWORD "$(r)"
setv sites/wa/.env DJANGO_SECRET_KEY "$(r)$(r)"
setv sites/wa/.env POSTGRES_PASSWORD "$(r)"
setv sites/wa/.env GATEWAY_API_KEY "$(r)"
setv sites/wa/.env EVOLUTION_API_KEY "$(r)"
setv sites/wa/.env ADMIN_PASSWORD "$(r)"

echo "==> Product databases on the shared PostgreSQL"
for p in accounts metadata links; do
  setv "sites/$p/.env" SECRET_KEY "$(r)$(r)"
  pw=$(bash scripts/create-db.sh "$p" | sed -n 's/^POSTGRES_PASSWORD=//p')
  [ -n "$pw" ] || { echo "create-db.sh $p failed" >&2; exit 1; }
  setv "sites/$p/.env" POSTGRES_PASSWORD "$pw"
done

echo "==> Building and starting everything"
bash scripts/deploy.sh

echo "==> Connecting products to the Marketian account"
for p in metadata links wa; do
  out=$(docker compose exec -T accounts python manage.py register_product "$p" "https://$p.marketian.net" | tr -d '\r')
  for k in MARKETIAN_CLIENT_ID MARKETIAN_CLIENT_SECRET; do
    v=$(printf '%s\n' "$out" | sed -n "s/^$k=//p")
    [ -n "$v" ] || { echo "register_product $p printed no $k" >&2; exit 1; }
    setv "sites/$p/.env" "$k" "$v"
  done
done
docker compose up -d metadata links wa-backend wa-worker wa-beat

docker compose ps
echo "FIRST-DEPLOY-OK"
