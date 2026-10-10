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
