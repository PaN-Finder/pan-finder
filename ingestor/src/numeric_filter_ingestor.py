"""
Normalise and enrich filter entries in the database.

This module derives structured numeric/value-unit filters from free-text values
stored in the `filter` table and embeds derived keys for semantic search.

What it does:
- normalise_value_unit():
    - Parses single value+unit strings like "10 um", "20 K", "5.5 mm", etc.
    - Inserts derived rows into `filter` with columns (document_id, key, value, unit)
        and type = 'DERIVED'. Supported units include: um, K, mm, m, °C, A, keV, meV,
        mA, g, k, mg.
- normalise_min_max():
    - Parses min-max ranges like "10-20K" or "5-15mm".
    - Inserts two derived rows per match: `<key>.min` and `<key>.max` with the
        corresponding numeric values and unit; type = 'DERIVED'.
    - Creates embeddings for the new keys and upserts them into the `filter_key`
        table as (name, name_vector).
"""

import logging
from typing import Callable, ContextManager, Any, List, Tuple

from sentence_transformers import SentenceTransformer


class NumericFilterIngestor:
    """Class wrapper for deriving numeric filters and embeddings."""

    logger = logging.getLogger("NumericFilterIngestor")

    def __init__(
        self,
        db_conn_factory: Callable[[], ContextManager[Any]],
        settings,
    ) -> None:
        self.db_conn_factory = db_conn_factory
        self.settings = settings
        self.encoder = SentenceTransformer(settings.embedding_model_path, device="cpu")

    def normalise_value_unit(self) -> None:
        """
        Normalise filter values with units like '10 um', '20 K', etc.
        """
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO filter (document_id, key, value, unit, type)
                            SELECT document_id, key, value_unit[1], value_unit[2], 'DERIVED'::filter_type
                            FROM (
                                SELECT document_id, key,
                                regexp_match(value, '^(-?\\d*\\.{0,1}\\d+)\\s?(um|K|mm|m|°C|A|keV|meV|mA|g|k|mg)$') as value_unit
                                FROM filter
                                WHERE
                                    not regexp_like(key, 'sampleParameters\\.Formula|sample_name|Load|sample\\.samplePreparation|sampleName|datasetName|description|keywords|^name$|abstract|proposalid|experimentalSettings\\.filters|summary|title|comments', 'i')
                                    AND
                                    regexp_like(value, '^(-?\\d*\\.{0,1}\\d+)\\s?(um|K|mm|m|°C|A|keV|meV|mA|g|k|mg)$')
                            ) AS subquery
                        """
                    )
                conn.commit()
            self.logger.info("Filter normalisation completed successfully")
        except Exception:
            self.logger.exception("Error during filter normalisation", exc_info=True)
            raise

    def normalise_min_max(self) -> None:
        """
        Normalise filter values with min-max ranges like '10-20 K', '5-15 mm', etc.
        """
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    # Insert the minimum values
                    cursor.execute(
                        """
                        INSERT INTO filter (document_id, key, value, unit, type)                    
                            SELECT 
                                document_id, CONCAT(key, '.min'), value_unit[1], value_unit[3], 'DERIVED'::filter_type
                            FROM (
                                SELECT document_id, key,
                                regexp_match(value, '^(-?\\d*\\.?\\d+)-(-?\\d*\\.?\\d+)([a-zA-Z]+)$') as value_unit
                                FROM filter
                                WHERE
                                    not regexp_like(key, 'sampleName', 'i')
                                    AND
                                    regexp_like(value, '^(-?\\d*\\.?\\d+)-(-?\\d*\\.?\\d+)([a-zA-Z]+)$')
                            ) AS subquery
                        """
                    )

                    # Insert the maximum values
                    cursor.execute(
                        """
                        INSERT INTO filter (document_id, key, value, unit, type)                    
                            SELECT 
                                document_id, CONCAT(key, '.max'), value_unit[2], value_unit[3], 'DERIVED'::filter_type
                            FROM (
                                SELECT document_id, key,
                                regexp_match(value, '^(-?\\d*\\.?\\d+)-(-?\\d*\\.?\\d+)([a-zA-Z]+)$') as value_unit
                                FROM filter
                                WHERE
                                    not regexp_like(key, 'sampleName', 'i')
                                    AND
                                    regexp_like(value, '^(-?\\d*\\.?\\d+)-(-?\\d*\\.?\\d+)([a-zA-Z]+)$')
                            ) AS subquery
                        """
                    )
                    conn.commit()

                    cursor.execute(
                        """
                            SELECT CONCAT(key, '.min') as min, CONCAT(key, '.max') as max
                            FROM filter
                            WHERE 
                                not regexp_like(key, 'sampleName', 'i')
                                AND
                                regexp_like(value, '^(-?\\d*\\.?\\d+)-(-?\\d*\\.?\\d+)([a-zA-Z]+)$')
                            GROUP BY key
                        """
                    )
                    min_max_keys: List[Tuple[str, str]] = cursor.fetchall()

                    keys_flat: List[str] = [k for pair in min_max_keys for k in pair]
                    if keys_flat:
                        # Replace dot with space for embedding, as before
                        texts = [k.replace(".", " ") for k in keys_flat]
                        vectors = self.encoder.encode(texts)
                        if hasattr(vectors, "tolist"):
                            vectors = vectors.tolist()
                        key_embeddings = list(zip(keys_flat, vectors))
                        cursor.executemany(
                            """
                            INSERT INTO filter_key (name, name_vector)
                            VALUES (%s, %s)
                            ON CONFLICT (name) DO NOTHING
                            """,
                            key_embeddings,
                        )
                    conn.commit()

            self.logger.info("Filter min-max normalisation completed successfully")
        except Exception:
            self.logger.exception(
                "Error during filter min-max normalisation", exc_info=True
            )
            raise

    def run(self) -> None:
        self.logger.info("Starting filter normalisation")
        self.normalise_value_unit()
        self.normalise_min_max()
        self.logger.info("Filter normalisation completed")
