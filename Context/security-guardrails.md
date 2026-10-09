# Data and Security Guardrails

Authoritative for ReviewLens AI's public-access model, API security boundaries, data handling, ingestion protections, LLM safeguards, and secret management. Read this before implementing or modifying any API endpoint, ingestion operation, or Q&A workflow.

## 1. Security model and assessment requirements

ReviewLens AI is a **publicly accessible, unauthenticated demonstration application**. A visitor must be able to open the deployed URL and complete the full flow—review ingestion, ingestion summary, review-specific Q&A, and scope-guard refusal—without creating an account or signing in.

The FutureSight technical assessment explicitly requires **no user authentication**. Consequently:

- Do not require Clerk, login, bearer tokens, sessions, or an API key provided by the visitor.
- Do not make account identity, user roles, or per-user ownership a prerequisite for using the application.
- Do not treat anonymous access as permission to run unlimited scraping, database operations, or LLM calls.
- Enforce safeguards on the **server**, not just in the frontend. The public web UI is not a security boundary.

The API is necessarily callable by untrusted clients. CORS, hidden UI controls, and unguessable URLs do **not** authenticate callers or protect public endpoints. The goal is to **limit abuse, resource consumption, injection, and data exposure**, not to invent an identity model the assessment does not require.

## 2. Remove identity and ownership dependencies

The earlier Cornerstone-derived model used Clerk identity, `users.auth_provider_user_id`, `get_current_user`, and `owner_user_id` on `AnalysisTarget`. That model is **not applicable to this assessment build**.

- Remove Clerk-related frontend components and configuration from the runtime path, including `@clerk/clerk-react` and `VITE_CLERK_PUBLISHABLE_KEY` where no longer used.
- Remove bearer-token checks and Clerk JWKS verification from public ReviewLens routes.
- Do not call `app.services.identity.bootstrap_user_from_identity` or require `app.dependencies.get_current_user` for these routes.
- Remove owner-scoped lookup requirements such as `get_owned_target(session, owner_user_id, target_id)`; replace them with carefully constrained resource lookups appropriate to public data.
- Evaluate whether legacy `User`, `Workspace`, `WorkspaceMember`, and ownership fields can be deleted in a migration. If retained temporarily for compatibility, they must **not** control the public workflow. Do not fabricate a shared "user" account as a substitute for authentication.

Any schema and migration changes must be coordinated with existing records and tests. Do not drop production data as a side effect of enabling anonymous access.

## 3. Data visibility and resource lifecycle

With no authenticated identity, ReviewLens cannot securely distinguish which visitor created a target, review set, ingestion run, or chat session. **Do not claim that data is private to an anonymous visitor merely because it has a UUID or is not displayed in the UI.**

For this assessment:

- Treat persisted `AnalysisTarget`, `Review`, and `IngestionRun` data as **non-private demonstration data**. Do not ingest confidential, personal-account, or credential-protected content.
- Only ingest reviews from the selected publicly accessible platform, or review data supplied in a supported, explicitly bounded format. Public access to a review page does not override platform terms or access restrictions.
- Make deliberate choices about what the public API exposes. Do not provide unrestricted database listing, search, arbitrary filtering, or bulk exports by default.
- If resource IDs are exposed, consider them locators, **not** authorization credentials. Do not use ID secrecy as the only protection against destructive operations.
- Avoid public update/delete endpoints unless essential to the assessment; where necessary, implement server-enforced abuse controls. A no-login public service cannot offer reliable per-visitor ownership authorization without another credential mechanism.
- Apply a documented retention/cleanup policy to persisted runs, review content, and chat data to limit cost and exposure. Set operationally appropriate values before deployment.

If future requirements introduce private analyses, account histories, or user-owned records, those features require a **separate authentication and authorization design**. They are not supported by this public-access policy.

## 4. API boundary and abuse protection

All endpoints, including `POST /analysis-targets`, ingestion triggers, review reads, and Q&A, must validate and constrain requests **server-side**.

- Validate request bodies with explicit Pydantic schemas; reject unsupported fields where appropriate. Never accept database/internal fields such as owner IDs, ingestion status, arbitrary provider credentials, or model configuration from the client.
- Enforce request size, text length, pagination, and result-count limits. Cap uploaded review size and total review counts where uploads are supported.
- Use rate limits at the public edge and/or API layer, especially for ingestion and chat. Use appropriate per-IP or network-level controls with awareness that IP addresses are shared and spoofable headers cannot be trusted without a configured proxy chain.
- Apply stricter concurrency limits and quotas for high-cost operations: upstream fetching, parsing, embedding, and LLM requests. Set a server-side maximum cost or token budget per operation and an overall service budget/alert.
- Apply timeouts for network calls and LLM operations; bound retries and use backoff. Never permit unbounded background work from a public trigger.
- Where practical, deduplicate or cache repeated ingestion of the same normalized review source rather than repeatedly charging for identical operations.
- Require an explicit allowlist of HTTP methods and paths. Use edge/WAF/bot controls or temporary operational shutdown if public abuse becomes significant; do not introduce mandatory visitor login to solve it in this assessment.
- Configure CORS only for intended browser origins. **CORS is not an authorization mechanism**; a direct HTTP client can still call the API.

Limits must be configurable and exercised in tests. Record the chosen values in deployment configuration or operational documentation rather than leaving them implicit.

## 5. URL ingestion and outbound request safety

The ingestion endpoint handles **untrusted, client-supplied URLs** and must defend against server-side request forgery (SSRF).

- Accept only supported public URLs from the **chosen review platform** (Google Maps, if this deployment uses that platform). Reject arbitrary domains, non-HTTP(S) schemes, and embedded credentials.
- Normalize and validate hosts and URLs before use. Follow redirects only if each destination is revalidated against the allowlist.
- Block loopback, private, link-local, metadata-service, and other non-public network destinations at the network/HTTP client layer. Defend against DNS rebinding and alternate IP representations; hostname checks alone are insufficient.
- Apply strict connection/read timeouts, response-size ceilings, redirect limits, and fetch concurrency bounds.
- Do not evaluate downloaded scripts or follow arbitrary review-page links. Treat external HTML, text, and structured review content as untrusted input.
- Keep any review-provider credentials on the backend. Never let the caller choose arbitrary upstream endpoints or supply server credentials.
- If automated retrieval is unavailable or prohibited, allow only the assessment-supported alternative ingestion path rather than attempting to bypass provider controls.

## 6. Guardrailed Q&A and prompt injection

The Q&A interface must answer **exclusively from the reviews ingested for the current analysis** and must explicitly decline questions about other sources or general world knowledge. This is a core assessment requirement.

- Build the system prompt to define the selected review platform, current analysis scope, permitted evidence, and required refusal behavior.
- Retrieve or pass only review content associated with the selected analysis target. Never mix retrieved chunks from unrelated analyses or other platforms.
- Treat review text, page content, filenames, and user questions as **untrusted data**, not instructions that can override the system's scope rules. Delimit review evidence clearly.
- Do not grant the model tools or unrestricted network access that would enable out-of-scope answers.
- Ask the model to acknowledge insufficient evidence rather than fabricate conclusions. Cite or reference supporting ingested reviews where the product supports it.
- Enforce model, token, context-size, and request limits server-side. Do not allow the caller to override system prompts, switch to arbitrary models, or set unlimited generation parameters.
- Check that responses remain within scope where feasible. Prompt configuration is the primary scope guard requested by the assessment, but prompt instructions alone are not an absolute security boundary.

At minimum, test questions about the selected reviews, a different review platform, unrelated world knowledge (e.g., weather), and malicious instructions embedded in a review.

## 7. Read/write operations and errors

Public API access does not imply unrestricted mutation privileges.

- Expose only the endpoints required for the demonstration flow. Avoid general-purpose database administration, bulk data modification, or schema-management endpoints.
- Use database transactions and idempotent operation semantics where appropriate so retries do not create uncontrolled duplicate ingestion runs or inconsistent records.
- For nonexistent resources, return `404` without confirming anything about hidden internal records. Do not retain the former cross-user `403` versus `404` rationale: the assessment has no user-ownership boundary.
- `app/main.py` must continue to return a fixed, safe message for unhandled exceptions; never include tracebacks in API responses.
- Ingestion failures should continue to return stable `error_code` values and messages from approved mappings (e.g., `INGESTION_ERROR_MESSAGES` in `app/domain.py`). Do not echo raw upstream response bodies, provider errors, database diagnostics, or internal URLs.
- The frontend API client and error boundary should continue to display user-safe messages for malformed error envelopes and render failures.

Use appropriate status codes, including `400`/`422` for invalid inputs, `404` for absent resources, `413` for oversized payloads, `429` for rate-limit rejections, and `503` for controlled service unavailability when applicable.

## 8. Secrets, configuration, and logging

- Never commit production credentials or secrets. `.env.example` and `apps/api/.env.example` contain variable names and safe placeholders only.
- `REVIEW_PROVIDER_API_KEY`, LLM API keys, database credentials, and other privileged configuration must remain server-side. The browser calls ReviewLens, not the review provider or LLM vendor directly with privileged credentials.
- Anything prefixed `VITE_` is compiled into the public frontend bundle. Only genuinely public configuration, such as the API base URL, belongs there. Remove unused Clerk settings.
- Keep using managed secret storage for deployed environments, consistent with the deployment approach described in `iaas-standards.md` where applicable. Do not require a particular cloud provider solely for the assessment.
- Log request outcomes, operation durations, throttling, upstream failures, and bounded cost/usage metrics. Do not log raw secrets, authorization headers, provider API keys, or entire review/chat payloads by default.
- Avoid persisting sensitive personal information submitted by visitors. Publish minimal operational logs and use retention limits.

## 9. Tests for the public-access model

Replace the previous `user_a`/`user_b` cross-user authorization matrix with tests of **anonymous functionality and abuse resistance**. Existing test factories may be refactored to create an unauthenticated API client without overriding `get_current_user`.

Every relevant feature should cover:

1. **Anonymous success:** A visitor can access the deployed app and complete ingestion, summary, scoped Q&A, and refusal without a login, Clerk token, or other visitor credential.
2. **Input validation:** Invalid bodies, unsupported fields, oversized payloads, and unsupported review URLs are rejected without side effects.
3. **SSRF resistance:** Internal destinations, non-allowlisted hosts, and unsafe redirects are rejected before content is fetched.
4. **Abuse limits:** Rate limits, concurrency controls, operation budgets, and bounded retries fail safely under pressure.
5. **Analysis isolation:** Q&A for one analysis cannot incorporate another analysis's reviews, even though neither belongs to a logged-in user.
6. **Scope refusal:** The model explicitly declines requests about another platform or general world knowledge, including attempts to override the system prompt through review content.
7. **Safe failures:** Errors reveal no stack traces, tokens, upstream credentials, or internal service details; partial failures do not corrupt stored data.
8. **Public API surface:** Nonessential destructive or administrative endpoints are absent or otherwise protected with an explicit server-side mechanism.

Remove or revise legacy tests such as `TestCrossUserAuthorization` and `TestCrossUserIngestionAuthorization` because they enforce an identity model this assessment expressly excludes. Preserve their useful service-level data-integrity assertions where applicable.

## 10. Checklist for any new public endpoint

- [ ] Works without visitor authentication, token, cookie, or account.
- [ ] Exists for a clear review-ingestion, summary, or scoped-Q&A purpose.
- [ ] Uses strict request schemas and bounds all input sizes, outputs, and work performed.
- [ ] Does not trust client-controlled database fields or privileged configuration.
- [ ] Applies appropriate rate, concurrency, timeout, and cost controls.
- [ ] Validates and constrains all outbound URLs; no unsafe redirects or private-network access.
- [ ] Queries only the intended analysis data and exposes no unrelated records.
- [ ] Treats external reviews as untrusted evidence, not executable instructions.
- [ ] Keeps keys and internal details server-side and returns safe errors.
- [ ] Includes anonymous-success, abuse, failure, and scope tests relevant to the endpoint.

---

**Scope note:** The assessment mandates public access, no user authentication, ingestion summary, guardrailed review-only Q&A, deployed URL, and a shared repository. The detailed API-abuse, SSRF, retention, and operational controls in this document are engineering safeguards proposed for a production-ready public prototype; they are not represented as separately enumerated requirements of the assessment.
