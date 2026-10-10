# ReviewLens AI

ReviewLens AI is a public, local-first review intelligence workspace for Google Maps businesses. It retrieves real review data through SerpApi, computes an honest ingestion summary, and uses OpenAI to answer questions only from the active cached dataset.

Milestone 1 is intentionally anonymous and ephemeral: there are no accounts, saved analyses, databases, or durable chat histories.

## Architecture

- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **Backend:** FastAPI and Pydantic
- **Review provider:** SerpApi Google Maps and Google Maps Reviews APIs
- **Q&A provider:** OpenAI Chat Completions API with structured JSON output
- **Storage:** bounded, process-local TTL cache

The backend validates a full `google.com/maps` URL and sends only derived search/provider identifiers to SerpApi. It never fetches the submitted URL. SerpApi records are normalized into a shared review model; malformed records are skipped and reported. The cache prefers the stable Place ID or SerpApi data ID returned by the provider and falls back to a normalized URL hash when an identifier is not present in the submitted URL.

Each Q&A call resolves the active source key from the backend cache. The versioned system prompt names the current business and platform, treats review text as untrusted evidence, prohibits external knowledge, requires explicit refusals, and distinguishes insufficient evidence from an out-of-scope request. Review context, dataset size, request lengths, provider timeouts, and cache size are bounded.

## Prerequisites

- Python 3.8 or newer
- Node.js `^20.19.0` or `>=22.12.0` (required by Vite 8)
- SerpApi API key with Google Maps access
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

Open `http://localhost:5173`, paste a full Google Maps place URL, and select **Analyze Reviews**.

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
| `POST` | `/api/ingest` | Validate a Google Maps URL, retrieve reviews, and return source metadata plus a computed summary |
| `POST` | `/api/chat` | Ask a question against an unexpired `source_key` |

Ingestion request:

```json
{"source_url": "https://www.google.com/maps/place/..."}
```

Chat request:

```json
{
  "source_key": "google-maps:place_id:...",
  "question": "What complaints recur in these reviews?"
}
```

Stable failures include invalid/unsupported URLs, missing or expired datasets, missing server configuration, provider rejection, throttling/quota exhaustion, malformed provider responses, and timeouts. Raw upstream bodies, credentials, and tracebacks are not returned.

## Validation

```bash
.venv/bin/pytest backend/test_app.py -q
.venv/bin/python -m compileall -q backend
cd frontend
npm run lint
npm run build
```

Tests use deterministic provider and model doubles; CI never depends on live SerpApi data or model wording. Coverage includes URL/SSRF validation, record normalization, computed summaries, cache hits and expiry, concurrent miss coalescing, source isolation, bounded model context, evidence validation, insufficient evidence, refusals, prompt injection boundaries, and sanitized provider failures.

## Assumptions and limitations

- Google Maps is the only Milestone 1 platform.
- A submitted URL must be a full `google.com/maps` location URL. Short-link resolution is deliberately excluded so the backend never follows user-controlled redirects.
- SerpApi determines available review coverage. `MAX_REVIEWS` bounds the exact normalized dataset used for both summary and Q&A.
- Cache state is shared by anonymous visitors in one backend process and disappears on expiration, eviction, or restart.
- Concurrent requests with the same submitted stable identifier or normalized URL share one in-flight ingestion. A previously resolved URL alias also reuses its stable provider-key entry.
- The frontend transcript exists only in the open page and is reset when the active source changes.
- Provider account quotas are authoritative; ReviewLens surfaces safe errors rather than implementing a second quota system.
- Milestone 1 does not include AWS deployment, authentication, a database, exports, or Amazon ingestion.
