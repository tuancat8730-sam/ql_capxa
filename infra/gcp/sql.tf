resource "random_password" "db" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "main" {
  name                = local.name
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = local.prod

  settings {
    tier              = var.db_tier
    edition           = "ENTERPRISE"
    availability_type = var.db_high_availability ? "REGIONAL" : "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = var.db_disk_gb
    disk_autoresize   = true

    ip_configuration {
      ipv4_enabled    = false
      private_network = google_compute_network.main.id
      ssl_mode        = "ENCRYPTED_ONLY"
    }

    # SPEC 4.17: automatic backups kept 7 days, plus point-in-time recovery
    backup_configuration {
      enabled                        = true
      start_time                     = "17:00" # 00:00 in Vietnam
      point_in_time_recovery_enabled = true
      transaction_log_retention_days = 7
      backup_retention_settings {
        retained_backups = 7
      }
    }

    maintenance_window {
      day  = 7
      hour = 18
    }
  }

  depends_on = [google_service_networking_connection.sql]
}

resource "google_sql_database" "app" {
  name     = "qlda"
  instance = google_sql_database_instance.main.name
}

# The application user may create the pg_trgm and unaccent extensions (migration 0004).
resource "google_sql_user" "app" {
  name     = "qlda"
  instance = google_sql_database_instance.main.name
  password = random_password.db.result
}
