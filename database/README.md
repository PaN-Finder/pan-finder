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