# Pan‑Finder Server

FastAPI service exposing the Pan‑Finder API with SSE streaming, LLM‑based query parsing, and PostgreSQL (pgvector + postgresql‑unit) integration.

## Run (dev)
- Ensure the embedding model exists at `models/all-MiniLM-L12-v2/` and root `.env` is configured (see Config).
- Start via top‑level compose:
```bash
docker compose -f ../docker-compose.dev.yml up
```

Health check
```bash
curl -s http://127.0.0.1:8080/health | jq
```

## Dependencies
- Python 3.12+
- Source of truth: `pyproject.toml` (runtime deps + dev extras). Pinned installs are generated `requirements*.txt`.
- Install (pinned):
  ```bash
  cd server
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  ```
- Dev/tooling (editable):
  ```bash
  pip install -e .[dev]
  ```

## Configuration
Loaded by `server/src/config.py` (`get_settings()`).

Required:
- `DATABASE_URL`

LLM provider settings:
- `LLM_PROVIDER` (`azure` or `openai`)
  - `LLM_PROVIDER=azure` requires the following configurations:
    - `AZURE_OPENAI_ENDPOINT`
    - `AZURE_OPENAI_API_KEY`
  - `LLM_PROVIDER=openai` might requires the following keys:
    - `OPENAI_BASE_URL` (optional) If not provided will use the official OpenAI endpoint. Please refer to the documentation of the library for more information.
    - `OPENAI_API_KEY`: required by the official OpenAI API. The key might be required in case of on-prem setup or if the service is provided by a third party.

Model selection (applies to both providers):
- `DEFAULT_MODEL_NAME` (optional) Please review the relevant code for the default value.
- `EXPLANATION_MODEL_NAME`(optional). Please review the relevant code for the default value.

Authentication & Security:
- `ENABLE_TURNSTILE` - Enable Cloudflare Turnstile bot protection
- `TURNSTILE_SECRET_KEY` (required if `ENABLE_TURNSTILE=true`) - Cloudflare Turnstile secret key

Common options:
- `EMBEDDING_MODEL_PATH` (default `/code/models/all-MiniLM-L12-v2`)
- `VALUE_VECTOR_KEYS` (optional comma-separated list of filter keys eligible for value-vector semantic matching and ingestion)
- `ALLOWED_ORIGINS` (default `*`), `API_HOST` (default `0.0.0.0`), `API_PORT` (default `8080`)
- `AZURE_OPENAI_API_VERSION` (only used when `LLM_PROVIDER=azure`)
- DB pool: `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`, `DB_CONNECTION_TIMEOUT`, `DB_MAX_IDLE`, `DB_MAX_LIFETIME`
- RRF: `RRF_K_SIMILARITY`, `RRF_K_CHUNK`, `RRF_K_FULL_MATCH`, `RRF_K_PARTIAL_MATCH`, `RRF_K_KEYWORD`, `RRF_K_VALUE_VECTOR`

## Endpoints

### Session Management
Session requirements depend on the `ENABLE_TURNSTILE` configuration:
- **If `ENABLE_TURNSTILE=true`**: All endpoints require `X-Session-ID` header. Create a session first using Turnstile token.
- **If `ENABLE_TURNSTILE=false`**: No session required. `X-Session-ID` header is optional.

#### Create session (when Turnstile is enabled)
```bash
curl -s -X POST http://127.0.0.1:8080/session/create \
  -H 'Content-Type: application/json' \
  -d '{"turnstile_token":"<TURNSTILE_TOKEN>"}'
```
Response contains `session_id` (use in subsequent calls).

### API Endpoints

#### Search (SSE)
```bash
curl -N -X POST http://127.0.0.1:8080/search \
  -H 'Content-Type: application/json' \
  -H "X-Session-ID: <session_id>" \
  -d '{"query":"Find datasets on graphene where temperature is between 99 and 101 K"}'
```
**Note**: Include `X-Session-ID` header only if `ENABLE_TURNSTILE=true`.

Streamed events: `analysis_started`, `analysis_completed`, `data_fetching`, `results`, optional `explanation_*`, `search_completed`.

#### Search with structured data (bypass LLM)
```bash
curl -N -X POST http://127.0.0.1:8080/search/structured \
  -H 'Content-Type: application/json' \
  -H "X-Session-ID: <session_id>" \
  -d '{
        "modified_query_id":"<previous_stat_id>",
        "structured_data":{
          "intention":"graphene",
          "keywords":["graphene"],
          "filters":{
            "logic":"AND",
            "conditions":[{"name":"temperature","operator":"BETWEEN","value":[99,101],"unit":"K"}]
          }
        }
      }'
```

#### Document details
```bash
curl -s http://127.0.0.1:8080/document/<url-encoded-doi> \
  -H "X-Session-ID: <session_id>"
```
**Note**: Include `X-Session-ID` header only if `ENABLE_TURNSTILE=true`.

#### Feedback
```bash
curl -s -X POST http://127.0.0.1:8080/feedback/submit \
  -H 'Content-Type: application/json' \
  -H "X-Session-ID: <session_id>" \
  -d '{"statistic_id":"<id>","feedback_type":"positive","doi":"10.1000/xyz123"}'
```
**Note**: Include `X-Session-ID` header only if `ENABLE_TURNSTILE=true`.

## How search works
- Query parsing: `SearchEngine.parse_query_to_structured_data()` (LLM provider selected via `LLM_PROVIDER`; prompt lives in `server/src/core/ai/prompts.py`).
- Query build: `SearchQueryBuilder.build_query()` composes SQL using pgvector (document + chunk similarity), full‑text (`to_tsquery`), and structured filters; scores fused via RRF.
- Execution: pooled connections in `server/src/db/connection.py`, enrichment via `DocumentRepository`.

## Testing
```bash
pytest
```

## Release automation
- Publishing a GitHub Release triggers the `Release server image` workflow.
- The workflow builds `server/docker/Dockerfile.prod` and pushes the image to GitHub Container Registry at `ghcr.io/PaN-Finder/pan-finder-server`.
- Each build embeds the release tag as `SERVER_VERSION`, exposed via the `/health` endpoint and container label.

## Public Docker image

The server image is available at `ghcr.io/pan-finder/pan-finder-server`.

```bash
docker pull ghcr.io/pan-finder/pan-finder-server:latest
```
