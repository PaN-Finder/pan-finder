"""
Populate the `filter` and `filter_key` tables from document raw metadata.
"""

import logging
from typing import Any

from base_filter_ingestor import BaseFilterIngestor


class FilterIngestor(BaseFilterIngestor):
    """Extract metadata filters from `document.raw` and persist them."""

    logger = logging.getLogger("FilterIngestor")

    # --- DB operations ---
    def fetch_documents_without_filters(
        self, cursor
    ) -> list[tuple[int, dict[str, Any]]]:
        cursor.execute(
            """
            SELECT d.id, d.raw
            FROM document d
            LEFT JOIN filter f ON d.id = f.document_id
            WHERE f.document_id IS NULL
              AND NOT (d.raw ? %s)
            """,
            (self.PUBLICATION_ROOT_KEY,),
        )
        return cursor.fetchall()

    def build_filters(
        self, doc_id: int, raw: dict[str, Any]
    ) -> tuple[list[tuple], list[str]]:
        filters = (
            self.flatten_json(raw.get("document", {}))
            + self.flatten_json(raw.get("panosc", {}))
            + self.flatten_json(raw.get("datasets", {}))
            + self.flatten_json(raw.get("datacite", {}))
            + self.flatten_json(raw.get("catalogue", {}))
        )
        return self.build_filter_rows(doc_id, filters)
