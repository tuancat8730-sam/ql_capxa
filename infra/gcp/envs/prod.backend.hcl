# terraform init -backend-config=envs/prod.backend.hcl
# bucket created once by hand in the prod project (versioning on)
bucket = "qlda-prod-terraform-state"
prefix = "qlda"
