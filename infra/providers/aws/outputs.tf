output "ecr_repository_url" {
  description = "ECR repository URL for the backend image."
  value       = aws_ecr_repository.api.repository_url
}

output "frontend_bucket" {
  description = "Private S3 bucket for the built frontend."
  value       = aws_s3_bucket.frontend.id
}

output "frontend_url" {
  description = "Public CloudFront URL; null until the backend is enabled."
  value       = try("https://${aws_cloudfront_distribution.frontend[0].domain_name}", null)
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID; null until the backend is enabled."
  value       = try(aws_cloudfront_distribution.frontend[0].id, null)
}

output "backend_url" {
  description = "App Runner backend URL; null until the backend is enabled."
  value       = try("https://${aws_apprunner_service.api[0].service_url}", null)
}

output "serpapi_secret_name" {
  description = "Secrets Manager name to populate with the SerpApi API key."
  value       = aws_secretsmanager_secret.serpapi.name
}

output "openai_secret_name" {
  description = "Secrets Manager name to populate with the OpenAI API key."
  value       = aws_secretsmanager_secret.openai.name
}
