"""Populate `filter.value_vector` for configured filter rows.

Two behaviors are supported:

- direct vectorization for normal text fields, where the original value is
    embedded and written to `value_vector` on the same row
- author-like splitting for configured name-list keys, where multi-name values
    are split into individual names and written as DERIVED rows with their own
    `value_vector`

Only keys marked as split-enabled in the configured value-vector key defaults use
the comma/semicolon name splitting heuristic. All other configured
`VALUE_VECTOR_KEYS` are embedded as-is.
"""

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer

BATCH_SIZE = 512


def _split_names(value: str) -> list[str] | None:
    """Return individual names for a multi-name value, or None for a single name.

    Returns None when the value represents a single person (plain name or
    "Last, First" format).  Returns a list when the value is a
    semicolon- or comma-separated sequence of full names.

    Semicolons unambiguously separate full names ("Last; First" is not a
    recognised convention), so a semicolon-containing value is always split
    on ";" without the extra heuristics applied to commas.
    """
    if ";" in value:
        parts = [p.strip() for p in value.split(";") if p.strip()]
        return parts if len(parts) > 1 else None

    parts = [p.strip() for p in value.split(",") if p.strip()]
    if len(parts) <= 1:
        return None
    # Single-person "Last, First" detection for exactly 2 comma-separated segments.
    # Treat as a single name when either:
    #   - the surname has no spaces: "Marone, Federica"
    #   - the given-name part has no spaces: "da Silva, MA" / "Cuevas Arenas, Rodrigo"
    # Only when BOTH parts contain spaces is it two full names: "Else Marie Friis, Federica Marone"
    if len(parts) == 2 and (" " not in parts[0] or " " not in parts[1]):
        return None
    return parts


class FilterVectorIngestor:
    """Compute and store embeddings in `filter.value_vector` for configured rows."""

    logger = logging.getLogger("FilterVectorIngestor")

    def __init__(
        self,
        db_conn_factory: Callable[[], AbstractContextManager[Any]],
        settings,
    ) -> None:
        self.db_conn_factory = db_conn_factory
        self.value_vector_keys = settings.value_vector_keys
        self.value_vector_split_keys = set(settings.value_vector_split_keys)
        model_path = Path(settings.embedding_model_path)
        if not model_path.exists():
            self.logger.warning("Embedding model path does not exist: %s", model_path)
        self.encoder = SentenceTransformer(str(model_path), device="cpu")

    def fetch_rows(self, cursor) -> list[tuple[int, int, str, str]]:
        """Return `(id, document_id, key, value)` for rows that still need processing.

        Multi-name rows are re-fetched on every run because their original
        `value_vector` intentionally stays NULL.  The idempotency guard for
        those rows lives in the INSERT NOT EXISTS check.
        """
        cursor.execute(
            """
            SELECT id, document_id, key, value
            FROM filter
            WHERE key = ANY(%s)
              AND value IS NOT NULL
              AND value != ''
              AND value_vector IS NULL
            """,
            (list(self.value_vector_keys),),
        )
        return cursor.fetchall()

    def _process_single_names(self, cursor, rows: list[tuple[int, str]]) -> None:
        """Embed single-name values and write the vector to the original row."""
        if not rows:
            return
        self.logger.info("Embedding %d single-name rows...", len(rows))
        ids = [r[0] for r in rows]
        values = [r[1] for r in rows]
        for start in range(0, len(rows), BATCH_SIZE):
            batch_ids = ids[start : start + BATCH_SIZE]
            batch_values = values[start : start + BATCH_SIZE]
            vectors = self.encoder.encode(batch_values)
            if hasattr(vectors, "tolist"):
                vectors = vectors.tolist()
            cursor.executemany(
                "UPDATE filter SET value_vector = %s WHERE id = %s",
                zip(vectors, batch_ids, strict=True),
            )
            self.logger.info(
                "Updated single-name rows %d-%d", start + 1, start + len(batch_ids)
            )

    def _process_multi_names(
        self, cursor, rows: list[tuple[int, str, list[str]]]
    ) -> None:
        """Insert DERIVED rows for each individual name in a multi-name value."""
        if not rows:
            return
        all_names = [name for _, _, names in rows for name in names]
        self.logger.info(
            "Embedding %d individual names from %d multi-name rows...",
            len(all_names),
            len(rows),
        )
        all_vectors = self.encoder.encode(all_names)
        if hasattr(all_vectors, "tolist"):
            all_vectors = all_vectors.tolist()

        vec_iter = iter(all_vectors)
        for doc_id, key, names in rows:
            for name in names:
                vec = next(vec_iter)
                cursor.execute(
                    """
                    INSERT INTO filter (document_id, key, value, type, value_vector)
                    SELECT %s, %s, %s, 'DERIVED'::filter_type, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM filter
                        WHERE document_id = %s
                          AND key = %s
                          AND value = %s
                          AND type = 'DERIVED'::filter_type
                    )
                    """,
                    (doc_id, key, name, vec, doc_id, key, name),
                )

    def process(self, rows: list[tuple[int, int, str, str]]) -> None:
        """Route each row to direct embedding or author-style splitting."""
        if not rows:
            self.logger.info("No filter rows to embed.")
            return

        single: list[tuple[int, str]] = []
        multi: list[tuple[int, str, list[str]]] = []

        for row_id, doc_id, key, value in rows:
            names = _split_names(value) if key in self.value_vector_split_keys else None
            if names is None:
                single.append((row_id, value))
            else:
                multi.append((doc_id, key, names))

        self.logger.info(
            "Processing %d single-name rows and %d multi-name rows.",
            len(single),
            len(multi),
        )

        with self.db_conn_factory() as conn:
            with conn.cursor() as cursor:
                self._process_single_names(cursor, single)
                self._process_multi_names(cursor, multi)
            conn.commit()

    def reset(self) -> None:
        """Undo all work done by this ingestor.

        - NULLs `value_vector` on original single-name rows.
        - Deletes DERIVED rows created for individual names from multi-name values.
        - Resets the filter_id_seq to MAX(id) so new rows get contiguous IDs.
        """
        self.logger.info("Resetting filter value vectors...")
        with self.db_conn_factory() as conn:
            with conn.cursor() as cursor:
                # Clear vectors on original (non-DERIVED) author rows
                cursor.execute(
                    """
                    UPDATE filter
                    SET value_vector = NULL
                    WHERE key = ANY(%s)
                      AND type != 'DERIVED'::filter_type
                      AND value_vector IS NOT NULL
                    """,
                    (list(self.value_vector_keys),),
                )
                self.logger.info("Cleared value_vector on %d rows.", cursor.rowcount)

                # Delete DERIVED rows created for split individual names
                cursor.execute(
                    """
                    DELETE FROM filter
                    WHERE key = ANY(%s)
                      AND type = 'DERIVED'::filter_type
                      AND value_vector IS NOT NULL
                    """,
                    (list(self.value_vector_keys),),
                )
                self.logger.info("Deleted %d derived rows.", cursor.rowcount)

                # Reset the sequence to the current max id
                cursor.execute(
                    "SELECT setval('public.filter_id_seq', (SELECT MAX(id) FROM public.filter))"
                )
            conn.commit()
        self.logger.info("Reset completed.")

    def run(self) -> None:
        # self.reset()
        self.logger.info("Starting filter vector ingestor...")
        try:
            with self.db_conn_factory() as conn, conn.cursor() as cursor:
                rows = self.fetch_rows(cursor)
            self.process(rows)
        except Exception:
            self.logger.exception("Error during filter vector ingestion", exc_info=True)
            raise
        self.logger.info("Filter vector ingestion completed.")
