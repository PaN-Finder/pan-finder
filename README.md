# Pan-Finder API

## Development

1. Download the all-MiniLM-L12-v2 embedding model from [Hugging Face](https://huggingface.co/sentence-transformers/all-MiniLM-L12-v2) and place it in the `models` directory.
2. Create a `.env` file in the root directory from the `.env.example` file.
3. Start the development server using Docker Compose:

```bash
docker compose -f docker-compose.dev.yml up
```

## Unit Tests

Run the unit tests using the following command:

```bash
pytest
```

## Database

The `database` directory contains the current schema for the PostgreSQL database, including the `pgvector` and `postgresql-unit` extensions.

# Ingestor Service

The ingestor service needs to be implementd. However the `ingestor` directory contains a basic implementation that can be used to ingest documents, create chunks, populate filters, and derive numeric filters.

# Benchmarking

The `benchmark` directory contains scripts to benchmark the performance of the Pan-Finder Query Builder.

## Using Frontend (Optional)

(Repository: https://github.com/panosc-eu/searchui)<br>
Clone the frontend repository somewhere and run it.<br>
It automatically connects to the PanFinder API server running on [127.0.0.1:8080](http://127.0.0.1:8080).

## Temporary docker commands (local development)

Build:
```bash
docker build -f server/docker/Dockerfile.k8s . -t registry.esss.lu.se/swap/pan-finder:server --platform linux/amd64
```
Push:
```bash
docker push registry.esss.lu.se/swap/pan-finder:server
```

Frontend:
```bash
cd searchui
docker build --build-arg API=https://federated.panosc.ess.eu/api --build-arg PAN_FINDER_API=https://pan-finder-api.dev-sims.ess.eu --build-arg TURNSTILE_SITE_KEY=*** -f Dockerfile . -t registry.esss.lu.se/swap/pan-finder:frontend --platform linux/amd64
```

Push Frontend:
```bash
docker push registry.esss.lu.se/swap/pan-finder:frontend
```

## Custom Postgresql image with pgvector and postresql-unit extension

Dockerfile: `database/Dockerfile.postgresql`

Build:
```bash
docker build -f database/Dockerfile.postgresql . -t registry.esss.lu.se/swap/pan-finder:postgresql --platform linux/amd64
```

Push:
```bash
docker push registry.esss.lu.se/swap/pan-finder:postgresql
```