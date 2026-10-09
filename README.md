# ReviewLens AI

ReviewLens AI is a locally hosted, public-access review analysis prototype for a Google Maps business. It ingests a source URL, summarizes the dataset, and answers grounded questions while refusing unrelated or out-of-scope prompts.

## Features
- Public, unauthenticated local web app experience
- Google Maps URL validation and ingestion flow
- Shared in-memory cache for repeated review retrievals
- Summary cards derived from the active dataset
- Q&A transcript grounded in the selected business reviews
- Scope guard that declines weather, competitor, and cross-platform questions

## Local setup

1. Create and activate a Python virtual environment:
   ```bash
   cd /path/to/futuresight-tech-sample
   python3 -m venv .venv
   . .venv/bin/activate
   pip install -r backend/requirements.txt
   ```
2. Start the API server:
   ```bash
   cd /path/to/futuresight-tech-sample
   . .venv/bin/activate
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```
3. In a second terminal, install the frontend dependencies and run the app:
   ```bash
   cd /path/to/futuresight-tech-sample/frontend
   npm install
   npm run dev -- --host 0.0.0.0
   ```
4. Open the frontend at `http://localhost:5173`.

## Default source
- The app starts with a sample Google Maps business URL for Blue Bottle Coffee — Mint Plaza and seeded review data.

## Validation
```bash
cd /path/to/futuresight-tech-sample
. .venv/bin/activate
pytest backend/test_app.py -q
cd frontend
npm run build
```

## Notes
- This milestone uses a local in-memory, single-instance cache by design and does not persist review history across restarts.
- The Q&A flow remains intentionally scoped to the active dataset rather than open-ended general knowledge.
