output "web_url" {
  value = local.web_origin
}

output "firebase_site_id" {
  description = "FIREBASE_SITE of the GitHub environment"
  value       = google_firebase_hosting_site.web.site_id
}

output "artifact_repository" {
  description = "Docker repository to push the API image to"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.api.repository_id}"
}

output "documents_bucket" {
  value = google_storage_bucket.documents.name
}

output "cloud_sql_instance" {
  value = google_sql_database_instance.main.connection_name
}

output "workload_identity_provider" {
  description = "GCP_WORKLOAD_IDENTITY_PROVIDER of the GitHub environment"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_service_account" {
  description = "GCP_DEPLOY_SERVICE_ACCOUNT of the GitHub environment"
  value       = google_service_account.deploy.email
}

output "app_service_account" {
  value = google_service_account.app.email
}
