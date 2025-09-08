"""
Enrich the `filter` table with publisher-related derived data.

This module provides the class `FilterEnricher`, which:
- Adds a derived `publisher` filter for each document based on its facility
    when no such entry exists (type = 'DERIVED').
- Harmonizes publisher names using a fixed mapping (e.g., ESRF <-> European
    Synchrotron Radiation Facility), inserting normalized variants only if they
    are not already present per document.
"""

import logging
from typing import Callable, ContextManager, Any


class FilterEnricher:
    """Adds and harmonizes publisher-related filter entries."""

    logger = logging.getLogger("FilterEnricher")

    def __init__(
        self,
        db_conn_factory: Callable[[], ContextManager[Any]],
    ) -> None:
        self.db_conn_factory = db_conn_factory

    def add_publisher(self) -> None:
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO filter (document_id, key, value, type)
                        SELECT doc.id, 'publisher', facility.name, 'DERIVED'
                        FROM document doc
                        JOIN facility on facility.id = doc.facility_id
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM filter f
                            WHERE f.document_id = doc.id
                            AND f.key = 'publisher'
                            AND f.type = 'DERIVED'
                        )
                        """
                    )
                conn.commit()
        except Exception:
            self.logger.exception("Error adding publisher filters", exc_info=True)
            raise

    def enrich_publisher(self) -> None:
        mapping = {
            "ESRF": "European Synchrotron Radiation Facility",
            "European Synchrotron Radiation Facility": "ESRF",
            "PSI": "Paul Scherrer Institute",
            "PSI LMU": "Paul Scherrer Institute",
            "ILL": "Institut Laue-Langevin",
            "ESS": "European Spallation Source",
            "MAX IV Laboratory, Lund University": "MAX IV",
            "MAXIV": "MAX IV Laboratory",
            "MAX IV": "MAX IV Laboratory",
        }

        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    # loop through the mapping and update the filter table
                    for key, value in mapping.items():
                        cursor.execute(
                            """
                            INSERT INTO filter (document_id, key, value, type)
                                SELECT f.document_id, 'publisher', %s, 'DERIVED'
                                FROM filter f
                                WHERE f.key = 'publisher' and f.value = %s
                                AND NOT EXISTS (
                                    SELECT 1
                                    FROM filter f2
                                    WHERE f2.document_id = f.document_id
                                    AND f2.key = 'publisher'
                                    AND f2.value = %s
                                )
                            """,
                            (value, key, value),
                        )
                    conn.commit()
        except Exception:
            self.logger.exception("Error enriching publisher filters", exc_info=True)
            raise

    def run(self) -> None:
        self.logger.info("Starting enrich filter process...")
        self.add_publisher()
        self.enrich_publisher()
        self.logger.info("Enrich filter process completed.")
