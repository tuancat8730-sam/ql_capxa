# Documents (SPEC section 9): private, versioned, no public access.
resource "google_storage_bucket" "documents" {
  name                        = "${var.project_id}-documents"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = !local.prod

  versioning {
    enabled = true
  }

  # old versions are kept for a year, then removed
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 365
      with_state                 = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }

  # Browsers upload and download straight to the bucket with signed URLs.
  cors {
    origin          = [local.web_origin]
    method          = ["GET", "PUT", "HEAD"]
    response_header = ["Content-Type", "Content-Disposition", "ETag"]
    max_age_seconds = 3000
  }

  depends_on = [google_project_service.apis]
}
