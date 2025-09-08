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

## Configuration
Loaded by `server/src/config.py` (`get_settings()`). Required:
- `DATABASE_URL`
- `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`
- `TURNSTILE_SECRET_KEY`

Common options:
- `EMBEDDING_MODEL_PATH` (default `/code/models/all-MiniLM-L12-v2`)
- `ALLOWED_ORIGINS` (default `*`), `API_HOST` (default `0.0.0.0`), `API_PORT` (default `8080`)
- `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_MODEL_NAME`, `AZURE_OPENAI_EXPLANATION_MODEL_NAME`
- DB pool: `DB_POOL_MIN_SIZE`, `DB_POOL_MAX_SIZE`, `DB_CONNECTION_TIMEOUT`, `DB_MAX_IDLE`, `DB_MAX_LIFETIME`
- RRF: `RRF_K_SIMILARITY`, `RRF_K_CHUNK`, `RRF_K_FULL_MATCH`, `RRF_K_PARTIAL_MATCH`, `RRF_K_KEYWORD`

## Endpoints
Most endpoints require a session header `X-Session-ID`. Create a session using a Cloudflare Turnstile token first.

Create session
```bash
curl -s -X POST http://127.0.0.1:8080/session/create \
  -H 'Content-Type: application/json' \
  -d '{"turnstile_token":"<TURNSTILE_TOKEN>"}'
```
Response contains `session_id` (use in subsequent calls).

Search (SSE)
```bash
curl -N -X POST http://127.0.0.1:8080/search \
  -H 'Content-Type: application/json' \
  -H "X-Session-ID: <session_id>" \
  -d '{"query":"Find datasets on graphene where temperature is between 99 and 101 K"}'
```
Streamed events: `analysis_started`, `analysis_completed`, `data_fetching`, `results`, optional `explanation_*`, `search_completed`.

Search with structured data (bypass LLM)
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

Document details
```bash
curl -s http://127.0.0.1:8080/document/<url-encoded-doi> \
  -H "X-Session-ID: <session_id>"
```

Feedback
```bash
curl -s -X POST http://127.0.0.1:8080/feedback/submit \
  -H 'Content-Type: application/json' \
  -H "X-Session-ID: <session_id>" \
  -d '{"statistic_id":"<id>","feedback_type":"positive","doi":"10.1000/xyz123"}'
```

## How search works
- Query parsing: `SearchEngine.parse_query_to_structured_data()` (Azure OpenAI; prompt lives in `server/src/core/ai/prompts.py`).
- Query build: `SearchQueryBuilder.build_query()` composes SQL using pgvector (document + chunk similarity), full‑text (`to_tsquery`), and structured filters; scores fused via RRF.
- Execution: pooled connections in `server/src/db/connection.py`, enrichment via `DocumentRepository`.

## Testing
```bash
pytest
```