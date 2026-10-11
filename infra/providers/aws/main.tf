locals {
  common_tags = var.tags
  api_domain  = var.enable_backend ? trimprefix(aws_apprunner_service.api[0].service_url, "https://") : null
}

resource "aws_ecr_repository" "api" {
  name                 = "${var.name_prefix}-api"
  image_tag_mutability = "IMMUTABLE"
  force_delete         = true
  tags                 = local.common_tags

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Retain only the five most recently pushed images."
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_secretsmanager_secret" "serpapi" {
  name                    = "${var.name_prefix}/serpapi-api-key"
  recovery_window_in_days = 0
  tags                    = local.common_tags
}

resource "aws_secretsmanager_secret" "openai" {
  name                    = "${var.name_prefix}/openai-api-key"
  recovery_window_in_days = 0
  tags                    = local.common_tags
}

resource "aws_iam_role" "apprunner_ecr_access" {
  name = "${var.name_prefix}-apprunner-ecr-access"
  tags = local.common_tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "build.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr_access" {
  role       = aws_iam_role.apprunner_ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

resource "aws_iam_role" "apprunner_instance" {
  name = "${var.name_prefix}-apprunner-instance"
  tags = local.common_tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "tasks.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "apprunner_secrets" {
  name = "${var.name_prefix}-read-runtime-secrets"
  role = aws_iam_role.apprunner_instance.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.serpapi.arn,
        aws_secretsmanager_secret.openai.arn,
      ]
    }]
  })
}

resource "aws_apprunner_auto_scaling_configuration_version" "single_instance" {
  auto_scaling_configuration_name = "${var.name_prefix}-single"
  max_concurrency                 = 100
  min_size                        = 1
  max_size                        = 1
  tags                            = local.common_tags
}

resource "aws_apprunner_service" "api" {
  count        = var.enable_backend ? 1 : 0
  service_name = "${var.name_prefix}-api"
  tags         = local.common_tags

  source_configuration {
    auto_deployments_enabled = false

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr_access.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
      image_repository_type = "ECR"

      image_configuration {
        port = "8000"

        runtime_environment_variables = {
          OPENAI_MODEL             = var.openai_model
          CACHE_TTL_SECONDS        = tostring(var.cache_ttl_seconds)
          CACHE_MAX_ENTRIES        = tostring(var.cache_max_entries)
          MAX_REVIEWS              = tostring(var.max_reviews)
          PROVIDER_TIMEOUT_SECONDS = tostring(var.provider_timeout_seconds)
          MODEL_CONTEXT_CHARS      = tostring(var.model_context_chars)
          CORS_ORIGINS             = ""
        }

        runtime_environment_secrets = {
          SERPAPI_API_KEY = aws_secretsmanager_secret.serpapi.arn
          OPENAI_API_KEY  = aws_secretsmanager_secret.openai.arn
        }
      }
    }
  }

  instance_configuration {
    cpu               = "0.25 vCPU"
    memory            = "0.5 GB"
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  auto_scaling_configuration_arn = aws_apprunner_auto_scaling_configuration_version.single_instance.arn

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  depends_on = [
    aws_iam_role_policy_attachment.apprunner_ecr_access,
    aws_iam_role_policy.apprunner_secrets,
  ]
}

resource "aws_s3_bucket" "frontend" {
  bucket        = "${var.name_prefix}-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  force_destroy = true
  tags          = local.common_tags
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket                  = aws_s3_bucket.frontend.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.name_prefix}-frontend"
  description                       = "Private S3 access for ReviewLens frontend."
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend" {
  count = var.enable_backend ? 1 : 0
  tags  = local.common_tags

  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  http_version        = "http2and3"

  origin {
    domain_name              = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id                = "reviewlens-frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  origin {
    domain_name = local.api_domain
    origin_id   = "reviewlens-api"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "reviewlens-frontend"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    cache_policy_id        = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  ordered_cache_behavior {
    path_pattern             = "api/*"
    target_origin_id         = "reviewlens-api"
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods           = ["GET", "HEAD"]
    compress                 = true
    cache_policy_id          = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    origin_request_policy_id = "b689b0a8-53d0-40ab-baf2-68738e2966ac"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
    minimum_protocol_version       = "TLSv1.2_2021"
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  count  = var.enable_backend ? 1 : 0
  bucket = aws_s3_bucket.frontend.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontReadOnly"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = ["s3:GetObject"]
      Resource  = "${aws_s3_bucket.frontend.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.frontend[0].arn
        }
      }
    }]
  })

  depends_on = [aws_s3_bucket_public_access_block.frontend]
}
