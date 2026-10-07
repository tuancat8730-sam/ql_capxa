data "google_project" "this" {}

locals {
  name = "qlda-${var.environment}"
  prod = var.environment == "prod"

  # Firebase Hosting serves the app at <site>.web.app unless a custom domain is configured.
  site_id    = "${var.project_id}-web"
  web_origin = var.web_domain != "" ? "https://${var.web_domain}" : "https://${local.site_id}.web.app"

  image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.api.repository_id}/api:${var.image_tag}"

  apis = [
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "firebase.googleapis.com",
    "firebasehosting.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}
