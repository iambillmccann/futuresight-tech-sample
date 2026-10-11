# ReviewLens AI

ReviewLens AI is a public, local-first review intelligence workspace for Google Maps businesses and Amazon products. It retrieves real review data through SerpApi, computes an honest ingestion summary, lets visitors browse, filter, refresh, and export the active dataset, and uses OpenAI to answer questions only from the active cached dataset with review evidence.

The application is intentionally anonymous and ephemeral: there are no accounts, saved analyses, databases, or durable chat histories. Refresh preserves a usable cache entry when the provider fails and merges unique prior review IDs when a refresh is partial. Amazon ingestion uses the limited customer reviews visible on a product page and is always marked partial.

## Architecture

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** FastAPI and Pydantic
- **Review provider:** SerpApi Google Maps, Google Maps Reviews, and Amazon Product APIs
- **Q&A provider:** OpenAI Chat Completions API with structured JSON output
- **Storage:** bounded, process-local TTL cache

Cloud development keeps the same architecture: one AWS App Runner backend
instance, with an S3-hosted frontend served through CloudFront. CloudFront
routes `/api/*` to the backend, so browser requests stay same-origin and no
production CORS allowlist is needed. There is no database, Redis, user login,
durable review storage, or durable chat history.

The backend validates a full `google.com/maps` place URL, a Google Maps share link, or a supported `amazon.com` product URL and sends only derived search/provider identifiers to the fixed SerpApi endpoint. It never fetches a submitted full URL. SerpApi records are normalized into a shared review model; malformed records are skipped and reported. Google Maps cache keys prefer the stable Place ID or SerpApi data ID and fall back to a normalized URL hash. Amazon keys include platform, marketplace, and ASIN (`amazon:amazon.com:asin:ASIN`), so product URL variants share a cache entry without colliding with Google Maps.

### Google Maps share links

Links copied from Google Maps' **Share** button (`https://maps.app.goo.gl/CODE`,
or legacy `https://goo.gl/maps/CODE`) are resolved before ingestion. The backend
rebuilds the link from its code on those fixed Google hosts (query strings,
credentials, ports, and extra path segments are dropped or rejected), requests
it without automatic redirects, reads only the `Location` header, and allows at
most three hops. Each hop must be another share link or a destination that passes
the normal `google.com/maps` validation; anything else is rejected without being
fetched. The resolved place URL then follows the standard path, so a share link and
the full URL for the same place share one cache entry. Expired links, redirect
loops, and network failures return explicit errors. A shared directions link (or
full directions URL) is analyzed as the first place in the route.

### Amazon coverage

SerpApi's [Amazon Product API](https://serpapi.com/amazon-product-api)
(`engine=amazon_product`) provides individual reviews in
`reviews_information.authors_reviews`. ReviewLens ingests only those customer
text/rating records, not Amazon's generated review summary or aggregate rating.
There is no documented review pagination in this endpoint: the dataset is always
marked **partial**, with a visible coverage warning. Counts and average ratings
describe the retrieved sample, not all reviews on Amazon. The visible reviews
may include variants of the selected product.

Supported URLs are `https://www.amazon.com/dp/ASIN`,
`https://www.amazon.com/product-name/dp/ASIN`, and
`https://www.amazon.com/gp/product/ASIN` (a 10-character alphanumeric ASIN).
Only the US `amazon.com` marketplace is enabled. Short links, other marketplaces,
search/review-list URLs, credentials, and custom ports are rejected.
Missing text reviews, a mismatched returned ASIN, and provider failures produce
explicit API errors rather than fabricated data. English review dates are
normalized to ISO dates when recognized; otherwise the provider date is retained.
When no usable customer reviews are available, the API returns HTTP 422 with
`NO_USABLE_REVIEWS` and the message "Reviews are not available for this item.
Please try another Amazon product." The frontend displays this message directly.
If no stable provider review ID is supplied, a deterministic local record ID is
generated from the ASIN, author, date, and text; it is not an Amazon review ID.

This mechanism was verified with a live SerpApi request on October 11, 2026:
product `B072MQ5BRX` returned 8 usable customer text reviews. Automated tests use
mocked HTTP responses, not paid live calls.

Each Q&A call resolves the active source key from the backend cache. The versioned system prompt names the current business and platform, treats review text as untrusted evidence, prohibits external knowledge, requires explicit refusals, and distinguishes insufficient evidence from an out-of-scope request. Review context, dataset size, request lengths, provider timeouts, and cache size are bounded.

When information is missing, the prompt asks for plain-language responses beginning
with "The reviews do not contain information about ..." rather than "review dataset".

## Prerequisites

- Python 3.8 or newer
- Node.js `^20.19.0` or `>=22.12.0` (required by Vite 8)
- SerpApi API key with Google Maps and/or Amazon Product access
- OpenAI API key

## Configuration

Copy the example environment file and add provider credentials:

```bash
cp .env.example .env
```

Required server-side values:

```dotenv
SERPAPI_API_KEY=...
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

The remaining values in `.env.example` configure allowed browser origins, the 24-hour cache TTL, cache and review bounds, provider timeout, and maximum model-context size. Vite does not receive either provider key.

The backend reads environment variables from its process. Export the file before starting it:

```bash
set -a
. ./.env
set +a
```

## Local setup

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
```

Start the API:

```bash
set -a
. ./.env
set +a
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`, paste a full Google Maps place URL or supported Amazon product URL, and select **Analyze Reviews**. The platform is detected from the URL.

In Q&A, press Return or click the arrow button to submit a question.
Use Shift+Return to add a new line.

Three charts below the metrics show star-rating distribution, weekly average
rating, and weekly review counts for the full active cached review set, unaffected
by browsing filters. Weeks start on Monday using the review's recorded calendar
date. Unknown/missing dates are excluded from trends and counted in a note.
Empty intervening weeks have zero reviews but no average rating (a gap in that
line). These charts describe the collected sample, not the platform's entire
review history. Weekly values are also available in expandable tables.

## AWS cloud development

The AWS adapter is in [`infra/providers/aws`](./infra/providers/aws). It uses:

- **Amazon S3 and CloudFront** for private-bucket static hosting and the AWS-provided HTTPS frontend URL.
- **AWS App Runner** for the containerized FastAPI API. Its auto-scaling configuration is capped at one 0.25-vCPU/0.5-GB instance to preserve the process-local cache.
- **Amazon ECR** for immutable, scanned backend images.
- **AWS Secrets Manager** for runtime provider credentials. Terraform creates secret containers and IAM access but never manages secret values.
- **An encrypted, versioned S3 bucket with native lock files** for Terraform state. The bootstrap bucket is intentionally retained during app teardown.

No PostgreSQL migration is needed: this milestone intentionally has no database.
The default resource prefix is `reviewlens-cloud-dev`. Custom `name_prefix`
values must be 1-25 lowercase letters, digits, or hyphens and start with a
letter or digit, keeping the App Runner scaling configuration within its
32-character name limit. CI checks these limits with mocked Terraform tests
without AWS credentials.
The API is accessed through the frontend's CloudFront origin, keeping requests
same-origin. The App Runner health endpoint is also available directly for
smoke testing.

### One-time AWS setup

1. Create or choose an AWS account and a region (the default is `us-east-1`).
   Install AWS CLI, Terraform 1.10+, and Docker, then authenticate locally with
   an AWS principal allowed to bootstrap the state bucket and provision the
   listed resources.
2. Create a GitHub Actions OIDC provider and a deployment IAM role. Restrict
   the role trust to this repository's `repo:OWNER/REPOSITORY:ref:refs/heads/main`
   subject; grant only the permissions needed for the Terraform-managed
   App Runner, ECR, CloudFront, S3, Secrets Manager, and IAM resources, and
   `iam:PassRole` only for the two ReviewLens App Runner roles. Do not use
   long-lived AWS keys in GitHub.
3. Add repository **Actions variables** `AWS_REGION` and `AWS_ROLE_ARN` with
   the selected region and OIDC role ARN.
4. Bootstrap and initialize Terraform state, then provision the ECR repository,
   secret containers, and hosting prerequisites:

   ```bash
   export AWS_REGION=us-east-1
   bash infra/providers/aws/bootstrap.sh
   cd infra/providers/aws
   account_id="$(aws sts get-caller-identity --query Account --output text)"
   terraform init \
     -backend-config="bucket=reviewlens-tfstate-${account_id}-${AWS_REGION}" \
     -backend-config="region=${AWS_REGION}"
   terraform apply -var="aws_region=${AWS_REGION}" -var="enable_backend=false"
   ```

5. In AWS Secrets Manager, set the `SecretString` values for the two names
   printed by `terraform output -raw serpapi_secret_name` and
   `terraform output -raw openai_secret_name`. Use the Plaintext editor and
   store only the raw API key, not JSON or a key/value pair. App Runner injects
   the entire secret string as the credential. After changing a secret value,
   redeploy App Runner so it receives the updated credential.
   Keep the values out of Terraform,
   shell history, GitHub, and the repository.
6. Push or merge to `main` (or run **Deploy cloud development** manually from
   `main`). The workflow verifies tests, publishes a SHA-tagged image, deploys
   the service and static frontend, invalidates the CDN, and smoke-tests both
   public endpoints. The output `frontend_url` is the AWS-provided public URL
   to share with the assessment reviewers.

The workflow intentionally refuses to deploy until both secret values exist.
GitHub Actions uses OIDC, not static AWS credentials. The first deployment
creates the public URL; no custom domain or URL shortener is used. The browser
bundle contains neither provider key.

### Teardown, cost, and limitations

Run **Tear down cloud development** from `main` and type `destroy` to confirm.
Terraform destroys the App Runner service, CloudFront distribution, frontend
bucket contents, ECR images/repository, and runtime secret containers/values.
The encrypted and versioned Terraform state bucket is retained. Store provider
keys safely elsewhere before teardown if you will redeploy. Review the Terraform
plan/state before destroying resources manually.

The single App Runner instance is always provisioned (it does not scale to
zero), so even an idle environment incurs a recurring compute charge. At the
smallest configured size, budget roughly **$3–$10/month for idle backend
compute** in a typical US region. A light active scenario (about 10 CPU-active
hours/month) is roughly **$3–$11/month for AWS hosting**, before variable
CloudFront/S3 requests and egress. These are estimates, not quotes; check the
AWS Pricing Calculator for the selected region, set a billing alert, and tear
down promptly when the demo is not needed. SerpApi and OpenAI quotas and
charges remain governed by those providers.

The public anonymous endpoint has no per-visitor identity or rate limiter.
Provider calls have configured timeouts and bounded review/context/cache sizes,
but this short-lived assessment deployment should be monitored and shut down
if abused. App Runner's single-instance cap preserves cache reuse only while
that instance remains running; deployments, restarts, and teardown clear the
cache. A successful infrastructure smoke test verifies frontend reachability
and API liveness; manually verify real ingestion, cache reuse, Q&A, scope
refusal, and provider-failure messaging before sharing the URL.

### Assessment walkthrough

Record a Loom video under three minutes that demonstrates a real Google Maps
ingestion, the computed summary, an in-scope question with evidence, and a
general-knowledge or other-platform question that is explicitly refused.
Briefly cover the review-only system prompt, anonymous single-process cache,
provider-managed quotas, AWS layout, one tradeoff, and what you would improve.
Share the video, repository, and deployed URL with FutureSight.

## REST API

Successful responses use:

```json
{"data": {}, "meta": {}}
```

Errors use:

```json
{
  "error": {
    "code": "STABLE_ERROR_CODE",
    "message": "Safe client-facing message.",
    "details": []
  }
}
```

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness |
| `GET` | `/ready` | Local readiness |
| `GET` | `/version` | API version |
| `POST` | `/api/ingest` | Validate a Google Maps or Amazon product URL, retrieve reviews, and return source metadata plus a computed summary |
| `POST` | `/api/refresh` | Refresh an unexpired cached source without discarding the old dataset on provider failure |
| `GET` | `/api/reviews` | Browse/filter/paginate active cached reviews (`source_key`, optional `rating`, `start_date`, `end_date`, `page`, `page_size`) |
| `POST` | `/api/chat` | Ask a question against an unexpired `source_key` |

Ingestion request:

```json
{"source_url": "https://www.google.com/maps/place/..."}
```

Amazon ingestion uses the same request shape:

```json
{"source_url": "https://www.amazon.com/dp/B072MQ5BRX"}
```

The response's `source.platform` is `Amazon` and `source.provider_id` is the ASIN.
The shared `source.business_name` field contains the product title for Amazon.
Summary, browsing, refresh, export, and Q&A use the same normalized dataset and
platform-aware source key. The system prompt explicitly requires refusal for an
unselected platform, even though both platforms are supported. A narrow
application check also prevents explicit Amazon/Google Maps requests from
relabeling the active platform's evidence if the model fails to refuse.

Chat request:

```json
{
  "source_key": "google-maps:place_id:...",
  "question": "What complaints recur in these reviews?"
}
```

Refresh request:

```json
{"source_key": "google-maps:place_id:..."}
```

Review browsing returns the exact source key, current page, page size, filtered review count, and normalized review records. An expired or evicted cache entry returns `DATASET_UNAVAILABLE`; it is never answered or exported from stale client-side state. The frontend exports reviews as CSV and the open, unsaved question/answer transcript as Markdown.

Stable failures include invalid/unsupported URLs, missing or expired datasets, missing server configuration, provider rejection, throttling/quota exhaustion, malformed provider responses, and timeouts. Raw upstream bodies, credentials, and tracebacks are not returned.

## Validation

```bash
.venv/bin/pytest backend/test_app.py backend/test_amazon.py -q
.venv/bin/python -m compileall -q backend
cd frontend
npm run lint
npm run build
```

Tests use deterministic provider and model doubles; CI never depends on live SerpApi data or model wording. Coverage includes URL/SSRF validation, record normalization, computed summaries, cache hits and expiry, concurrent miss coalescing, source isolation, review filters and pagination, refresh failure preservation and partial-result merging, bounded model context, evidence identifiers, insufficient evidence, refusals, prompt injection boundaries, and sanitized provider failures.

## Assumptions and limitations

- Google Maps is the only Milestone 1 platform.
- A submitted URL must be a full `google.com/maps` location URL, a `maps.app.goo.gl`/`goo.gl/maps` share link, or a supported `amazon.com` product URL. Share links are resolved only by reading redirect headers from those fixed Google hosts, and every hop is revalidated; arbitrary redirects are never followed.
- SerpApi determines available review coverage. `MAX_REVIEWS` bounds the exact normalized dataset used for both summary and Q&A.
- Cache state is shared by anonymous visitors in one backend process and disappears on expiration, eviction, or restart.
- Concurrent requests with the same submitted stable identifier or normalized URL share one in-flight ingestion. A previously resolved URL alias also reuses its stable provider-key entry.
- The frontend transcript exists only in the open page and is reset when the active source changes.
- Provider account quotas are authoritative; ReviewLens surfaces safe errors rather than implementing a second quota system.
- Amazon support is a limited product-page sample, not full review-history ingestion. Only `amazon.com` is enabled.
- Review browsing, manual refresh, and CSV/Markdown exports operate on the current process-local cache and do not create saved analyses or durable history.
