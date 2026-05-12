"""
Ingest publication records from JSON files under `data/` into the database.
"""

import logging
from typing import Any

from base_document_ingestor import BaseDocumentIngestor


class PublicationDocumentIngestor(BaseDocumentIngestor):
    logger = logging.getLogger("PublicationDocumentIngestor")

    DATASETS = [
        {
            "filename": "oscars_pan_finder_publications_20260427115632932727050.skip",
            "facility": "ESRF",
        },
    ]

    def extract_document(
        self, record: dict[str, Any], dataset: dict[str, Any]
    ) -> dict[str, str] | None:
        datacite = record.get("datacite")
        if not datacite or not isinstance(datacite[0], dict):
            self.logger.warning("Skipping record without datacite entry: %s", record)
            return None

        attributes = datacite[0].get("attributes", {})

        titles = attributes.get("titles") or []
        title = (titles[0].get("title") if titles else None) or ""

        descriptions = attributes.get("descriptions") or []
        abstract = next(
            (
                d.get("description", "")
                for d in descriptions
                if isinstance(d, dict) and d.get("descriptionType") == "Abstract"
            ),
            "",
        )

        return {
            "doi": (attributes.get("doi") or "").strip().upper(),
            "title": title.strip(),
            "text": abstract.strip(),
        }
