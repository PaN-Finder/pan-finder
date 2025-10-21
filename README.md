# Pan‑Finder

Search API for scientific documents combining vector similarity (pgvector), full‑text, and structured filters, with SSE streaming and LLM‑based query parsing.

## Quick Start

1. **Download embedding model** into `models/all-MiniLM-L12-v2/`:
   ```
   https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2
   ```

2. **Configure backend**: Create `server/.env.dev` from `server/.env.example` and set:
   - `DATABASE_URL`
   - `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`
   - `ENABLE_TURNSTILE=false` (for local dev)

3. **Configure frontend**: Create `frontend/.env.dev` from `frontend/.env.example` and set:
   - `REACT_APP_ENABLE_TURNSTILE=false` (for local dev)

4. **Start**:
   ```bash
   docker compose -f docker-compose.dev.yml up
   ```

## Project Structure

- `server/` - FastAPI backend with SSE streaming
- `frontend/` - React frontend
- `database/` - PostgreSQL schema with pgvector + postgresql-unit
- `ingestor/` - Document ingestion scripts
- `benchmark/` - Evaluation tools for search performance

## Documentation

- API usage: `server/README.md`
- Database setup: `database/README.md`
- Ingestion: `ingestor/README.md`
