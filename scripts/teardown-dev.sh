#!/usr/bin/env bash
# Tear down the whole dev environment (project qlda-dev-lamdong) so Google Cloud stops charging:
# Cloud Run, Cloud SQL, the documents bucket, Artifact Registry, secrets, VPC, monitoring and the
# Firebase Hosting site all go. Everything is Terraform-managed, so `terraform destroy` removes it
# and the steps in docs/OPERATIONS_GCP.md section 2 bring it back.
#
# Kept on purpose: the Terraform state bucket (cents per month, and needed to redeploy) and the
# project itself. Set UNLINK_BILLING=1 to also detach the billing account (relink on redeploy).
#
# Before destroying, the script saves the database and the documents to BACKUP_DIR.
#
# Needs: gcloud (logged in), terraform >= 1.9.
# Usage: scripts/teardown-dev.sh                 backup, show the plan, ask, destroy
#        SKIP_BACKUP=1 scripts/teardown-dev.sh   skip the backup (data is lost for good)
#        UNLINK_BILLING=1 scripts/teardown-dev.sh
#        CONFIRM=qlda-dev-lamdong scripts/teardown-dev.sh   no prompt (non-interactive)
set -euo pipefail

export PATH="$HOME/google-cloud-sdk/bin:$PATH"

PROJECT_ID="${PROJECT_ID:-qlda-dev-lamdong}"
REGION="${REGION:-asia-southeast1}"
SQL_INSTANCE="${SQL_INSTANCE:-qlda-dev}"
SQL_DATABASE="${SQL_DATABASE:-qlda}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/qlda-dev}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT/infra/gcp"
STAMP="$(date +%Y%m%d-%H%M%S)"
DOCS_BUCKET="gs://${PROJECT_ID}-documents"

step() { printf '\n==> %s\n' "$*"; }
die() { echo "error: $*" >&2; exit 1; }

command -v gcloud >/dev/null || die "gcloud not found"
command -v terraform >/dev/null || die "terraform not found (needed to destroy what it created)"
gcloud config set project "$PROJECT_ID" --quiet

backup_database() {
  local bucket="gs://${PROJECT_ID}-tmp-backup-${STAMP}"
  local sa
  sa="$(gcloud sql instances describe "$SQL_INSTANCE" --format='value(serviceAccountEmailAddress)')"
  # Cloud SQL has a private IP only: export through a throw-away bucket, then download
  gcloud storage buckets create "$bucket" --location="$REGION" --uniform-bucket-level-access
  gcloud storage buckets add-iam-policy-binding "$bucket" \
    --member="serviceAccount:$sa" --role=roles/storage.objectAdmin >/dev/null
  gcloud sql export sql "$SQL_INSTANCE" "$bucket/${SQL_DATABASE}.sql.gz" \
    --database="$SQL_DATABASE" --offload --quiet
  gcloud storage cp "$bucket/${SQL_DATABASE}.sql.gz" "$BACKUP_DIR/${SQL_DATABASE}-${STAMP}.sql.gz"
  gcloud storage rm -r "$bucket"
  gzip -t "$BACKUP_DIR/${SQL_DATABASE}-${STAMP}.sql.gz"
  echo "database saved: $BACKUP_DIR/${SQL_DATABASE}-${STAMP}.sql.gz"
}

backup_documents() {
  if ! gcloud storage buckets describe "$DOCS_BUCKET" >/dev/null 2>&1; then
    echo "no documents bucket, skipped"
    return
  fi
  mkdir -p "$BACKUP_DIR/documents-${STAMP}"
  # rsync keeps the object paths (the database refers to documents by them); `cp -r bucket/**`
  # flattens them and drops files with the same name. Current versions only: the bucket is
  # force-destroyed, old versions go with it.
  gcloud storage rsync -r "$DOCS_BUCKET" "$BACKUP_DIR/documents-${STAMP}"
  echo "documents saved: $BACKUP_DIR/documents-${STAMP}"
}

if [ -z "${SKIP_BACKUP:-}" ]; then
  mkdir -p "$BACKUP_DIR"
  step "Backup of the database"
  if gcloud sql instances describe "$SQL_INSTANCE" >/dev/null 2>&1; then
    backup_database
  else
    echo "no Cloud SQL instance ${SQL_INSTANCE}, skipped"
  fi
  step "Backup of the documents"
  backup_documents
else
  echo "warning: SKIP_BACKUP is set, the database and the documents will not be saved" >&2
fi

step "Terraform plan (destroy)"
cd "$TF_DIR"
terraform init -input=false -backend-config=envs/dev.backend.hcl
terraform plan -destroy -input=false -var-file=envs/dev.tfvars

step "Confirm"
echo "This deletes EVERYTHING in ${PROJECT_ID}: database, documents, services, images, secrets."
if [ "${CONFIRM:-}" != "$PROJECT_ID" ]; then
  read -r -p "Type the project id (${PROJECT_ID}) to continue: " answer
  [ "$answer" = "$PROJECT_ID" ] || die "not confirmed, nothing was destroyed"
fi

step "Terraform destroy"
destroy() { terraform destroy -input=false -auto-approve -var-file=envs/dev.tfvars; }
if ! destroy; then
  # the private-services VPC peering often fails while Cloud SQL is still releasing it
  echo "destroy failed; waiting 120s for Cloud SQL to release its network, then retrying once" >&2
  sleep 120
  destroy
fi

step "What is left in ${PROJECT_ID}"
gcloud run services list --region "$REGION" --format='value(name)' || true
gcloud sql instances list --format='value(name)' || true
gcloud storage buckets list --format='value(name)' || true
gcloud artifacts repositories list --location "$REGION" --format='value(name)' || true
gcloud compute addresses list --format='value(name)' || true
echo "(only the Terraform state bucket should appear above)"

if [ -n "${UNLINK_BILLING:-}" ]; then
  step "Unlink billing"
  ACCOUNT="$(gcloud billing projects describe "$PROJECT_ID" --format='value(billingAccountName)' | sed 's#.*/##')"
  if [ -n "$ACCOUNT" ]; then
    mkdir -p "$BACKUP_DIR"
    echo "$ACCOUNT" >"$BACKUP_DIR/billing-account.txt"
    gcloud billing projects unlink "$PROJECT_ID"
    echo "unlinked ${ACCOUNT}; relink with: gcloud billing projects link ${PROJECT_ID} --billing-account=${ACCOUNT}"
  else
    echo "billing is not linked, nothing to do"
  fi
fi

cat <<EOF

Done. To bring the environment back (docs/OPERATIONS_GCP.md section 2, steps 3 to 8):
  1. (only if you unlinked billing) gcloud billing projects link ${PROJECT_ID} --billing-account=<id>
  2. terraform apply -var-file=envs/dev.tfvars -var deploy_services=false   (in infra/gcp)
  3. build and push the first image, terraform apply again, then scripts/deploy-dev.sh
  4. restore the data: the database from ${BACKUP_DIR}/${SQL_DATABASE}-${STAMP}.sql.gz
     and the documents from ${BACKUP_DIR}/documents-${STAMP}
NOTE: Cloud SQL keeps a deleted instance name reserved for a while; if the apply fails with
"instance name ... was recently used", wait (up to a week) or change the name in infra/gcp/locals.tf.
EOF
