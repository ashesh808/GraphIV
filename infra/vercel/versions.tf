terraform {
  required_version = ">= 1.7.0, < 2.0.0"

  required_providers {
    vercel = {
      source  = "vercel/vercel"
      version = "~> 5.24.1"
    }
  }
}

provider "vercel" {
  # The provider reads the token from VERCEL_API_TOKEN.
  team = var.team
}
