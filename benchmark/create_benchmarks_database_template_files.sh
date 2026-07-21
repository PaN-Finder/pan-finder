#!/bin/bash

# Configuration
CONTAINER_NAME="8ea3e62856c7"  # Replace with your container name
POSTGRES_USER="usr"
POSTGRES_DB="pan-finder-benchmarks"
HOST_OUTPUT_DIR="./database/template"  # Host directory to save the files

# Create host output directory if it doesn't exist
mkdir -p "$HOST_OUTPUT_DIR"

# Execute pg_dump commands inside the container
docker exec "$CONTAINER_NAME" sh -c "
  pg_dump -U $POSTGRES_USER -h localhost -d $POSTGRES_DB --schema-only -f /tmp/pan-finder-benchmarks-schema.sql &&
  pg_dump -U $POSTGRES_USER -h localhost -d $POSTGRES_DB --data-only --table=test_pairs -f /tmp/pan-finder-benchmarks-test-pairs.sql
"

# Copy the files from the container to the host
docker cp "$CONTAINER_NAME:/tmp/pan-finder-benchmarks-schema.sql" "$HOST_OUTPUT_DIR/"
docker cp "$CONTAINER_NAME:/tmp/pan-finder-benchmarks-test-pairs.sql" "$HOST_OUTPUT_DIR/"

# Remove the files from the container
docker exec "$CONTAINER_NAME" sh -c "
  rm -f /tmp/pan-finder-benchmarks-schema.sql /tmp/pan-finder-benchmarks-test-pairs.sql
"

echo "Export completed. Files saved to: $HOST_OUTPUT_DIR"
