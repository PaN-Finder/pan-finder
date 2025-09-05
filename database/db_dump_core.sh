#!/bin/bash
set -euo pipefail

# Create a timestamp (UTC, ISO-like compact form) and use it in the dump filename.
# Example: pan-finder-20250822T153045Z.dump
TS=$(date -u +%Y%m%dT%H%M%SZ)
OUT="pan-finder-${TS}.dump"
FUNCS_OUT="pan-finder-functions-${TS}.sql"

echo "Creating dump: $OUT"
pg_dump -h localhost -U usr -d pan-finder \
  -Fc -t public.chunk -t public.document -t public.facility -t public.filter -t public.filter_key \
  -f "$OUT"

echo "Dump created successfully: $OUT"

# Also dump helper functions into a plain SQL file so they can be restored easily
echo "Exporting helper functions to: $FUNCS_OUT"
psql -h localhost -U usr -d pan-finder -At -c "
  SELECT string_agg(pg_get_functiondef(p.oid), E'\n\n')
  FROM pg_proc p
  JOIN pg_namespace n ON n.oid = p.pronamespace
  WHERE n.nspname = 'public'
    AND p.proname = ANY(ARRAY[
      'rrf_score',
      'update_document_tsvector',
      'to_unit'
    ]);
" > "$FUNCS_OUT"

echo "Helper functions exported successfully: $FUNCS_OUT"
echo "To restore the dump, use the following command:"
echo "psql -h localhost -U usr -d pan-finder -f $FUNCS_OUT"
echo "pg_restore -h localhost -U usr -d pan-finder --clean --if-exists --no-owner --no-privileges $OUT"
