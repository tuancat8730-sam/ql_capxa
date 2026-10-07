# terraform workspace select prod && terraform apply -var-file=envs/prod.tfvars
region = "ap-southeast-1"

api_domain          = "api.qlda.example.vn"
api_certificate_arn = "arn:aws:acm:ap-southeast-1:111111111111:certificate/replace-me"
web_domain          = "qlda.example.vn"
web_certificate_arn = "arn:aws:acm:us-east-1:111111111111:certificate/replace-me"
route53_zone_id     = "ZREPLACEME"
ses_sender          = "no-reply@qlda.example.vn"
alarm_email         = "ops@example.vn"
github_repository   = "your-org/ql_capxa"

nat_gateways                = 2
db_instance_class           = "db.t4g.small"
db_multi_az                 = true
api_desired_count           = 2
create_github_oidc_provider = false
