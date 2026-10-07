variable "project_id" {
  description = "GCP project of this environment (dev and prod are separate projects)"
  type        = string
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "region" {
  type    = string
  default = "asia-southeast1"
}

variable "web_domain" {
  description = "Custom domain of the web app; empty serves it from the Firebase Hosting domain"
  type        = string
  default     = ""
}

variable "github_repository" {
  description = "owner/name of the repository allowed to deploy through Workload Identity Federation"
  type        = string
}

variable "alarm_email" {
  description = "Receives monitoring alerts; empty creates the policies without a channel"
  type        = string
  default     = ""
}

variable "db_tier" {
  type    = string
  default = "db-f1-micro"
}

variable "db_disk_gb" {
  type    = number
  default = 10
}

variable "db_high_availability" {
  description = "Regional (HA) Cloud SQL: off in dev, on in prod"
  type        = bool
  default     = false
}

variable "api_min_instances" {
  type    = number
  default = 0
}

variable "api_max_instances" {
  description = "Caps open database connections: each instance holds its own pool"
  type        = number
  default     = 3
}

variable "api_cpu" {
  type    = string
  default = "1"
}

variable "api_memory" {
  type    = string
  default = "1Gi"
}

variable "image_tag" {
  description = "Tag of the API image in Artifact Registry (the pipeline deploys by commit sha)"
  type        = string
  default     = "latest"
}

variable "mail_backend" {
  description = "memory until an SMTP provider is chosen (e-mail is on hold); smtp afterwards"
  type        = string
  default     = "memory"
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "deploy_services" {
  description = "false on the very first apply: the Cloud Run resources need an image that the Deploy workflow pushes afterwards"
  type        = bool
  default     = true
}

variable "db_pool_size" {
  type    = number
  default = 3
}

variable "db_max_overflow" {
  type    = number
  default = 2
}
