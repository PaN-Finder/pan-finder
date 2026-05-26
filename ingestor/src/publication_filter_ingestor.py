"""
Populate filters for publication-shaped documents.
"""

import logging
from copy import deepcopy
from typing import Any

from base_filter_ingestor import BaseFilterIngestor


class PublicationFilterIngestor(BaseFilterIngestor):
    """Extract filters from publication document raw metadata."""

    logger = logging.getLogger("PublicationFilterIngestor")

    def fetch_documents_without_filters(
        self, cursor
    ) -> list[tuple[int, dict[str, Any]]]:
        cursor.execute(
            """
            SELECT d.id, d.raw
            FROM document d
            LEFT JOIN filter f ON d.id = f.document_id
            WHERE f.document_id IS NULL
              AND d.raw ? %s
            """,
            (self.PUBLICATION_ROOT_KEY,),
        )
        return cursor.fetchall()

    def fetch_all_documents(self, cursor) -> list[tuple[int, dict[str, Any]]]:
        cursor.execute(
            """
            SELECT d.id, d.raw
            FROM document d
            WHERE d.raw ? %s
            """,
            (self.PUBLICATION_ROOT_KEY,),
        )
        return cursor.fetchall()

    @staticmethod
    def filter_entries_with_parameters(entries: Any) -> list[Any]:
        if not isinstance(entries, list):
            return []

        filtered_entries: list[Any] = []
        for entry in entries:
            if not isinstance(entry, dict):
                filtered_entries.append(entry)
                continue

            filtered_entry = deepcopy(entry)
            filtered_entry.pop("datafiles", None)
            parameters = filtered_entry.get("parameters")
            if isinstance(parameters, list):
                filtered_entry["parameters"] = [
                    parameter
                    for parameter in parameters
                    if not (
                        isinstance(parameter, dict)
                        and isinstance(parameter.get("name"), str)
                        and parameter["name"].startswith("__")
                    )
                ]
            filtered_entries.append(filtered_entry)

        return filtered_entries

    @staticmethod
    def filter_datacite_entries(raw: dict[str, Any]) -> list[Any]:
        datacite_entries = raw.get("datacite")
        if not isinstance(datacite_entries, list):
            return []

        filtered_entries: list[Any] = []
        for entry in datacite_entries:
            if not isinstance(entry, dict):
                filtered_entries.append(entry)
                continue

            filtered_entry = deepcopy(entry)
            attributes = filtered_entry.get("attributes")
            if isinstance(attributes, dict):
                attributes.pop("xml", None)
            filtered_entries.append(filtered_entry)

        return filtered_entries

    def normalize_raw(self, raw: dict[str, Any]) -> dict[str, Any]:
        normalized_raw = deepcopy(raw)
        normalized_raw.pop(self.PUBLICATION_ROOT_KEY, None)
        normalized_raw["samples"] = self.filter_entries_with_parameters(
            raw.get("samples")
        )
        normalized_raw["datasets"] = self.filter_entries_with_parameters(
            raw.get("datasets")
        )
        normalized_raw["datacite"] = self.filter_datacite_entries(raw)
        return normalized_raw

    def build_filters(
        self, doc_id: int, raw: dict[str, Any]
    ) -> tuple[list[tuple], list[str]]:
        normalized = self.normalize_raw(raw)
        filters = (
            self.flatten_json(normalized.get("panosc", {}))
            + self.flatten_json(normalized.get("samples", []), "samples")
            + self._flatten_datasets(normalized.get("datasets", []))
            + self.flatten_json(normalized.get("datacite", []))
            + self.flatten_json(normalized.get("users", []), "users")
            + self.flatten_json(normalized.get("reports", []), "reports")
            + self.flatten_json(normalized.get("citations", []), "citations")
            + self.flatten_json(normalized.get("instruments", []), "instruments")
            + self.flatten_json(normalized.get("investigation", {}), "investigation")
        )
        return self.build_filter_rows(doc_id, filters)
