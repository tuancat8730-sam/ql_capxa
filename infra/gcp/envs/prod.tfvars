# terraform apply -var-file=envs/prod.tfvars
project_id        = "qlda-prod" # replace with the real project id
environment       = "prod"
region            = "asia-southeast1"
github_repository = "tuancat8730-sam/ql_capxa"

web_domain  = "qlda.example.vn"
alarm_email = "ops@example.vn"

db_tier              = "db-custom-1-3840"
db_disk_gb           = 20
db_high_availability = true
api_min_instances    = 1
api_max_instances    = 5
db_pool_size         = 4
db_max_overflow      = 2

mail_backend    = "memory"
deploy_services = true
