# terraform init -backend-config=envs/dev.backend.hcl
# bucket created once by hand in the dev project (versioning on)
bucket = "qlda-dev-terraform-state"
prefix = "qlda"
