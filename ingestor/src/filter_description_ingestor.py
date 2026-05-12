"""
Populate the `filter_description` table from a curated CSV of key/description pairs.

Steps performed by `run()`:
1. Load key→description mappings from `filter_description_data.csv` (located next to
   this file).
2. Match each CSV key against existing rows in `filter_key` using two strategies:
   - Exact match: filter_key.name == csv_key
   - Suffix match: the last dot-separated segment of filter_key.name == csv_key
3. Insert matched (filter_key_name, description) pairs into `filter_description`,
   skipping rows that already exist (idempotent).
4. Embed all `filter_description` rows whose `description_vector` is still NULL.
"""

import csv
import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer

_CSV_PATH = Path(__file__).parent / "filter_description_data.csv"
_BATCH_SIZE = 100


class FilterDescriptionIngestor:
    logger = logging.getLogger("FilterDescriptionIngestor")

    def __init__(
        self,
        db_conn_factory: Callable[[], AbstractContextManager[Any]],
        settings,
    ) -> None:
        self.db_conn_factory = db_conn_factory
        self.encoder = SentenceTransformer(settings.embedding_model_path, device="cpu")

    # ------------------------------------------------------------------
    # Step 1 – load CSV
    # ------------------------------------------------------------------

    def _load_csv(self) -> list[tuple[str, str]]:
        """Return [(key, description), …] from the bundled CSV file."""
        rows: list[tuple[str, str]] = []
        with _CSV_PATH.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                key = (row.get("key") or "").strip()
                description = (row.get("description") or "").strip()
                if key and description:
                    rows.append((key, description))
        self.logger.info("Loaded %d entries from CSV", len(rows))
        return rows

    # ------------------------------------------------------------------
    # Step 2 + 3 – match against filter_key and insert
    # ------------------------------------------------------------------

    def _insert_descriptions(self, cursor, csv_rows: list[tuple[str, str]]) -> int:
        """Match CSV keys to filter_key rows and insert into filter_description.

        Matching rules (applied in order, both may produce rows):
        - Exact:  filter_key.name = csv_key
        - Suffix: the segment after the last '.' in filter_key.name = csv_key

        Returns the number of rows inserted.
        """
        cursor.execute(
            """
            INSERT INTO filter_description (filter_key_name, description)
            SELECT DISTINCT fk.name, v.description
            FROM filter_key fk
            JOIN (SELECT unnest(%s::text[]) AS csv_key,
                         unnest(%s::text[]) AS description) AS v
              ON fk.name = v.csv_key
              OR (position('.' IN fk.name) > 0
                  AND substring(fk.name FROM '([^.]+)$') = v.csv_key)
            WHERE NOT EXISTS (
                SELECT 1
                FROM filter_description fd
                WHERE fd.filter_key_name = fk.name
                  AND fd.description = v.description
            )
            """,
            (
                [k for k, _ in csv_rows],
                [d for _, d in csv_rows],
            ),
        )
        return cursor.rowcount

    # ------------------------------------------------------------------
    # Step 4 – embed
    # ------------------------------------------------------------------

    def _fetch_unembedded(self, cursor) -> list[tuple[int, str]]:
        cursor.execute(
            """
            SELECT id, description
            FROM filter_description
            WHERE description_vector IS NULL
            """
        )
        return cursor.fetchall()

    def _embed_descriptions(self, cursor, rows: list[tuple[int, str]]) -> None:
        for start in range(0, len(rows), _BATCH_SIZE):
            batch = rows[start : start + _BATCH_SIZE]
            ids = [r[0] for r in batch]
            texts = [r[1] for r in batch]
            vectors = self.encoder.encode(texts)
            if hasattr(vectors, "tolist"):
                vectors = vectors.tolist()
            cursor.executemany(
                "UPDATE filter_description SET description_vector = %s WHERE id = %s",
                zip(vectors, ids, strict=True),
            )
            self.logger.info(
                "Embedded descriptions %d-%d", start + 1, start + len(batch)
            )

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        self.logger.info("Starting filter description ingestor...")
        try:
            csv_rows = self._load_csv()

            with self.db_conn_factory() as conn, conn.cursor() as cursor:
                inserted = self._insert_descriptions(cursor, csv_rows)
                self.logger.info("Inserted %d new filter_description rows", inserted)

                unembedded = self._fetch_unembedded(cursor)
                if unembedded:
                    self.logger.info(
                        "Embedding %d filter_description rows", len(unembedded)
                    )
                    self._embed_descriptions(cursor, unembedded)
                else:
                    self.logger.info("All filter_description rows already have vectors")

                conn.commit()

        except Exception:
            self.logger.exception("Error during filter description ingestion")
            raise

        self.logger.info("Filter description ingestion completed.")
