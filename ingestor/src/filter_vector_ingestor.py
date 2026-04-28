"""
Populate `filter.value_vector` for author-related filter rows.

Fetches filter rows where the key is one of the author-related keys and
`value_vector IS NULL`, encodes the `value` field using a SentenceTransformer,
and stores the resulting embedding back into `value_vector`.
"""

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer

AUTHOR_KEYS = (
    "authors",
    "creator",
    "scientificMetadata.author",
    "owner",
    "metadata.authors.name",
    "principalInvestigator",
    "investigator",
)

BATCH_SIZE = 512


class FilterVectorIngestor:
    """Compute and store embeddings in `filter.value_vector` for author-related rows."""

    logger = logging.getLogger("FilterVectorIngestor")

    def __init__(
        self,
        db_conn_factory: Callable[[], AbstractContextManager[Any]],
        settings,
    ) -> None:
        self.db_conn_factory = db_conn_factory
        model_path = Path(settings.embedding_model_path)
        if not model_path.exists():
            self.logger.warning("Embedding model path does not exist: %s", model_path)
        self.encoder = SentenceTransformer(str(model_path), device="cpu")

    def fetch_rows(self, cursor) -> list[tuple[int, str]]:
        """Return `(id, value)` for target rows that still need an embedding."""
        cursor.execute(
            """
            SELECT id, value
            FROM filter
            WHERE key = ANY(%s)
              AND value IS NOT NULL
              AND value != ''
              AND value_vector IS NULL
            """,
            (list(AUTHOR_KEYS),),
        )
        return cursor.fetchall()

    def process(self, rows: list[tuple[int, str]]) -> None:
        """Encode values in batches and update `value_vector`."""
        if not rows:
            self.logger.info("No filter rows to embed.")
            return

        ids = [r[0] for r in rows]
        values = [r[1] for r in rows]

        self.logger.info("Embedding %d filter rows...", len(rows))

        with self.db_conn_factory() as conn:
            with conn.cursor() as cursor:
                for start in range(0, len(rows), BATCH_SIZE):
                    batch_ids = ids[start : start + BATCH_SIZE]
                    batch_values = values[start : start + BATCH_SIZE]

                    vectors = self.encoder.encode(batch_values)
                    if hasattr(vectors, "tolist"):
                        vectors = vectors.tolist()

                    cursor.executemany(
                        """
                        UPDATE filter
                        SET value_vector = %s
                        WHERE id = %s
                        """,
                        [
                            (vec, row_id)
                            for vec, row_id in zip(vectors, batch_ids, strict=True)
                        ],
                    )
                    self.logger.info(
                        "Updated rows %d–%d", start + 1, start + len(batch_ids)
                    )
            conn.commit()

    def run(self) -> None:
        self.logger.info("Starting filter vector ingestor...")
        try:
            with self.db_conn_factory() as conn, conn.cursor() as cursor:
                rows = self.fetch_rows(cursor)
            self.process(rows)
        except Exception:
            self.logger.exception("Error during filter vector ingestion", exc_info=True)
            raise
        self.logger.info("Filter vector ingestion completed.")
