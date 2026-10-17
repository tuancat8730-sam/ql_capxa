#!/usr/bin/env bash
# Manual deploy of the dev environment (project qlda-dev-lamdong): the same steps as the
# "Deploy (Google Cloud)" workflow, run from this machine with gcloud and firebase.
#
# Needs: gcloud (logged in, `gcloud auth login`), firebase (`firebase login`), docker, pnpm, jq.
# Usage: scripts/deploy-dev.sh            deploy HEAD
#        SKIP_WEB=1 scripts/deploy-dev.sh  only the API, worker and migration
set -euo pipefail

export PATH="$HOME/google-cloud-sdk/bin:$PATH"

PROJECT_ID="${PROJECT_ID:-qlda-dev-lamdong}"
REGION="${REGION:-asia-southeast1}"
REPOSITORY="${REPOSITORY:-qlda-dev}"
FIREBASE_SITE="${FIREBASE_SITE:-qlda-dev-lamdong-web}"
WEB_URL="${WEB_URL:-https://${FIREBASE_SITE}.web.app}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHA="$(git -C "$ROOT" rev-parse HEAD)"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/api:${SHA}"

step() { printf '\n==> %s\n' "$*"; }

if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
  echo "warning: the working tree has uncommitted changes; the image is built from them" >&2
fi

step "Deploying ${SHA:0:7} to ${PROJECT_ID}"
gcloud config set project "$PROJECT_ID" --quiet

step "Build and push the API image"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet
docker build -t "$IMAGE" "$ROOT/apps/api"
docker push "$IMAGE"

step "Run database migrations"
# a failing migration stops the script before the services change
gcloud run jobs update migrate --region "$REGION" --image "$IMAGE" --quiet
gcloud run jobs update seed --region "$REGION" --image "$IMAGE" --quiet
gcloud run jobs execute migrate --region "$REGION" --wait

step "Roll out the API and the worker"
# a revision that fails its health probe never receives traffic
gcloud run services update api --region "$REGION" --image "$IMAGE" --quiet
gcloud run services update worker --region "$REGION" --image "$IMAGE" --quiet

if [ -z "${SKIP_WEB:-}" ]; then
  step "Build the web app"
  (cd "$ROOT/apps/web" && pnpm install --frozen-lockfile && pnpm build)

  step "Publish the web app (Firebase Hosting)"
  (
    cd "$ROOT/apps/web"
    # the site id differs per environment: patch it into a copy of firebase.json
    jq --arg site "$FIREBASE_SITE" '.hosting.site = $site' firebase.json > firebase.deploy.json
    trap 'rm -f firebase.deploy.json' EXIT
    firebase deploy --only hosting --project "$PROJECT_ID" \
      --config firebase.deploy.json --non-interactive
  )
fi

step "Smoke test ${WEB_URL}/api/v1/health"
for _ in $(seq 1 12); do
  if curl -fsS "${WEB_URL}/api/v1/health"; then
    printf '\nDeployed %s\n' "${SHA:0:7}"
    exit 0
  fi
  sleep 5
done
echo "the API did not answer through ${WEB_URL}" >&2
exit 1
