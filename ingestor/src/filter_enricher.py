"""
Enrich the `filter` table with derived metadata filters.

This module provides the class `FilterEnricher`, which:
- Adds a derived `publisher` filter for each document based on its facility
    when no such entry exists (type = 'DERIVED').
- Harmonizes publisher names using a fixed mapping (e.g., ESRF <-> European
    Synchrotron Radiation Facility), inserting normalized variants only if they
    are not already present per document.
- Derives `beamline` filters from facility-specific instrument metadata fields
    (e.g., instrument.name, instrumentName, instrumentGroup) for ESRF, PSI, and MAX IV.
"""

import logging
from typing import Callable, ContextManager, Any

from filter_ingestor import FilterIngestor


class FilterEnricher:
    logger = logging.getLogger("FilterEnricher")

    def __init__(
        self,
        db_conn_factory: Callable[[], ContextManager[Any]],
        settings,
    ) -> None:
        self.db_conn_factory = db_conn_factory
        self.settings = settings
        self.filter_ingestor = FilterIngestor(db_conn_factory, settings)

    def add_publisher(self) -> None:
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO filter (document_id, key, value, type)
                        SELECT doc.id, 'publisher', facility.name, 'DERIVED'::filter_type
                        FROM document doc
                        JOIN facility on facility.id = doc.facility_id
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM filter f
                            WHERE f.document_id = doc.id
                            AND f.key = 'publisher'
                            AND f.type = 'DERIVED'::filter_type
                        )
                        """
                    )
                conn.commit()
        except Exception:
            self.logger.exception("Error adding publisher filters", exc_info=True)
            raise

    def enrich_instrument_to_beamline(self) -> None:
        """
        Derive 'beamline' filter entries from instrument-related metadata.

        This method maps various facility-specific instrument fields to a normalized
        'beamline' filter key. The mapping is facility-dependent:

        - ESRF (facility_id=5): instrument.name, instrumentName → beamline
        - MAX IV (facility_id=4): instrumentGroup → beamline
        - PSI (facility_id=3): scientificMetadata.measurement.beamline → beamline

        Only creates new entries if:
        - Source value is non-NULL and non-empty
        - No identical DERIVED beamline filter exists for that document
        - Document belongs to one of the target facilities (3, 4, 5)

        The DERIVED type distinguishes these from user-provided or raw metadata values.
        """
        try:
            with self.db_conn_factory() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO filter (document_id, key, value, type)
                        SELECT DISTINCT f.document_id, 'beamline', f.value, 'DERIVED'::filter_type
                        FROM filter f
                        INNER JOIN document d ON d.id = f.document_id
                        WHERE f.key IN ('instrument.name', 'instrumentName', 'instrumentGroup', 'scientificMetadata.measurement.beamline')
                          AND f.value IS NOT NULL
                          AND f.value != ''
                          AND d.facility_id IN (3, 4, 5)
                          AND NOT EXISTS (
                            SELECT 1
                            FROM filter f2
                            WHERE f2.document_id = f.document_id
                              AND f2.key = 'beamline'
                              AND f2.value = f.value
                              AND f2.type = 'DERIVED'::filter_type
                          )
                        """
                    )

                    # Ensure 'beamline' key exists in filter_key table with embedding
                    self.filter_ingestor.insert_filter_keys_with_embeddings(
                        cursor, ["beamline"]
                    )

                conn.commit()
        except Exception:
            self.logger.exception(
                "Error enriching instrument filters to beamline", exc_info=True
            )
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
                                SELECT f.document_id, 'publisher', %s, 'DERIVED'::filter_type
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
        self.enrich_instrument_to_beamline()
        self.logger.info("Enrich filter process completed.")
