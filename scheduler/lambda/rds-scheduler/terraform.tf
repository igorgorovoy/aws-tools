terraform {
 required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "= 5.60.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.6.0"
    }
  }
  required_version = "1.8.4"
  backend "s3" {}
}
