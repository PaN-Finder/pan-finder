"""
Ingest publication records from JSON files under `data/` into the database.
"""

import json
import logging
from typing import Any

from base_document_ingestor import BaseDocumentIngestor


class PublicationDocumentIngestor(BaseDocumentIngestor):
    logger = logging.getLogger("PublicationDocumentIngestor")
    PUBLICATION_ROOT_KEY = "collection"

    DATASETS = [
        {
            "filename": "example_publications.json",
            "facility": "ESRF",
        },
    ]

    def parse_collection(self, record: dict[str, Any]) -> dict[str, Any] | None:
        collection = record.get(self.PUBLICATION_ROOT_KEY)
        if not collection:
            self.logger.warning("Skipping record without collection: %s", record)
            return None

        if isinstance(collection, str):
            try:
                collection_data = json.loads(collection)
            except json.JSONDecodeError:
                self.logger.warning(
                    "Skipping record with invalid collection JSON: %s", record
                )
                return None
        elif isinstance(collection, dict):
            collection_data = collection
        else:
            self.logger.warning(
                "Skipping record with unsupported collection type %s",
                type(collection).__name__,
            )
            return None

        return collection_data

    def extract_document(
        self, record: dict[str, Any], dataset: dict[str, Any]
    ) -> dict[str, str] | None:
        collection_data = self.parse_collection(record)
        if collection_data is None:
            return None

        parameter_values = {
            parameter.get("name"): parameter.get("value")
            for parameter in collection_data.get("parameters", [])
            if isinstance(parameter, dict) and parameter.get("name")
        }

        return {
            "doi": (collection_data.get("doi") or "").strip(),
            "title": (parameter_values.get("title") or "").strip(),
            "text": (parameter_values.get("abstract") or "").strip(),
        }
