# terraform init -backend-config=envs/prod.backend.hcl
bucket         = "qlda-terraform-state-REPLACE-ME"
key            = "qlda/terraform.tfstate"
region         = "ap-southeast-1"
dynamodb_table = "qlda-terraform-locks"
encrypt        = true
# workspaces are stored under env:/dev/ and env:/prod/ in the same bucket
workspace_key_prefix = "env"
