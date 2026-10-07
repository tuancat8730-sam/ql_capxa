resource "google_monitoring_notification_channel" "email" {
  count        = var.alarm_email != "" ? 1 : 0
  display_name = "${local.name} alarms"
  type         = "email"
  labels       = { email_address = var.alarm_email }
  depends_on   = [google_project_service.apis]
}

locals {
  channels = google_monitoring_notification_channel.email[*].id
}

resource "google_monitoring_alert_policy" "api_5xx" {
  display_name          = "${local.name} API 5xx"
  combiner              = "OR"
  notification_channels = local.channels

  conditions {
    display_name = "More than 5 server errors in 5 minutes"
    condition_threshold {
      filter          = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"api\" AND metric.type = \"run.googleapis.com/request_count\" AND metric.labels.response_code_class = \"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_SUM"
        cross_series_reducer = "REDUCE_SUM"
      }
    }
  }
  depends_on = [google_project_service.apis]
}

# Probes the real path users take: Firebase Hosting, then /api/** to Cloud Run.
resource "google_monitoring_uptime_check_config" "api" {
  display_name = "${local.name} API health"
  timeout      = "10s"
  period       = "300s"

  http_check {
    path           = "/api/v1/health"
    port           = 443
    use_ssl        = true
    validate_ssl   = true
    request_method = "GET"
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = replace(local.web_origin, "https://", "")
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "api_down" {
  display_name          = "${local.name} API not answering"
  combiner              = "OR"
  notification_channels = local.channels

  conditions {
    display_name = "Health check failing"
    condition_threshold {
      filter          = "metric.type = \"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.labels.check_id = \"${google_monitoring_uptime_check_config.api.uptime_check_id}\" AND resource.type = \"uptime_url\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "300s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.*"]
      }
    }
  }
}

resource "google_monitoring_alert_policy" "worker_missing" {
  display_name          = "${local.name} worker not running"
  combiner              = "OR"
  notification_channels = local.channels

  conditions {
    display_name = "No worker instance for 10 minutes"
    condition_absent {
      filter   = "resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"worker\" AND metric.type = \"run.googleapis.com/container/instance_count\""
      duration = "600s"
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MAX"
      }
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "sql_cpu" {
  display_name          = "${local.name} database CPU"
  combiner              = "OR"
  notification_channels = local.channels

  conditions {
    display_name = "CPU above 80% for 10 minutes"
    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${var.project_id}:${google_sql_database_instance.main.name}\" AND metric.type = \"cloudsql.googleapis.com/database/cpu/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.8
      duration        = "600s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }
}

resource "google_monitoring_alert_policy" "sql_disk" {
  display_name          = "${local.name} database disk"
  combiner              = "OR"
  notification_channels = local.channels

  conditions {
    display_name = "Disk above 85%"
    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${var.project_id}:${google_sql_database_instance.main.name}\" AND metric.type = \"cloudsql.googleapis.com/database/disk/utilization\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0.85
      duration        = "300s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }
}
