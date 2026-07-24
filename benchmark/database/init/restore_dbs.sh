#!/bin/bash
set -e

# Wait for PostgreSQL to start
until pg_isready -U usr; do
  sleep 1
done

# Create the databases
createdb -U usr pan-finder
createdb -U usr pan-finder-benchmarks

# Restore the dumps
pg_restore -U usr -d pan-finder /backups/pan-finder-database-production.dump
psql -U usr -d pan-finder -f /backups/pan-finder-functions-production.sql

psql -U usr -d pan-finder-benchmarks -f /backups/pan-finder-benchmarks-schema.sql
psql -U usr -d pan-finder-benchmarks -f /backups/pan-finder-benchmarks-test-pairs.sql

# create empty dataset to signal that is ready
createdb -U usr pan-finder-test

