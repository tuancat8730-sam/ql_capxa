# terraform apply -var-file=envs/dev.tfvars
project_id        = "qlda-dev-lamdong"
environment       = "dev"
region            = "asia-southeast1"
github_repository = "tuancat8730-sam/ql_capxa"

web_domain  = ""
alarm_email = ""

# cheap dev settings: no HA, scale to zero
db_tier              = "db-f1-micro"
db_high_availability = false
api_min_instances    = 0
api_max_instances    = 3

# e-mail is on hold: mails are only collected in memory until an SMTP provider is chosen
mail_backend = "memory"

# first apply: false (creates everything except Cloud Run), run the Deploy workflow, then true
deploy_services = true
