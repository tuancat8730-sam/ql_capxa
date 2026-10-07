# terraform workspace select dev && terraform apply -var-file=envs/dev.tfvars
region = "ap-southeast-1"

api_domain          = "api-dev.qlda.example.vn"
api_certificate_arn = "arn:aws:acm:ap-southeast-1:111111111111:certificate/replace-me"
web_domain          = ""
ses_sender          = "no-reply@qlda.example.vn"
alarm_email         = ""
github_repository   = "your-org/ql_capxa"

# cost-saving dev settings (SPEC 10.2: no Multi-AZ in dev)
nat_gateways      = 1
db_instance_class = "db.t4g.micro"
db_multi_az       = false
api_desired_count = 1
