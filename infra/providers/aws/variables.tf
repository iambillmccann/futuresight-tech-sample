variable "aws_region" {
  description = "AWS region for the cloud development environment."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Resource name prefix: 1-25 lowercase letters, digits, or hyphens, starting with a letter or digit."
  type        = string
  default     = "reviewlens-cloud-dev"

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{0,24}$", var.name_prefix))
    error_message = "name_prefix must be 1-25 lowercase letters, digits, or hyphens, starting with a letter or digit, so the App Runner scaling configuration name stays within 32 characters."
  }
}

variable "enable_backend" {
  description = "Create the App Runner service and CloudFront distribution after the image is pushed."
  type        = bool
  default     = false
}

variable "image_tag" {
  description = "Existing image tag in the managed ECR repository."
  type        = string
  default     = "latest"
}

variable "cache_ttl_seconds" {
  description = "In-memory review dataset cache lifetime."
  type        = number
  default     = 86400
}

variable "cache_max_entries" {
  description = "Maximum cached datasets in the single backend instance."
  type        = number
  default     = 50
}

variable "max_reviews" {
  description = "Maximum reviews fetched per dataset."
  type        = number
  default     = 200
}

variable "provider_timeout_seconds" {
  description = "Timeout for review and model provider calls."
  type        = number
  default     = 20
}

variable "model_context_chars" {
  description = "Maximum review context size sent to the language model."
  type        = number
  default     = 60000
}

variable "openai_model" {
  description = "Server-side OpenAI model name."
  type        = string
  default     = "gpt-4.1-mini"
}

variable "tags" {
  description = "Tags applied to provisioned resources."
  type        = map(string)
  default = {
    application = "reviewlens"
    environment = "cloud-dev"
    managed_by  = "terraform"
  }
}
