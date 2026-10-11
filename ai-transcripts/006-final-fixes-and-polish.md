# Final Fixes and Polish

## Prompt

We broke our CI/CD deployment. Here is the error log from GitHub Actions ...

```
Run if ! terraform state list | grep -Fqx 'aws_apprunner_service.api[0]'; then
data.aws_caller_identity.current: Reading...
aws_ecr_repository.api: Refreshing state... [id=reviewlens-cloud-dev-api]
aws_cloudfront_origin_access_control.frontend: Refreshing state... [id=EYV8K2MIWJOAU]
aws_secretsmanager_secret.serpapi: Refreshing state... [id=arn:aws:secretsmanager:us-east-1:098295335350:secret:reviewlens-cloud-dev/serpapi-api-key-l9munO]
aws_apprunner_auto_scaling_configuration_version.single_instance: Refreshing state... [id=arn:aws:apprunner:us-east-1:098295335350:autoscalingconfiguration/reviewlens-cloud-dev-single/1/63c8a2d0f8a34463bfb0700705914fab]
aws_secretsmanager_secret.openai: Refreshing state... [id=arn:aws:secretsmanager:us-east-1:098295335350:secret:reviewlens-cloud-dev/openai-api-key-2bMRxQ]
aws_iam_role.apprunner_instance: Refreshing state... [id=reviewlens-cloud-dev-apprunner-instance]
aws_iam_role.apprunner_ecr_access: Refreshing state... [id=reviewlens-cloud-dev-apprunner-ecr-access]
data.aws_caller_identity.current: Read complete after 0s [id=098295335350]
aws_s3_bucket.frontend: Refreshing state... [id=reviewlens-cloud-dev-098295335350-us-east-1]
aws_ecr_lifecycle_policy.api: Refreshing state... [id=reviewlens-cloud-dev-api]
aws_iam_role_policy_attachment.apprunner_ecr_access: Refreshing state... [id=reviewlens-cloud-dev-apprunner-ecr-access-20261011013450821900000003]
aws_iam_role_policy.apprunner_secrets: Refreshing state... [id=reviewlens-cloud-dev-apprunner-instance:reviewlens-cloud-dev-read-runtime-secrets]
aws_s3_bucket_public_access_block.frontend: Refreshing state... [id=reviewlens-cloud-dev-098295335350-us-east-1]

Planning failed. Terraform encountered an error while generating this plan.

╷
│ Error: reading CloudFront Origin Access Control (EYV8K2MIWJOAU): operation error CloudFront: GetOriginAccessControl, https response error StatusCode: 403, RequestID: f5ca0f7c-edbc-42aa-87c4-1ef40e768ddf, AccessDenied: User: arn:aws:sts::098295335350:assumed-role/reviewlens-github-deploy/GitHubActions is not authorized to perform: cloudfront:GetOriginAccessControl on resource: arn:aws:cloudfront::098295335350:origin-access-control/EYV8K2MIWJOAU because no identity-based policy allows the cloudfront:GetOriginAccessControl action
│
│   with aws_cloudfront_origin_access_control.frontend,
│   on main.tf line 178, in resource "aws_cloudfront_origin_access_control" "frontend":
│  178: resource "aws_cloudfront_origin_access_control" "frontend" {
│
╵
::error::Terraform exited with code 1.
Error: Process completed with exit code 1.
```

## Response
