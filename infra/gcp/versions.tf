terraform {
  required_version = ">= 1.9"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.10"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.10"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # State lives in a GCS bucket of the environment's own project:
  # terraform init -backend-config=envs/<env>.backend.hcl
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region

  # with user credentials some APIs (Firebase, Monitoring) need a quota project
  user_project_override = true
  billing_project       = var.project_id
}

provider "google-beta" {
  project = var.project_id
  region  = var.region

  # with user credentials some APIs (Firebase, Monitoring) need a quota project
  user_project_override = true
  billing_project       = var.project_id
}
