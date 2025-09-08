"""
Ingest dataset records from JSON files under `data/` into a PostgreSQL database.

Behavior overview:
- For each configured dataset (ILL: `ill.json`, `ill_manual.json`; ESS: `ess.json`; PSI: `psi.json`; MAXIV: `maxiv.json`; ESRF: `esrf.json`):
    - Ensure the facility exists in table `facility` (insert-on-conflict by `name`).
    - Iterate records and, when a non-empty DOI is present, insert a row into `document`
        with columns `(doi, title, text, raw, facility_id)`:
            - `text` comes from `summary` for `panosc` records and from `abstract` for `document` records.
            - The full original record is stored in `raw` as JSON.
    - Duplicates are ignored at the database level via `ON CONFLICT(doi) DO NOTHING`.
    - Records without a DOI are skipped and logged as warnings.
- Missing dataset files are logged as warnings; a commit occurs after each file is processed.

Entry point: `store_data(db_conn)` expects a DB-API connection supporting context management.
"""

import logging
import json
from pathlib import Path

logging.getLogger("store")


def get_or_create_facility(cursor, name):
    cursor.execute(
        "INSERT INTO facility(name) VALUES (%s) ON CONFLICT(name) DO NOTHING;",
        (name,),
    )
    cursor.execute("SELECT id FROM facility WHERE name = %s;", (name,))
    return cursor.fetchone()[0]


def insert_document(cursor, doc, raw_record, facility_id, text_field):
    cursor.execute(
        """
        INSERT INTO document (doi, title, text, raw, facility_id)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT(doi) DO NOTHING        
        """,
        (
            doc["doi"],
            doc["title"],
            doc[text_field],
            json.dumps(raw_record),
            facility_id,
        ),
    )


def store_data(db_conn):
    """Store data from JSON files into the database."""
    try:
        datasets = [
            {
                "filename": "ill_manual.json",
                "facility": "ILL",
                "record_key": "panosc",
                "text_field": "summary",
            },
            {
                "filename": "ill.json",
                "facility": "ILL",
                "record_key": "panosc",
                "text_field": "summary",
            },
            {
                "filename": "ess.json",
                "facility": "ESS",
                "record_key": "document",
                "text_field": "abstract",
            },
            {
                "filename": "psi.json",
                "facility": "PSI",
                "record_key": "document",
                "text_field": "abstract",
            },
            {
                "filename": "maxiv.json",
                "facility": "MAXIV",
                "record_key": "document",
                "text_field": "abstract",
            },
            {
                "filename": "esrf.json",
                "facility": "ESRF",
                "record_key": "panosc",
                "text_field": "summary",
            },
        ]

        with db_conn as conn:
            with conn.cursor() as cursor:
                for ds in datasets:
                    file_path = Path("data") / ds["filename"]
                    if not file_path.exists():
                        logging.warning(f"Data file not found: {file_path}")
                        continue

                    with file_path.open() as f:
                        data = json.load(f)

                    facility_id = get_or_create_facility(cursor, ds["facility"])
                    for record in data:
                        doc = record[ds["record_key"]]
                        if doc.get("doi") is None or not doc.get("doi").strip():
                            logging.warning(f"Skipping record without DOI: {record}")
                            continue

                        insert_document(
                            cursor, doc, record, facility_id, ds["text_field"]
                        )

                    conn.commit()
                    logging.info(f"Processed {len(data)} records from {ds['filename']}")
    except Exception as e:
        logging.error("Error during store", exc_info=True)
        raise
