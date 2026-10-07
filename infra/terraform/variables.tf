variable "region" {
  description = "AWS region of the whole stack"
  type        = string
  default     = "ap-southeast-1"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "nat_gateways" {
  description = "1 is enough for dev; use 2 (one per AZ) in prod"
  type        = number
  default     = 1

  validation {
    condition     = contains([1, 2], var.nat_gateways)
    error_message = "nat_gateways must be 1 or 2."
  }
}

variable "api_certificate_arn" {
  description = "ACM certificate (same region) for the API load balancer"
  type        = string
}

variable "api_domain" {
  description = "Host name of the API load balancer (its certificate must match). CloudFront reaches the API through it; the browser only ever calls /api on the web host."
  type        = string
}

variable "web_domain" {
  description = "Public host name of the web app; empty serves it from the CloudFront domain"
  type        = string
  default     = ""
}

variable "web_certificate_arn" {
  description = "ACM certificate in us-east-1 for web_domain (required when web_domain is set)"
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Hosted zone that holds api_domain and web_domain; empty skips the DNS records"
  type        = string
  default     = ""
}

variable "ses_sender" {
  description = "Verified sender of alert e-mails (address or domain identity)"
  type        = string
}

variable "alarm_email" {
  description = "Receives CloudWatch alarms; empty creates the topic without a subscriber"
  type        = string
  default     = ""
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "db_multi_az" {
  description = "Off in dev (SPEC 10.2), on in prod"
  type        = bool
  default     = false
}

variable "api_cpu" {
  type    = number
  default = 512
}

variable "api_memory" {
  type    = number
  default = 1024
}

variable "api_desired_count" {
  type    = number
  default = 1
}

variable "image_tag" {
  description = "Tag of the API image in ECR that the services run"
  type        = string
  default     = "latest"
}

variable "github_repository" {
  description = "owner/name of the repository allowed to deploy through OIDC"
  type        = string
}

variable "create_github_oidc_provider" {
  description = "Only one OIDC provider per account: set false when it already exists"
  type        = bool
  default     = true
}

variable "log_retention_days" {
  type    = number
  default = 30
}
