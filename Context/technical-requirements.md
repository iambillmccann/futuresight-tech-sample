# ReviewLens AI — Three-Milestone Requirements

**Purpose:** Deliver the FutureSight ReviewLens AI technical assessment as one coherent, publicly accessible review-intelligence application.

**Source and scope:** Consolidated from the three Fall 2026 ReviewLens AI capstone sprint backlogs, revised for the FutureSight technical assessment and the architectural decisions made for this short-lived demonstration. This is a personal implementation backlog, not a student assignment or team grading specification. Delivery is organized into three sequential milestones: local operation, AWS deployment, and optional enhancements.

**Supported platforms:** Google Maps is the sole platform required for Milestones 1 and 2. Amazon customer reviews are an optional additional ingestion target in Milestone 3. **SerpApi** is the selected ingestion provider for Google Maps; any Amazon support must use a verified, supported ingestion mechanism and must not be assumed to be available through the same SerpApi endpoint.

**Primary workflow:** Supply a Google Maps URL → ingest real reviews → inspect an ingestion summary → ask review-grounded questions → see explicit refusals for out-of-scope questions. The entire workflow must be available without a login at a public URL.

## Architecture and scope decisions

1. **Standalone implementation.** Build ReviewLens from scratch; do not assume Cornerstone, an existing application shell, CI, deployment, database, or services. The intended stack is React, TypeScript, and Vite for the frontend, and Python and FastAPI for the backend.
2. **Selected providers and configuration.** Use SerpApi for Google Maps review ingestion and OpenAI for review-grounded Q&A, with `gpt-4.1-mini` as the default model. Provider credentials and the model name are configured through server-side environment variables (`SERPAPI_API_KEY`, `OPENAI_API_KEY`, `OPENAI_MODEL`), with `OPENAI_MODEL=gpt-4.1-mini` in the example configuration. The backend must not embed credentials or hard-code the model name. Keep both integrations behind focused adapters/services.
3. **No authentication or ownership.** The frontend and API are anonymously accessible. There are no accounts, users, tenants, authenticated sessions, or owner-scoped records.
4. **No database or durable application storage.** Use a single FastAPI backend instance and an in-process, shared review-dataset cache. Do not introduce PostgreSQL, an ORM, migrations, Redis, disk persistence, or stored analysis/chat histories for the assessment.
5. **Cache by source, not by visitor.** Canonicalize a submitted Google Maps source using a **stable provider identifier when available** (prefer the canonical Google Maps Place ID or equivalent returned by SerpApi); **fall back to a normalized source URL when no stable identifier is available**. Do not build an exhaustive URL-resolution subsystem. Different URL forms that resolve to the same stable identifier must share a cache entry; normalized-URL fallback may not deduplicate every equivalent URL. A cache hit reuses previously normalized reviews and their computed summary instead of contacting the ingestion provider again.
6. **Transient cache lifecycle.** Start with a configurable 24-hour TTL and a modest maximum cache size/review count chosen to protect backend memory. Cache entries include source metadata, normalized reviews, summary, retrieval timestamp, and expiration. Expiry, eviction, process restart, or deployment may remove all data; the user can ingest again. The cache is not a saved-analysis feature or durability guarantee.
7. **Coalesce concurrent cache misses.** If requests for the same source arrive while ingestion is running, share one in-flight ingestion operation rather than issuing duplicate provider calls. A failure must not be cached as a successful dataset.
8. **Keep active context, not history.** The frontend tracks the currently selected source/cache identifier and optionally a visible, unsaved Q&A transcript for the open page. Every Q&A request resolves its review context from the server cache for that source. No personal libraries, Save/Save As, rename, reopen, delete, or persisted chat history.
9. **Delegate paid-provider quotas.** Do not implement application-level per-IP/global rate limiting, daily token budgets, or a provider-quota accounting system. Let the ingestion and LLM providers enforce their own account limits and return appropriate, safe, intelligible errors when requests are throttled or exhausted. Reasonable request validation, network safeguards, timeouts, and bounded LLM context remain required.
10. **Short-lived assessment deployment.** Run one backend instance on AWS at a public hosting URL, without a custom domain or URL shortener. Share the URL only with FutureSight; do not treat its obscurity as authentication or a security boundary. No scalability or enterprise operations requirements. Redis or a database would only be a possible future replacement for the in-memory cache, not an implementation requirement.
11. **Prioritize FutureSight's baseline.** Real review ingestion, truthful ingestion summary, review-grounded Q&A and scope refusal, public deployment, repository, complete AI transcripts, Loom video, and README are required. Browsing, filtering, exports, refresh, and detailed evidence exploration are optional enhancements.

## Canonical business rules

### Access, security, and operating limits

- **BR-001:** ReviewLens is accessible to anonymous visitors without login or account creation.
- **BR-002:** Backend endpoints validate inputs and request sizes independently of the frontend, and accept only the operations required for ingestion, summary, and grounded Q&A. No application-specific per-user or per-IP rate limiter is required.
- **BR-003:** In Milestones 1–2, ingestion accepts supported Google Maps URLs only; optional Milestone 3 may additionally accept validated Amazon product URLs. URL resolution, redirects, and outbound requests must not be usable for SSRF or access to loopback, private, link-local, or metadata endpoints. Prefer a fixed, trusted ingestion-provider API over arbitrary server-side URL fetching.
- **BR-004:** Review-ingestion and LLM API credentials remain server-side and outside the repository or browser assets. No database or authentication credentials are required.
- **BR-005:** Bound request payload sizes, outbound-call timeouts, normalized dataset size, and LLM context size. Third-party ingestion/LLM account quota and throttling limits are authoritative; ReviewLens does not replicate them with local consumption budgets or custom rate limiting.
- **BR-006:** Map provider 429/rate-limit, quota-exhaustion, timeout, unavailable-service, and invalid-source failures into useful, sanitized client messages. Never expose API keys, upstream raw error bodies, or tracebacks.

### Active analysis and ingestion

- **BR-007:** Milestones 1 and 2 support Google Maps only, using SerpApi for review ingestion. Amazon is optional in Milestone 3 and must not be implemented during Milestone 1.
- **BR-008:** Each active analysis identifies a supported platform and entity/source and its corresponding shared cached dataset; it has no user owner or durable saved-analysis record.
- **BR-009:** A visitor can submit a source URL and initiate actual review retrieval. A supplementary data import may be offered as a recovery path, but must be clearly distinguished from URL ingestion.
- **BR-010:** Successfully normalized reviews contain review text and rating. Preserve useful source metadata, such as review ID, author, date, or URL, when available.
- **BR-011:** Failed or incomplete ingestion must never be disguised with fabricated reviews. Report success, failure, and partial success when applicable.
- **BR-012:** The ingestion summary is derived from the exact current dataset used by Q&A. It includes review count and useful rating information, and identifies any skipped/rejected records when known.
- **BR-013:** Changing the frontend’s active source must change the cached dataset used by subsequent Q&A. Reviews from a previously selected source must not enter the new model context.
- **BR-014:** No usable ingested reviews means no normal review-grounded Q&A answer.
- **BR-014A:** For Google Maps, cache by a stable provider business identifier (prefer Place ID or equivalent) when available; otherwise use a normalized source URL. Serve unexpired hits without re-ingestion and coalesce simultaneous misses for the same resolved cache key. Cache entries expire after a configurable TTL (initially 24 hours) and may disappear on restart or eviction; there is no persistence guarantee.
- **BR-014B:** If a source is absent or expired when Q&A is requested, return a clear expired/unavailable-dataset response directing the visitor to ingest again rather than answering without evidence.

### Review-grounded AI

- **BR-015A:** Use OpenAI for Q&A. Read the model from the server-side `OPENAI_MODEL` environment variable, defaulting through documented configuration to `gpt-4.1-mini`; never place `OPENAI_API_KEY` in browser-delivered code.

- **BR-015:** Q&A may answer questions only about reviews in the active dataset; it must not supplement evidence with general world knowledge or other review platforms.
- **BR-016:** The system prompt explicitly defines the active entity, source platform, evidence boundary, refusal behavior, and response expectations. Prompt-level scope enforcement is primary; application validation may reinforce it.
- **BR-017:** When the review evidence is insufficient for an otherwise relevant question, the response clearly communicates that limitation instead of inventing an answer.
- **BR-018:** General-knowledge requests, unrelated entities, and questions about unavailable platforms are explicitly declined.
- **BR-019:** Review content is untrusted input, not instructions. The model must not follow instructions embedded in review text that conflict with its system scope.
- **BR-020:** No particular retrieval strategy, embeddings system, vector database, or RAG framework is required. Choose the simplest approach that works for the dataset and token budget.

### Delivery and quality

- **BR-021:** The application is deployed on AWS and accessible by public URL with no authentication prerequisite.
- **BR-022:** Full source code, setup steps, architecture, assumptions, and limitations are available in a GitHub repository.
- **BR-023:** Complete AI-assisted development session transcripts, including unsuccessful attempts, are retained in `/ai-transcripts` in the repository in accordance with the assessment.
- **BR-024:** A Loom demonstration under three minutes covers ingestion, summary, review-grounded Q&A, a scope-guard refusal, key design tradeoffs, and what could be improved.
- **BR-025:** Engineering tests must be repeatable without depending on live third-party review pages or nondeterministic live-model wording.

## API contract and milestone execution boundaries

- **REST API contract:** Define and document the minimum endpoints required to ingest a Google Maps source, retrieve its current summary/status, and ask a question against its cache identifier. Document request/response schemas, validation behavior, and stable error envelopes/status codes (including invalid URL, missing or expired cache entry, upstream throttling/quota, and timeout). Copilot may choose endpoint names and exact schema shapes, but these must be consistent and captured in the README or an API reference before Milestone 1 is considered complete.
- **Milestone boundary:** Milestone 1 is strictly local development and functionality; it must not provision or deploy AWS infrastructure or implement Milestone 3 features, including Amazon ingestion. Milestone 2 deploys the already validated baseline and prepares handoff artifacts. Milestone 3 remains optional.
- **External configuration:** Supply `.env.example` entries for `SERPAPI_API_KEY`, `OPENAI_API_KEY`, and `OPENAI_MODEL=gpt-4.1-mini`, plus required frontend/backend configuration. Never commit live values. Fail clearly when required settings are missing.

## Engineering and test baseline

- Maintain readable coding, UI/UX, and security guidance appropriate to the actual application; do not preserve obsolete authentication and ownership instructions.
- Run build, lint/static checks, and automated tests in GitHub Actions (or equivalent CI). Add integration tests where ingestion, in-memory cache, summary, and model orchestration meet. Avoid disproportionate release infrastructure for this assessment.
- Test valid and invalid URLs; unsupported hosts; redirect/SSRF attempts; malformed provider responses; partial or failed ingestion; summary accuracy; cache hit/miss/expiry; concurrent same-source requests; empty data; correct active dataset; out-of-scope refusals; prompt-injection attempts; provider 429/quota failure; and timeouts.
- Mock the review provider and LLM in CI. Maintain a small evaluation set with in-scope, insufficient-evidence, other-entity, other-platform, and unrelated questions. Test behaviors and context selection rather than requiring exact prose.
- Store normalized review datasets only in backend process memory, with a configurable TTL and simple size/eviction bounds. No disk/database persistence. A browser refresh need not restore an analysis; backend restarts clear the cache.

## Milestone 1 — Local application and complete assessment workflow

**Goal:** Build and run the full required ReviewLens functionality locally on the development device. This is the development and functional-validation milestone; public hosting is not necessary to complete it.

**Completion criteria:** From a locally running frontend and backend, enter a Google Maps URL, ingest or reuse actual review data, inspect the summary, ask grounded questions, receive scope refusals, and pass automated tests. All functionality is anonymous and uses an ephemeral shared backend cache.

### Foundation and API security

### RL-001 — Prepare the Application for Public Anonymous Access

**Outcome:** ReviewLens opens directly to its analysis experience; neither the frontend nor the API requires user authentication.

**Technical Guidance:** Implement the public React/Vite application shell and FastAPI endpoints from scratch. Do not create Clerk integration, authentication middleware, user tables, owner columns, or saved-analysis infrastructure. The public REST API supports the assessment workflow without bearer tokens.

**Acceptance:** A fresh anonymous browser can complete the workflow. No login, protected-route redirect, bearer token, or user model is required. Tests cover anonymous access and input/network safety.

**Rules:** BR-001, BR-002, BR-008.

### RL-002 — Establish Engineering, CI, and Secret Configuration

**Outcome:** The application builds, tests, and runs locally and in CI using documented configuration without disclosing credentials.

**Technical Guidance:** Create the React/Vite frontend and FastAPI backend from scratch; no Cornerstone components or services are assumed. Use `.env.example` with `SERPAPI_API_KEY`, `OPENAI_API_KEY`, and `OPENAI_MODEL=gpt-4.1-mini`; load these settings on the backend only. Include consistent logging, test fixtures, and a documented REST API contract (request/response schemas and stable error behavior). Integrate build, lint, unit tests, and selected integration tests into CI. Maintain only the engineering context documentation that meaningfully guides the implementation.

**Acceptance:** Local startup is reproducible; failing tests fail CI; provider keys are absent from the browser bundle and repository.

**Rules:** BR-004, BR-021, BR-022, BR-025.

### RL-003 — Harden the Anonymous API

**Outcome:** The anonymous backend exposes only the necessary, validated ingestion and review-grounded Q&A operations and handles upstream limits safely.

**Technical Guidance:** Validate input schemas and lengths; restrict ingestion sources to Google Maps and prevent SSRF through redirect/destination validation or trusted-provider-only fetching. Set request, dataset, and model-context size bounds and outbound timeouts. Keep credentials on the backend. Do not implement custom IP rate limiting, application-wide token budgets, or provider quota counters. Translate provider throttling, quota, and timeout responses into stable safe errors. This is a short-lived demonstration, not an abuse-proof SaaS endpoint.

**Acceptance:** Negative-path tests cover invalid/internal URLs, excessive payloads, provider rate-limit or quota exhaustion, timeouts, and safe error responses. Direct API requests cannot bypass URL and payload validation.

**Rules:** BR-002–BR-006.

### Ingestion, cache, and summary

### RL-004 — Submit and Validate a Review Source

**Outcome:** An anonymous visitor can enter a Google Maps URL and start an analysis.

**Technical Guidance:** Provide a clear Google Maps URL input, validation message, processing state, and currently supported platform indication. Milestone 1 must not include Amazon ingestion. Identify the target/entity from provider data where practical rather than requiring a separate saved AnalysisTarget workflow. The backend validates the URL independently of the browser.

**Acceptance:** Valid supported URLs start ingestion; malformed and unsupported URLs fail clearly without provider calls.

**Rules:** BR-007–BR-009.

### RL-005 — Retrieve and Normalize Real Reviews

**Outcome:** A supplied review URL produces a usable collection of actual review records, or an explicit ingestion failure.

**Technical Guidance:** Integrate **SerpApi** for Google Maps review ingestion using server-side `SERPAPI_API_KEY`. Convert supported input URLs to SerpApi request parameters without arbitrary URL fetching; resolve a stable business/Place ID when the provider supplies one. Normalize review text, rating, and available metadata into a canonical representation. Handle malformed individual records, provider timeouts, quota exhaustion, and empty responses without fabricating fallback data. Use deterministic fixtures for tests.

**Acceptance:** Representative provider records normalize correctly; invalid records are rejected consistently; failures do not appear as success.

**Rules:** BR-009–BR-011.

### RL-006 — Implement Shared In-Memory Review Cache

**Outcome:** The single FastAPI process reuses ingested reviews across anonymous visitors requesting the same Google Maps business, and ingestion, summary, and Q&A operate on the same cached dataset.

**Technical Guidance:** Build an in-process cache keyed by a **stable SerpApi/Google Maps business identifier (prefer Place ID) when available, otherwise a normalized source URL**. Document the normalization fallback; do not assume every Google Maps URL form can be collapsed to one canonical business. Associate source metadata, normalized reviews, derived summary, `fetched_at`, and `expires_at` with each entry. A cache hit returns the cached dataset without another provider call. Use a configurable TTL (default 24 hours) and simple bounded cache size/review count; eviction or restart loses entries. Coalesce concurrent misses for the same key into one provider request. The frontend stores the active platform-qualified source/cache identifier but no owner or saved-history information. Use neither database nor Redis.

**Acceptance:** Two visitors requesting the same source reuse the same cache entry; two simultaneous misses trigger one ingestion; distinct businesses remain isolated in Q&A context; expired/evicted entries require re-ingestion; restart is allowed to clear everything. No persistent data or authentication exists.

**Rules:** BR-008, BR-012–BR-014B.

### RL-007 — Report Ingestion Results and Summary

**Outcome:** The visitor can tell what ReviewLens actually ingested and whether it is sufficient for analysis.

**Technical Guidance:** Show entity/source, ingestion state, successfully ingested review count, and rating summary such as average rating and/or rating distribution. Report skipped/rejected review counts when available. Derive every number from the current normalized dataset; do not generate summary statistics with the LLM.

**Acceptance:** Fixture-based tests exactly match displayed counts and ratings. Empty, failure, and partial results have distinct, honest explanations.

**Rules:** BR-011–BR-014.

### Review-grounded Q&A and scope guard

### RL-008 — Build the Question-and-Answer Interface

**Outcome:** A visitor can ask natural-language questions about the active reviews and read responses in the analysis workspace.

**Technical Guidance:** Include input, submit, loading, answer, and error states, with visible current entity/platform context. A current-page transcript can be maintained in UI memory to support natural interaction, but it is not saved or restored after refresh. No chat-history database or previous-analysis sidebar is required.

**Acceptance:** A question can be submitted against ingested reviews. Empty datasets disable or reject normal Q&A. Browser refresh need not restore questions.

**Rules:** BR-014–BR-015.

### RL-009 — Construct Evidence-Bounded Model Context

**Outcome:** Each model request is grounded in the active analysis reviews, within bounded model context and provider-enforced account limits.

**Technical Guidance:** Call the OpenAI API using server-only `OPENAI_API_KEY` and the model selected by `OPENAI_MODEL` (default `gpt-4.1-mini`). Load reviews from the active source’s unexpired backend cache entry. Supply all reviews when small enough, or use a bounded retrieval/filtering strategy for larger datasets. Clearly identify entity and source platform. Treat review text as untrusted data. Ensure prior-source reviews cannot enter a new question. Handle cache expiry and LLM-provider throttling/quota failure explicitly. No mandatory vector store or embeddings architecture.

**Acceptance:** Tests inspect mocked model inputs to verify correct cache-key selection, context-size bounds, absence of stale-source reviews, and prompt boundaries; an expired cache entry does not trigger ungrounded Q&A.

**Rules:** BR-013–BR-015, BR-019–BR-020.

### RL-010 — Answer Supported Questions and Acknowledge Missing Evidence

**Outcome:** ReviewLens answers questions supported by the dataset and explicitly acknowledges when evidence is absent.

**Technical Guidance:** Support questions about recurring complaints, positive themes, low-rating patterns, and service concerns. Do not invent review facts, reviewer quotations, or certainty. Distinguish an in-scope but unanswerable question from an unrelated question.

**Acceptance:** Controlled test sets demonstrate useful answers to supported questions and an evidence-insufficiency response to unsupported factual inferences.

**Rules:** BR-015, BR-017.

### RL-011 — Enforce the System-Prompt Scope Guard

**Outcome:** ReviewLens declines unrelated general questions and questions about entities or review platforms outside the active dataset.

**Technical Guidance:** Version the system prompt with the code. It should declare the active review-only scope, evidence restrictions, refusal criteria, and how to handle instructions embedded in reviews. Do not implement a brittle hard-coded blacklist of example questions. Add tests for weather/general knowledge, other businesses, other platforms, and prompt injection.

**Acceptance:** In-scope questions are accepted; irrelevant or cross-platform questions receive explicit, helpful refusals; review text cannot override system scope in representative tests.

**Rules:** BR-015–BR-019, BR-025.

## Milestone 2 — Deploy to Amazon Web Services

**Goal:** Deploy the locally validated application to AWS and complete the required FutureSight review handoff. Use a single backend instance, no persistent database, no authentication, and no custom domain.

**Completion criteria:** The AWS-hosted application works end-to-end at its public URL; the GitHub repository contains source, README, and AI session transcripts; a Loom walkthrough under three minutes is ready for FutureSight.

### Deployment and assessment deliverables

### RL-012 — Deploy ReviewLens to a Public URL

**Outcome:** The complete application works from a stable, publicly accessible URL without authentication.

**Technical Guidance:** Deploy the standalone frontend and one FastAPI backend instance to Amazon Web Services (AWS), using a straightforward AWS hosting arrangement appropriate to a short-lived assessment. Document the selected AWS services and configuration; avoid additional infrastructure unless required by the chosen deployment approach. Do not require a database, Redis, authentication, custom domain, or URL shortener. Configure provider secrets through hosting settings. Confirm ingestion, cache reuse, summary, Q&A, scope guard, and provider-failure messaging from the deployed frontend. Configure CORS appropriately. Use the AWS-provided public URL where practical and share it only with FutureSight; do not purchase a custom domain or use a URL shortener. URL obscurity is not a security boundary.

**Acceptance:** The AWS-hosted public URL supports the complete review-to-Q&A flow with no login; frontend-to-backend requests and CORS work from the deployed location. Secrets are not present in client-delivered assets.

**Rules:** BR-001–BR-006, BR-021.

### RL-013 — Prepare Repository, AI Transcripts, and README

**Outcome:** A reviewer can inspect and run the source and understand implementation choices and tradeoffs.

**Technical Guidance:** Publish the complete code in GitHub. Provide from-scratch local setup, required environment variable names, standalone architecture, single-instance/in-memory-cache limitations, ingestion approach, scope-guard strategy, public API validation, provider-enforced quotas, assumptions, and known limits in `README.md`. Include full unedited AI development session transcripts in `/ai-transcripts`, including dead ends, as requested by FutureSight. Before sharing, ensure no secrets or personal sensitive information are present in transcripts; if unavoidable, document necessary redactions rather than silently misrepresenting completeness.

**Acceptance:** Repository can be cloned and configured; requested transcripts are present; README explains how to exercise the solution.

**Rules:** BR-022–BR-023.

### RL-014 — Record the Assessment Walkthrough

**Outcome:** A Loom video of less than three minutes demonstrates the delivered product and the important engineering decisions.

**Technical Guidance:** Show real source ingestion, trustworthy summary, an in-scope review question, and an explicitly rejected out-of-scope question. Briefly explain architecture/prompt and security tradeoffs, one choice worth highlighting, and what would be improved with more time. Provide the public URL and GitHub repository to the hiring team.

**Acceptance:** Video duration is under three minutes and covers the required end-to-end sequence.

**Rules:** BR-021–BR-024.

## Milestone 3 — Optional features

**Goal:** Enhance the review-analysis experience only after Milestones 1 and 2 are complete. These stories are optional and do not block the FutureSight baseline. They must preserve the anonymous, no-history, in-memory architecture.

**Completion criteria:** No mandatory completion gate. Each optional story is independently deliverable and testable.

### RL-015 — Display Supporting Review Evidence

**Outcome:** Answers can show real supporting review excerpts or stable source identifiers.

**Technical Guidance:** Cite only reviews in the active cached dataset; do not fabricate excerpts, author metadata, or review identifiers.

**Acceptance:** Representative answers link to verifiable records from the active dataset, without mixing sources.

**Rules:** BR-013, BR-015, BR-019.

### RL-016 — Browse and Filter Reviews

**Outcome:** Visitors can inspect the active cached reviews beyond the summary and optionally filter by rating or review date.

**Technical Guidance:** Read from the current cached dataset, not saved history; handle pagination or incremental loading if needed. Filtering must not alter the underlying reviews.

**Acceptance:** Browsing reflects the active source; filtering returns the expected subset; an expired dataset prompts re-ingestion.

**Rules:** BR-008, BR-013–BR-014B.

### RL-017 — Refresh a Cached Dataset

**Outcome:** Visitors can request fresh reviews for the active source without depending on cache TTL expiry.

**Technical Guidance:** Invalidate or bypass the entry intentionally; avoid duplicate records. On failure, retain the previous usable dataset where possible. If the provider returns a partial dataset, merge carefully rather than treating it as a complete replacement.

**Acceptance:** A successful refresh updates the cache and summary; a failed refresh does not incorrectly destroy the last known-good dataset.

**Rules:** BR-010–BR-014B.

### RL-018 — Export Current Reviews or Session Analysis

**Outcome:** Visitors can download current review data as CSV and/or a current-session analysis summary as Markdown.

**Technical Guidance:** Export only the active cached review dataset and available current-page analysis. Do not introduce saved-analysis records, ownership, or persisted chat history for export.

**Acceptance:** Generated files contain the correct active source and content, with useful filenames and no fabricated values.

**Rules:** BR-008, BR-012–BR-015.

### RL-019 — Add Amazon Review Ingestion (Optional)

**Outcome:** A visitor can submit a supported Amazon product URL and analyze genuine customer reviews through the existing ingestion-summary and review-grounded Q&A workflow.

**Technical Guidance:** Add Amazon as a **second platform only in Milestone 3**. Confirm that a permitted, functioning review-data mechanism is available before implementation; do not assume the SerpApi Google Maps Reviews API also supports Amazon reviews. Introduce an Amazon-specific ingestion adapter while retaining the shared normalized `Review`/dataset shapes. Include the platform in cache keys so identical source identifiers across different platforms never collide; prefer a stable Amazon product identifier (such as ASIN) when available, otherwise a normalized product URL. Keep reviews and model context isolated to the currently active product and platform; the scope guard must reject requests for reviews from an unselected platform.

**Acceptance:** Valid supported Amazon product URLs yield real, normalized reviews or an explicit provider failure; invalid/unsupported URLs are rejected; cache lookup, summary, and Q&A behave correctly without mixing Google Maps and Amazon datasets. Google Maps remains functional and regression tests pass.

**Rules:** BR-009–BR-020, with BR-007 extended for this optional milestone only.

## Explicitly out of scope

- Authentication, registration, login/logout, user profiles, organizations, roles, and tenant ownership.
- User-scoped resources, cross-user permission checks, or private data vaults.
- A database, ORM, schema migrations, Redis, or durable application storage.
- Custom per-IP rate limiting, application token budgets, and quota-accounting infrastructure.
- Multiple backend instances, distributed cache coherence, or high-availability service design.
- Saved analyses, named analysis history, Save As, renaming, reopening, and deletion workflows.
- Persisted conversation history, multi-session memory, and history restoration.
- Multiple review platforms **in Milestones 1–2**. Amazon is the sole optional second platform in Milestone 3; other platforms and competitor comparisons remain out of scope.
- General-purpose AI chat or questions answered from external world knowledge.
- Mandatory embeddings, vector database, or particular RAG framework.
- Advanced dashboards, custom model training, sophisticated sentiment pipelines, and numerical confidence scoring without a defensible method.
- Enterprise-scale deployment mechanisms such as Kubernetes, canary releases, or multi-region infrastructure.

## Acceptance checklists by milestone

### Milestone 1 — Local workflow

- [ ] Local visitor can open ReviewLens without authenticating; Amazon ingestion and AWS deployment are not part of this milestone.
- [ ] SerpApi ingests Google Maps reviews; OpenAI Q&A uses the backend-configured `OPENAI_MODEL` (default `gpt-4.1-mini`); provider keys stay server-side.
- [ ] Public REST endpoints have documented request/response schemas and predictable validation/error responses.
- [ ] Valid Google Maps URL initiates real ingestion; unsupported/malicious URLs are rejected.
- [ ] Real normalized reviews form a shared in-memory cached dataset keyed by source; repeated visits reuse the dataset without fabricated fallback content.
- [ ] Ingestion summary truthfully reports count, rating information, and relevant failure/partial states.
- [ ] Q&A answers supported questions only from that dataset and acknowledges missing evidence.
- [ ] Q&A explicitly declines general-knowledge, other-entity, and other-platform requests.
- [ ] Cache hits, misses, expiry, and simultaneous same-source requests behave correctly; changing the active source does not leak prior review context.
- [ ] API applies meaningful validation, SSRF defense, bounded request/context sizes, timeouts, and safe handling of provider rate limits and exhausted quotas; no custom rate limiter is required.
- [ ] Automated tests pass in CI, including deterministic scope-guard tests.

### Milestone 2 — AWS deployment and handoff

- [ ] AWS public deployment works end-to-end; source and secrets are handled appropriately.
- [ ] GitHub repository contains README and complete appropriately sanitized AI transcripts.
- [ ] Loom walkthrough is under three minutes and includes all requested flow and commentary.

### Milestone 3 — Optional enhancements

- [ ] Supporting review evidence, if implemented, references real reviews.
- [ ] Review browsing/filtering, if implemented, uses the active cache.
- [ ] Manual refresh, if implemented, preserves data integrity.
- [ ] Amazon ingestion, if implemented, uses an explicitly validated data provider and preserves platform-aware cache isolation.
- [ ] CSV/Markdown export, if implemented, does not require durable history.
