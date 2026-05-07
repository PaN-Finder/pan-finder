"""
Shared workflow for document ingestors.
"""

import json
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any


class BaseDocumentIngestor:
    """Base workflow for ingesting document records into the database."""

    logger = logging.getLogger("BaseDocumentIngestor")
    DATASETS: list[dict[str, Any]] = []

    def __init__(
        self,
        db_conn_factory: Callable[[], AbstractContextManager[Any]],
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

    def extract_document(
        self, record: dict[str, Any], dataset: dict[str, Any]
    ) -> dict[str, str] | None:
        raise NotImplementedError

    def insert_document(
        self, cursor, doc: dict[str, str], raw_record: dict[str, Any], facility_id: int
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
                doc["text"],
                json.dumps(raw_record),
                facility_id,
            ),
        )

    def run(self) -> None:
        """Store data from JSON files into the database."""
        try:
            with self.db_conn_factory() as conn, conn.cursor() as cursor:
                for dataset in self.DATASETS:
                    file_path = Path("data") / dataset["filename"]
                    if not file_path.exists():
                        raise FileNotFoundError(f"Data file not found: {file_path}")

                    with file_path.open() as handle:
                        data = json.load(handle)

                    facility_id = self.get_or_create_facility(
                        cursor, dataset["facility"]
                    )
                    for record in data:
                        doc = self.extract_document(record, dataset)
                        if doc is None:
                            continue

                        doi = (doc.get("doi") or "").strip()
                        if not doi:
                            self.logger.warning(
                                "Skipping record without DOI: %s", record
                            )
                            continue

                        self.insert_document(cursor, doc, record, facility_id)

                    conn.commit()
                    self.logger.info(
                        "Processed %d records from %s",
                        len(data),
                        dataset["filename"],
                    )
        except Exception:
            self.logger.error("Error during store", exc_info=True)
            raise
