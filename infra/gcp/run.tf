locals {
  app_env = {
    APP_TIMEZONE     = "Asia/Ho_Chi_Minh"
    STORAGE_BACKEND  = "gcs"
    GCS_BUCKET       = google_storage_bucket.documents.name
    GCP_PROJECT      = var.project_id
    GCS_SIGNER_EMAIL = google_service_account.app.email
    # Firebase Hosting forwards only a cookie called __session to Cloud Run
    REFRESH_COOKIE_NAME    = "__session"
    COOKIE_SECURE          = "true"
    CORS_ORIGINS           = local.web_origin
    APP_BASE_URL           = local.web_origin
    MAIL_BACKEND           = var.mail_backend
    ALERT_REFRESH_ON_WRITE = "true"
    DB_POOL_SIZE           = tostring(var.db_pool_size)
    DB_MAX_OVERFLOW        = tostring(var.db_max_overflow)
  }

  app_secrets = {
    DATABASE_URL = google_secret_manager_secret.database_url.secret_id
    JWT_SECRET   = google_secret_manager_secret.jwt.secret_id
  }
}

# --- API ------------------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "api" {
  count    = var.deploy_services ? 1 : 0
  name     = "api"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL" # Firebase Hosting calls it; the API authenticates every request itself

  deletion_protection = local.prod

  template {
    service_account = google_service_account.app.email

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = google_compute_network.main.name
        subnetwork = google_compute_subnetwork.run.name
      }
    }

    containers {
      image   = local.image
      command = ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = var.api_cpu
          memory = var.api_memory
        }
        # CPU stays allocated between requests: the engine re-run after a write is a background task
        cpu_idle          = false
        startup_cpu_boost = true
      }

      dynamic "env" {
        for_each = local.app_env
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = local.app_secrets
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      startup_probe {
        http_get {
          path = "/api/v1/health"
        }
        period_seconds    = 5
        timeout_seconds   = 3
        failure_threshold = 12
      }
      liveness_probe {
        http_get {
          path = "/api/v1/health"
        }
        period_seconds = 30
      }
    }
  }

  # The Deploy workflow rolls out new revisions; Terraform must not roll them back.
  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [
    google_secret_manager_secret_version.jwt,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_iam_member.app_jwt,
    google_secret_manager_secret_iam_member.app_database_url,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  count    = var.deploy_services ? 1 : 0
  name     = google_cloud_run_v2_service.api[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --- worker: exactly one instance, always running (the scheduler would otherwise run twice) ---

resource "google_cloud_run_v2_service" "worker" {
  count    = var.deploy_services ? 1 : 0
  name     = "worker"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  deletion_protection = local.prod

  template {
    service_account = google_service_account.app.email

    scaling {
      min_instance_count = 1
      max_instance_count = 1
    }

    vpc_access {
      egress = "PRIVATE_RANGES_ONLY"
      network_interfaces {
        network    = google_compute_network.main.name
        subnetwork = google_compute_subnetwork.run.name
      }
    }

    containers {
      image   = local.image
      command = ["python", "-m", "app.worker"]

      # the worker answers 200 on $PORT so that Cloud Run keeps it running
      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
        cpu_idle = false
      }

      dynamic "env" {
        for_each = local.app_env
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = local.app_secrets
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      startup_probe {
        tcp_socket {
          port = 8080
        }
        period_seconds    = 5
        failure_threshold = 12
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].containers[0].image, client, client_version]
  }

  depends_on = [
    google_secret_manager_secret_version.jwt,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_iam_member.app_jwt,
    google_secret_manager_secret_iam_member.app_database_url,
  ]
}

# --- one-off jobs: `migrate` runs in every deploy before the services move; `seed` makes the first
# admin and the reference data (idempotent) and is run by hand once ------------------------

locals {
  jobs = {
    migrate = ["alembic", "upgrade", "head"]
    seed    = ["python", "-m", "app.seed.run"]
  }
}

resource "google_cloud_run_v2_job" "job" {
  for_each = var.deploy_services ? local.jobs : {}
  name     = each.key
  location = var.region

  deletion_protection = local.prod

  template {
    template {
      service_account = google_service_account.app.email
      max_retries     = 0
      timeout         = "600s"

      vpc_access {
        egress = "PRIVATE_RANGES_ONLY"
        network_interfaces {
          network    = google_compute_network.main.name
          subnetwork = google_compute_subnetwork.run.name
        }
      }

      containers {
        image   = local.image
        command = each.value

        dynamic "env" {
          for_each = local.app_env
          content {
            name  = env.key
            value = env.value
          }
        }
        dynamic "env" {
          for_each = local.app_secrets
          content {
            name = env.key
            value_source {
              secret_key_ref {
                secret  = env.value
                version = "latest"
              }
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [template[0].template[0].containers[0].image, client, client_version]
  }

  depends_on = [
    google_secret_manager_secret_version.jwt,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_iam_member.app_jwt,
    google_secret_manager_secret_iam_member.app_database_url,
  ]
}
