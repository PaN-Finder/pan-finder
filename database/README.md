# Pan-Finder Database

## Create an empty schema

```bash
# docker
cat schema.sql | docker exec -i pan-finder-postgres psql -U youruser -d pan-finder

# local
psql -U youruser -d pan-finder < schema.sql
```

## Save the schema to a file

```bash
pg_dump --schema-only --no-owner --no-privileges -U usr -h localhost -p 5432 pan-finder > schema.sql
```

## Public Docker image

The PostgreSQL image with `pgvector` and `postgresql-unit` is available at `ghcr.io/pan-finder/pan-finder-postgresql`.

```bash
docker pull ghcr.io/pan-finder/pan-finder-postgresql:latest
```