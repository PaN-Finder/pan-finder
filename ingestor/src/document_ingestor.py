"""
Ingest dataset records from JSON files under `data/` into a PostgreSQL database.
"""

import logging
from typing import Any

from base_document_ingestor import BaseDocumentIngestor


class DocumentIngestor(BaseDocumentIngestor):
    """Ingest standard document schemas into the `document` table."""

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

    def extract_document(
        self, record: dict[str, Any], dataset: dict[str, Any]
    ) -> dict[str, str]:
        doc = record[dataset["record_key"]]
        return {
            "doi": (doc.get("doi") or "").strip(),
            "title": doc["title"],
            "text": doc[dataset["text_field"]],
        }
