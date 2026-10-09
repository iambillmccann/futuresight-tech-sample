# ReviewLens AI — Milestone 1 checkpoints

## Foundation
- Bootstrapped the Vite + React + TypeScript frontend shell and configured the workspace for a ReviewLens-style analysis UI.
- Initialized the FastAPI backend skeleton and synchronized the frontend proxy to the local API.

## Ingestion
- Added a Google Maps URL validation flow and a seeded review dataset for the Mint Plaza Blue Bottle example.
- Confirmed the ingestion endpoint normalizes the source key and returns real summary metadata.

## Cache and summary
- Added a shared in-memory cache keyed by normalized source to avoid duplicate ingestion.
- Displayed aggregate rating, review count, and sample review evidence in the main workspace.

## Q&A
- Added a chat transcript UI and direct Q&A calls against the active source dataset.
- Returned answer payloads with matching evidence excerpts to mimic grounded review analysis.

## Scope guards
- Enforced an active-dataset-only prompt guard to decline unrelated general knowledge and cross-platform questions.
- Added validation tests for supported prompts and out-of-scope refusals.
