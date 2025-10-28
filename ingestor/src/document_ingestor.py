"""
Ingest dataset records from JSON files under `data/` into a PostgreSQL database.
"""

import logging
import json
from pathlib import Path
from typing import Callable, ContextManager, Any


class DocumentIngestor:
    """Encapsulates dataset ingestion into the `document` table."""

    logger = logging.getLogger("DocumentIngestor")

    DATASETS = [
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
        {
            "filename": "desy.json",
            "facility": "DESY",
            "record_key": "document",
            "text_field": "abstract",
        },
    ]

    def __init__(
        self,
        db_conn_factory: Callable[[], ContextManager[Any]],
        settings=None,
    ) -> None:
        self.db_conn_factory = db_conn_factory
        self.settings = settings  # reserved for future use

    def get_or_create_facility(self, cursor, name: str) -> int:
        cursor.execute(
            "INSERT INTO facility(name) VALUES (%s) ON CONFLICT(name) DO NOTHING;",
            (name,),
        )
        cursor.execute("SELECT id FROM facility WHERE name = %s;", (name,))
        return cursor.fetchone()[0]

    def insert_document(
        self, cursor, doc: dict, raw_record: dict, facility_id: int, text_field: str
    ) -> None:
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

    def run(self) -> None:
        """Store data from JSON files into the database."""
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    for ds in self.DATASETS:
                        file_path = Path("data") / ds["filename"]
                        if not file_path.exists():
                            raise FileNotFoundError(f"Data file not found: {file_path}")

                        with file_path.open() as f:
                            data = json.load(f)

                        facility_id = self.get_or_create_facility(
                            cursor, ds["facility"]
                        )
                        for record in data:
                            doc = record[ds["record_key"]]
                            doi = (doc.get("doi") or "").strip()
                            if not doi:
                                self.logger.warning(
                                    "Skipping record without DOI: %s", record
                                )
                                continue

                            self.insert_document(
                                cursor, doc, record, facility_id, ds["text_field"]
                            )

                        conn.commit()
                        self.logger.info(
                            "Processed %d records from %s", len(data), ds["filename"]
                        )
        except Exception:
            self.logger.error("Error during store", exc_info=True)
            raise
