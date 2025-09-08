# Pan‑Finder

Search API for scientific documents combining vector similarity (pgvector), full‑text, and structured filters, with SSE streaming and LLM‑based query parsing.

## Overview
- Backend: `server/` (FastAPI). Endpoints stream results via Server‑Sent Events (SSE).
- Data: PostgreSQL with `pgvector` + `postgresql-unit` (see `database/`).
- Ingestion: `ingestor/` contains starter scripts (ingestor service is not finalized).
- Evaluation: `benchmark/` runs LLM‑driven parsing + ranking tests and plots.
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

## How search works (high level)
- `POST /search` → LLM parses query to structured data (see `server/src/core/ai/prompts.py`).
- `SearchQueryBuilder` builds SQL with psycopg composables (no string concat), combining:
	- Vector similarity over documents and chunks (pgvector)
	- Full‑text search over titles (`to_tsquery`)
	- Structured filters with unit‑aware comparisons (`postgresql-unit`)
- Scores fused via Reciprocal Rank Fusion (RRF); final LIMIT 20.

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
`ingestor/` provides a basic framework to ingest documents, create chunks, populate filters, and derive numeric filters (service not finalized yet). See its `README.md`.

## Build images (optional, local)

### Server image
```bash
docker build -f server/docker/Dockerfile.k8s . -t registry.esss.lu.se/swap/pan-finder:server --platform linux/amd64
docker push registry.esss.lu.se/swap/pan-finder:server
```

### Frontend image (example args)
```bash
cd searchui
docker build \
	--build-arg API=https://federated.panosc.ess.eu/api \
	--build-arg PAN_FINDER_API=https://pan-finder-api.dev-sims.ess.eu \
	--build-arg TURNSTILE_SITE_KEY=*** \
	-f Dockerfile . -t registry.esss.lu.se/swap/pan-finder:frontend --platform linux/amd64
docker push registry.esss.lu.se/swap/pan-finder:frontend
```

### Custom Postgres image (with extensions)
```bash
docker build -f database/Dockerfile.postgresql . -t registry.esss.lu.se/swap/pan-finder:postgresql --platform linux/amd64
docker push registry.esss.lu.se/swap/pan-finder:postgresql
```

## Optional UI
You can use the bundled `searchui/` or the external repo https://github.com/panosc-eu/searchui. By default the UI expects the API at http://127.0.0.1:8080.