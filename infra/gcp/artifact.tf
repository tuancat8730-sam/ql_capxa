resource "google_artifact_registry_repository" "api" {
  repository_id = local.name
  location      = var.region
  format        = "DOCKER"
  description   = "API image of ${local.name}"

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 30
    }
  }

  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      older_than = "2592000s" # 30 days
    }
  }

  depends_on = [google_project_service.apis]
}
