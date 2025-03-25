variable "github_token" {
  description = "GitHub Personal Access Token"
  type        = string
  sensitive   = true
}

variable "environment" {
  description = "Environment type (dev, staging, prod)"
  type        = string
  default     = "dev"
}
