#!/bin/bash

# Wait for PostgreSQL to start
until pg_isready -U usr; do
  sleep 1
done

# Create the databases
createdb -U usr pan-finder
createdb -U usr pan-finder-benchmarks

# Restore the dumps
pg_restore -U usr -d pan-finder /backups/pan-finder-database-production.dump
pg_restore -U usr -d pan-finder-benchmarks /backups/pan-finder-benchmarks-init.dump

