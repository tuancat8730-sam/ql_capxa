resource "google_compute_network" "main" {
  name                    = local.name
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

# Cloud Run reaches Cloud SQL's private address through Direct VPC egress on this subnet.
resource "google_compute_subnetwork" "run" {
  name                     = "${local.name}-run"
  network                  = google_compute_network.main.id
  region                   = var.region
  ip_cidr_range            = "10.30.0.0/24"
  private_ip_google_access = true
}

# Private services access: the range Google uses for Cloud SQL's private IP.
resource "google_compute_global_address" "sql_range" {
  name          = "${local.name}-sql-range"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 20
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "sql" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.sql_range.name]
  depends_on              = [google_project_service.apis]
}
