# Pan-Finder Database

## Create a new database

```bash
docker run --name pan-finder-postgres -e POSTGRES_PASSWORD=yourpassword -e POSTGRES_USER=youruser -e POSTGRES_DB=panfinder -p 5432:5432 -d registry.esss.lu.se/swap/pan-finder:postgresql
```

## Create an empty schema

```bash
cat schema.sql | docker exec -i pan-finder-postgres psql -U youruser -d panfinder
```

## Save the schema to a file

```bash
pg_dump --schema-only --no-owner --no-privileges -U usr -h localhost -p 5432 pan-finder > schema.sql
```