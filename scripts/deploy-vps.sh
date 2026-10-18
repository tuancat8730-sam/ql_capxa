#!/usr/bin/env bash
# Deploy to the single VPS (plain HTTP on its IP): images and web app are built here and shipped
# over SSH, since the server has 1 GB of RAM and cannot build them.
#
# Needs: ssh key access to the server (user in the docker group), docker, pnpm, rsync, openssl.
# Usage: scripts/deploy-vps.sh                      build, ship, migrate, start, health check
#        SKIP_WEB=1 scripts/deploy-vps.sh           reuse apps/web/dist as it is
#        RESTORE_DB=~/backups/qlda-dev/x.sql.gz scripts/deploy-vps.sh      load a dump (only into an
#                                                   empty database)
#        RESTORE_DOCS=~/backups/qlda-dev/documents-X scripts/deploy-vps.sh upload a documents folder
#        SEED=1 scripts/deploy-vps.sh               create the first admin (prints a temp password)
set -euo pipefail

VPS_HOST="${VPS_HOST:-deploy@103.9.78.91}"
REMOTE_DIR="${REMOTE_DIR:-qlda}"
BUCKET="${BUCKET:-qlda-documents}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TAG="$(date +%Y%m%d%H%M%S)"
PUBLIC_IP="${VPS_HOST#*@}"
SSH=(ssh -o BatchMode=yes "$VPS_HOST")
DC="cd $REMOTE_DIR && docker compose"

step() { printf '\n==> %s\n' "$*"; }
rnd() { openssl rand -hex "$1"; }

step "Build the API image ($TAG)"
docker build -t "qlda-api:$TAG" "$ROOT/apps/api"

if [ -z "${SKIP_WEB:-}" ]; then
  step "Build the web app"
  (cd "$ROOT/apps/web" && pnpm install --frozen-lockfile && pnpm build)
fi

step "Ship files"
"${SSH[@]}" "mkdir -p $REMOTE_DIR/web"
rsync -az "$ROOT/deploy/vps/docker-compose.yml" "$ROOT/deploy/vps/Caddyfile" \
  "$ROOT/deploy/vps/garage.toml" "$VPS_HOST:$REMOTE_DIR/"
rsync -az --delete "$ROOT/apps/web/dist/" "$VPS_HOST:$REMOTE_DIR/web/"
docker save "qlda-api:$TAG" | gzip | "${SSH[@]}" "gunzip | docker load"

step "Configuration (.env is created once, with random secrets)"
if ! "${SSH[@]}" "test -f $REMOTE_DIR/.env"; then
  PG="$(rnd 16)"
  "${SSH[@]}" "umask 077 && cat > $REMOTE_DIR/.env" <<EOF
PUBLIC_URL=http://$PUBLIC_IP
IMAGE_TAG=$TAG
POSTGRES_PASSWORD=$PG
DATABASE_URL=postgresql+asyncpg://qlda:$PG@db:5432/qlda
DB_POOL_SIZE=3
DB_MAX_OVERFLOW=3
JWT_SECRET=$(rnd 32)
COOKIE_SECURE=false
STORAGE_BACKEND=s3
S3_BUCKET=$BUCKET
S3_ENDPOINT_URL=http://garage:3900
S3_PUBLIC_ENDPOINT_URL=http://$PUBLIC_IP
S3_ACCESS_KEY=GK$(rnd 12)
S3_SECRET_KEY=$(rnd 32)
AWS_REGION=ap-southeast-1
GARAGE_RPC_SECRET=$(rnd 32)
APP_BASE_URL=http://$PUBLIC_IP
CORS_ORIGINS=http://$PUBLIC_IP
APP_TIMEZONE=Asia/Ho_Chi_Minh
ALERT_RUN_HOURS=6,13
AI_PROVIDER=none
MAIL_BACKEND=memory
ALERT_REFRESH_ON_WRITE=true
SEED_ADMIN_EMAIL=admin@qlda.local
EOF
  echo ".env created"
else
  "${SSH[@]}" "sed -i 's/^IMAGE_TAG=.*/IMAGE_TAG=$TAG/' $REMOTE_DIR/.env"
  echo ".env kept, image tag set to $TAG"
fi

step "Database and Garage"
"${SSH[@]}" "$DC up -d db garage"
"${SSH[@]}" "$DC exec -T db sh -c 'until pg_isready -U qlda >/dev/null 2>&1; do sleep 1; done'"

# Garage needs a one-time layout, an access key and the bucket (all idempotent)
"${SSH[@]}" "bash -s" <<EOF
set -euo pipefail
cd $REMOTE_DIR
. ./.env
# </dev/null: exec -T would otherwise swallow the rest of this script from stdin
g() { docker compose exec -T garage /garage "\$@" </dev/null; }
until g status >/dev/null 2>&1; do sleep 1; done
if g status | grep -q 'NO ROLE ASSIGNED'; then
  NODE=\$(g node id -q | cut -d@ -f1)
  g layout assign -z dc1 -c 10G "\$NODE"
  g layout apply --version 1
fi
g key info "\$S3_ACCESS_KEY" >/dev/null 2>&1 || g key import --yes -n qlda "\$S3_ACCESS_KEY" "\$S3_SECRET_KEY"
g bucket info "\$S3_BUCKET" >/dev/null 2>&1 || g bucket create "\$S3_BUCKET"
g bucket allow --read --write --owner "\$S3_BUCKET" --key "\$S3_ACCESS_KEY"
EOF

if [ -n "${RESTORE_DB:-}" ]; then
  step "Restore the database from $RESTORE_DB"
  HAS="$("${SSH[@]}" "$DC exec -T db psql -U qlda -d qlda -tAc \"select to_regclass('public.alembic_version') is not null\"")"
  if [ "$HAS" = "t" ]; then
    echo "the database already has tables; refusing to load a dump over them" >&2
    exit 1
  fi
  zcat "$RESTORE_DB" | "${SSH[@]}" "$DC exec -T db psql -U qlda -d qlda -v ON_ERROR_STOP=0 -q" 2>&1 | tail -30
fi

step "Migrate"
"${SSH[@]}" "$DC run --rm migrate"

if [ -n "${SEED:-}" ]; then
  step "Seed the first admin"
  "${SSH[@]}" "$DC run --rm seed"
fi

step "Start"
"${SSH[@]}" "$DC up -d --remove-orphans && docker image prune -f >/dev/null"

if [ -n "${RESTORE_DOCS:-}" ]; then
  step "Upload documents from $RESTORE_DOCS"
  rsync -az --delete "$RESTORE_DOCS/" "$VPS_HOST:$REMOTE_DIR/restore-docs/"
  "${SSH[@]}" "$DC run --rm -T -v \$PWD/restore-docs:/docs:ro api python -" <<'PY'
import mimetypes, os, boto3
from botocore.config import Config
s3 = boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT_URL"],
    aws_access_key_id=os.environ["S3_ACCESS_KEY"], aws_secret_access_key=os.environ["S3_SECRET_KEY"],
    region_name=os.environ["AWS_REGION"], config=Config(signature_version="s3v4", s3={"addressing_style": "path"}))
n = 0
for base, _, files in os.walk("/docs"):
    for name in files:
        path = os.path.join(base, name)
        key = os.path.relpath(path, "/docs")
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        s3.upload_file(path, os.environ["S3_BUCKET"], key, ExtraArgs={"ContentType": ctype})
        n += 1
print(f"uploaded {n} objects")
PY
  "${SSH[@]}" "rm -rf $REMOTE_DIR/restore-docs"
fi

step "Health check http://$PUBLIC_IP/api/v1/health"
for _ in $(seq 1 20); do
  if curl -fsS "http://$PUBLIC_IP/api/v1/health"; then
    printf '\nDeployed %s at http://%s\n' "$TAG" "$PUBLIC_IP"
    exit 0
  fi
  sleep 3
done
echo "the API did not answer; see: ssh $VPS_HOST 'cd $REMOTE_DIR && docker compose logs --tail=50'" >&2
exit 1
