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

I'll find where the `reviewlens-github-deploy` role's policy is defined.

Search for `cloudfront:|reviewlens-github-deploy|github-deploy`

The deploy role's policy is managed manually in IAM (not in the repo). Let me check what the current policy grants for CloudFront.

Search for `OriginAccessControl|origin-access-control`

Read , lines 2960 to 3060
Completed with input: {
"path": "/home/iambillmccann/repositories/futuresight-tech-sample/ai-transcripts/004-milestone-2.md",
"view_range": [
2960,
3060
]
}

Search for `aws_cloudfront|origin_access_control`

Read , lines 1730 to 1750
Completed with input: {
"path": "/home/iambillmccann/repositories/futuresight-tech-sample/ai-transcripts/004-milestone-2.md",
"view_range": [
1730,
1750
]
}

Found the cause. Checking whether the saved policy JSON from the earlier session still has the hard-coded ID.

Ran terminal command: f=/home/iambillmccann/.copilot/session-state/0246d3f8-23db-450e-8647-b4a768ab1187/files/reviewlens-github-deploy-policy.json; ls -l $f && grep -n "origin-access-control" $f

I'll update the saved policy JSON so the OAC statement uses a wildcard, and save a copy in this session's folder.

Ran terminal command: src=/home/iambillmccann/.copilot/session-state/0246d3f8-23db-450e-8647-b4a768ab1187/files/reviewlens-github-deploy-policy.json
dst=/home/iambillmccann/.copilot/session-state/c430be5d-75bd-4f0b-9fad-82a6a9e6c4be/files/reviewlens-github-deploy-policy.json
sed -i 's#origin-access-control/E3P6VQD6E0QTY#origin-access-control/\*#' "$src" && cp "$src" "$dst"
node -e 'const p=JSON.parse(require("fs").readFileSync(process.argv[1],"utf8"));console.log("valid, size",JSON.stringify(p).length,"/6144");console.log(JSON.stringify(p.Statement.find(s=>[].concat(s.Action).includes("cloudfront:GetOriginAccessControl")),null,2))' "$dst"

The deploy role's IAM policy, not the code, is what broke the deployment. The policy you set up during milestone 2 gives `GetOriginAccessControl`, `UpdateOriginAccessControl` and `DeleteOriginAccessControl` access to a single CloudFront origin access control, the one with ID **`E3P6VQD6E0QTY`**.

When you tore the stack down and redeployed, Terraform created a new origin access control with a new ID (**`EYV8K2MIWJOAU`**). The policy still only covers the old ID, so Terraform gets "Access Denied" as soon as it tries to read the new one. This will happen again on every teardown and redeploy as long as the ID is hard-coded.

**Fix (in the AWS Console, not the repo):**

1. Go to **IAM → Policies** and open `reviewlens-github-deployment-policy`. Then choose **Edit → JSON**.
2. Press Ctrl+F and search for `E3P6VQD6E0QTY`. In that statement, change the `Resource` to:
   ```json
   "Resource": "arn:aws:cloudfront::098295335350:origin-access-control/*"
   ```
3. Click **Next → Save changes**, then rerun the deploy workflow.

**Why a wildcard:** origin access controls don't support tags, so the tag-based conditions used for the distributions won't work here. The wildcard still limits these permissions to CloudFront origin access controls in your account.

I made the same change in the saved policy file, which is still valid JSON and under the IAM size limit (5,722 of 6,144 characters). A copy is at `reviewlens-github-deploy-policy.json` if you'd rather paste in the whole policy. No repository changes were needed.

## Prompt

Apparently the teardown script removes the values of our secrets. I will restore the values now but let's discuss what services should persist after teardown. We should consider two modes of teardown, one that shuts down the services to minimize cost, and another that removes all artifacts of the app.

Here is the error message ...

```
Run for secret_name in "$(terraform output -raw serpapi_secret_name)" "$(terraform output -raw openai_secret_name)"; do
  for secret_name in "$(terraform output -raw serpapi_secret_name)" "$(terraform output -raw openai_secret_name)"; do
    aws secretsmanager get-secret-value --secret-id "$secret_name" --query ARN --output text >/dev/null
  done
  shell: /usr/bin/bash -e {0}
  env:
    AWS_REGION: us-east-1
    AWS_ROLE_ARN: arn:aws:iam::098295335350:role/reviewlens-github-deploy
    pythonLocation: /opt/hostedtoolcache/Python/3.12.15/x64
    PKG_CONFIG_PATH: /opt/hostedtoolcache/Python/3.12.15/x64/lib/pkgconfig
    Python_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.15/x64
    Python2_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.15/x64
    Python3_ROOT_DIR: /opt/hostedtoolcache/Python/3.12.15/x64
    LD_LIBRARY_PATH: /opt/hostedtoolcache/Python/3.12.15/x64/lib
    TERRAFORM_CLI_PATH: /home/runner/work/_temp/492e1b14-e2de-4d83-bf53-3d296c004141
    AWS_DEFAULT_REGION: us-east-1
    AWS_ACCESS_KEY_ID: ***
    AWS_SECRET_ACCESS_KEY: ***
    AWS_SESSION_TOKEN: ***

aws: [ERROR]: An error occurred (ResourceNotFoundException) when calling the GetSecretValue operation: Secrets Manager can't find the specified secret value for staging label: AWSCURRENT
Error: Process completed with exit code 254.
```

## Response
