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

## Python Environments

- Use one virtual environment per component (`server`, `ingestor`, `benchmark`).
- Each component has its own `pyproject.toml` (metadata/tooling) and `requirements*.txt` (pinned install lists).

### Dependency strategy

- Source of truth: keep intent in `pyproject.toml` per component, and generate pinned `requirements*.txt` (e.g., with `pip-compile pyproject.toml -o requirements.txt` and `pip-compile --extra dev pyproject.toml -o requirements-dev.txt`).

## Tooling

- Ruff is configured in `.ruff.toml` for linting/formatting.
- Run checks: `ruff check server ingestor benchmark`
- Run formatting: `ruff format server ingestor benchmark`
- VS Code settings are in `.vscode/settings.json` (Ruff on save, formatter set to Ruff).

## Documentation

- API usage: `server/README.md`
- Database setup: `database/README.md`
- Ingestion: `ingestor/README.md`
