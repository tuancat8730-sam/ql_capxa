# The web app is served by Firebase Hosting: static files from its CDN, and /api/** rewritten to
# the Cloud Run service (see apps/web/firebase.json), so the browser only ever talks to one host.

resource "google_firebase_project" "this" {
  provider   = google-beta
  project    = var.project_id
  depends_on = [google_project_service.apis]
}

resource "google_firebase_hosting_site" "web" {
  provider   = google-beta
  project    = var.project_id
  site_id    = local.site_id
  depends_on = [google_firebase_project.this]
}

resource "google_firebase_hosting_custom_domain" "web" {
  provider              = google-beta
  count                 = var.web_domain != "" ? 1 : 0
  project               = var.project_id
  site_id               = google_firebase_hosting_site.web.site_id
  custom_domain         = var.web_domain
  wait_dns_verification = false
}
