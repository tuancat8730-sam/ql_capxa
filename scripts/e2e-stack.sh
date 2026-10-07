#!/usr/bin/env bash
# Throwaway stack for the Playwright run: fresh Postgres database, moto S3, API on :8000.
# Needs Postgres (the compose `db` service from `make up`, or any server when E2E_PSQL=local, as
# in CI) and `uv`. Stays in the foreground until killed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"
DB_NAME="${E2E_DB_NAME:-qlda_e2e}"
DB_HOST="${E2E_DB_HOST:-localhost:5432}"
S3_PORT="${E2E_S3_PORT:-5001}"
S3_URL="http://localhost:${S3_PORT}"

export DATABASE_URL="postgresql+asyncpg://qlda:qlda@${DB_HOST}/${DB_NAME}"
export JWT_SECRET="e2e-secret-e2e-secret-e2e-secret-e2e"
export COOKIE_SECURE=false
export CORS_ORIGINS="http://localhost:5173"
export S3_BUCKET=qlda-documents S3_ENDPOINT_URL="$S3_URL" S3_PUBLIC_ENDPOINT_URL="$S3_URL"
export S3_ACCESS_KEY=test S3_SECRET_KEY=test AWS_REGION=ap-southeast-1
export MAIL_BACKEND=memory ALERT_REFRESH_ON_WRITE=true
export SEED_ADMIN_PASSWORD="E2e-Passw0rd!x"

cd "$ROOT/apps/api"
if [ "${E2E_PSQL:-compose}" = "local" ]; then
  export PGPASSWORD="${PGPASSWORD:-qlda}"
  PSQL=(psql -h "${DB_HOST%%:*}" -p "${DB_HOST##*:}" -U qlda -d postgres -v ON_ERROR_STOP=1)
else
  PSQL=(docker compose -f "$ROOT/docker-compose.yml" exec -T db psql -U qlda -d postgres -v ON_ERROR_STOP=1)
fi
"${PSQL[@]}" -c "DROP DATABASE IF EXISTS ${DB_NAME} WITH (FORCE)" -c "CREATE DATABASE ${DB_NAME}"

uv run alembic upgrade head
uv run python -m app.seed.run
uv run python scripts/seed_e2e.py

uv run moto_server -p "$S3_PORT" >/tmp/e2e-moto.log 2>&1 &
MOTO=$!
trap 'kill $MOTO 2>/dev/null || true' EXIT
for _ in $(seq 1 50); do curl -s "$S3_URL" >/dev/null && break; sleep 0.2; done
uv run python - <<PY
import boto3
boto3.client("s3", endpoint_url="$S3_URL", aws_access_key_id="test", aws_secret_access_key="test",
             region_name="ap-southeast-1").create_bucket(
    Bucket="qlda-documents",
    CreateBucketConfiguration={"LocationConstraint": "ap-southeast-1"})
PY

exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
