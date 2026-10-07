data "aws_caller_identity" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  env  = terraform.workspace
  name = "qlda-${local.env}"
  azs  = slice(data.aws_availability_zones.available.names, 0, 2)
  prod = local.env == "prod"

  web_origin = var.web_domain != "" ? "https://${var.web_domain}" : "https://${aws_cloudfront_distribution.web.domain_name}"
}

# Only the two workspaces of SPEC 10.2 exist.
check "workspace" {
  assert {
    condition     = contains(["dev", "prod"], terraform.workspace)
    error_message = "Select the dev or prod workspace: terraform workspace select dev"
  }
}
