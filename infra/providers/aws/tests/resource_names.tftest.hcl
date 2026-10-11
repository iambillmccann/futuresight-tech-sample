mock_provider "aws" {}

override_data {
  target = data.aws_caller_identity.current
  values = {
    account_id = "123456789012"
  }
}

run "default_scaling_configuration_name" {
  command = plan

  assert {
    condition     = aws_apprunner_auto_scaling_configuration_version.single_instance.auto_scaling_configuration_name == "reviewlens-cloud-dev-single"
    error_message = "The default scaling configuration must use the shortened name."
  }
}

run "maximum_prefix_fits_aws_limit" {
  command = plan

  variables {
    name_prefix = "abcdefghijklmnopqrstuvwxy"
  }

  assert {
    condition     = length(aws_apprunner_auto_scaling_configuration_version.single_instance.auto_scaling_configuration_name) == 32
    error_message = "The maximum supported prefix must produce a 32-character scaling configuration name."
  }
}

run "overlong_prefix_is_rejected" {
  command = plan

  variables {
    name_prefix = "abcdefghijklmnopqrstuvwxyz"
  }

  expect_failures = [var.name_prefix]
}

run "cloudfront_uses_verified_managed_policies" {
  command = plan

  variables {
    enable_backend = true
  }

  assert {
    condition     = aws_cloudfront_distribution.frontend[0].default_cache_behavior[0].cache_policy_id == "658327ea-f89d-4fab-a63d-7e88639e58f6"
    error_message = "Static assets must use AWS Managed-CachingOptimized."
  }

  assert {
    condition     = aws_cloudfront_distribution.frontend[0].ordered_cache_behavior[0].cache_policy_id == "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
    error_message = "API requests must use AWS Managed-CachingDisabled."
  }

  assert {
    condition     = aws_cloudfront_distribution.frontend[0].ordered_cache_behavior[0].origin_request_policy_id == "b689b0a8-53d0-40ab-baf2-68738e2966ac"
    error_message = "API requests must use AWS Managed-AllViewerExceptHostHeader."
  }
}
