# Pan‑Finder

(This project is under active development; use at your own risk. If you have any questions or issues, please use the discussion forum.)

Search API for scientific documents combining vector similarity (pgvector), full‑text, and structured filters, with SSE streaming and LLM‑based query parsing.

## Overview
- Backend: `server/` (FastAPI). Endpoints stream results via Server‑Sent Events (SSE).
- Data: PostgreSQL with `pgvector` + `postgresql-unit` (see `database/`).
- Ingestion: `ingestor/` contains starter scripts (the ingestor service is not yet finalized).
- Evaluation: `benchmark/` runs LLM‑driven parsing and ranking tests, and generates plots.
- Optional UI: `searchui/` SPA for demos; backend works independently.

## Quick start (dev)
1) Download the embedding model into `models/all-MiniLM-L12-v2/`:
	 https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2

2) Create `.env` in the repo root from `.env.example` and set required variables (see `server/README.md`). Minimum required:
	 - `DATABASE_URL`
	 - `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`
	 - `TURNSTILE_SECRET_KEY`

3) Start the stack:
```bash
docker compose -f docker-compose.dev.yml up
```

## API
API usage (endpoints, session handling, SSE examples) is documented in `server/README.md`.

## Benchmarking
Evaluate RRF settings and prompts using datasets in `benchmark/queries/`.
```bash
cd benchmark
./run.sh
```
Outputs CSVs and plots to `benchmark/results/`.

## Database
- Schema: `database/schema.sql` (includes `pgvector` + `postgresql-unit`).
- Applying schema: `database/README.md` has examples for Docker and local Postgres.

## Ingestor
`ingestor/` provides a basic framework for ingesting documents, creating chunks, populating filters, and deriving numeric filters (the service is not yet finalized). See its `README.md`.

## Optional UI
You can use the bundled `searchui/` or the external repo https://github.com/panosc-eu/searchui/tree/pan-finder-page. By default, the UI expects the API at http://127.0.0.1:8080.
