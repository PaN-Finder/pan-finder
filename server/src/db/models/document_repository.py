from psycopg.rows import dict_row
from typing import List, cast

from ..connection import get_database_connection
from .document import Document, DocumentTypedDict


class DocumentRepository:
    """
    Repository for CRUD operations on the document table.
    """

    DETAIL_FILTER_KEYS_BY_FIELD = {
        "publication_year": {
            1: ["publicationYear"],
            2: ["publicationYear"],
            3: ["publicationYear"],
            4: ["publicationYear"],
            5: ["publicationYear"],
            6: ["publicationYear"],
        },
        "instrument_name": {
            1: ["instruments.name"], # ILL
            2: ["creationLocation"], # ESS
            3: ["beamline"], # PSI
            4: ["creationLocation"], # MAX IV
            5: ["beamline", "instruments.name"], # ESRF
            6: ["instrument.name"], # DESY
        },
        "authors": {
            1: ["authors.name"],
            2: ["creator", "authors"],
            3: ["creator"],
            4: ["creator"],
            5: ["creators.name"],
            6: ["creator"],
        },
    }

    @classmethod
    def _get_detail_filter_keys(
        cls, field_name: str, facility_id: int | None
    ) -> list[str]:
        field_mappings: dict[int, list[str]] = cls.DETAIL_FILTER_KEYS_BY_FIELD.get(
            field_name, {}
        )
        if facility_id is not None and facility_id in field_mappings:
            return field_mappings[facility_id]
        return []

    @classmethod
    def _split_detail_value(
        cls, field_name: str, key: str, value: str
    ) -> list[str]:
        stripped_value = value.strip()
        if not stripped_value:
            return []

        if field_name == "authors":
            parts = [part.strip() for part in stripped_value.split(",") if part.strip()]
            if len(parts) <= 1:
                return parts

            # Keep surname-first names like "x, y" intact while still
            # splitting obvious combined author rows like "x y, x y".
            if all(" " in part for part in parts):
                return parts

            return [stripped_value]

        return [part.strip() for part in stripped_value.split(",") if part.strip()]

    @classmethod
    def _get_detail_field_values(
        cls, conn, document_id: int | None, field_names: list[str], facility_id: int | None
    ) -> dict[str, str | None]:
        filter_keys_by_field = {
            field_name: cls._get_detail_filter_keys(field_name, facility_id)
            for field_name in field_names
        }
        all_filter_keys: list[str] = []
        for filter_keys in filter_keys_by_field.values():
            for filter_key in filter_keys:
                if filter_key not in all_filter_keys:
                    all_filter_keys.append(filter_key)

        if document_id is None or not all_filter_keys:
            return {field_name: None for field_name in field_names}

        filter_query = """
            SELECT key, value
            FROM filter
            WHERE document_id = %s
              AND key = ANY(%s)
              AND value IS NOT NULL
              AND value != ''
            ORDER BY array_position(%s::text[], key), id ASC
        """
        
        filter_cursor = conn.execute(
            filter_query, [document_id, all_filter_keys, all_filter_keys]
        )
        rows = filter_cursor.fetchall()

        detail_values: dict[str, str | None] = {}
        for field_name, filter_keys in filter_keys_by_field.items():
            values: list[str] = []
            seen_values: set[str] = set()
            valid_keys = set(filter_keys)

            for key, value in rows:
                if key not in valid_keys:
                    continue
                for part in cls._split_detail_value(field_name, key, value):
                    dedupe_key = part.casefold()
                    if dedupe_key in seen_values:
                        continue
                    seen_values.add(dedupe_key)
                    values.append(part)

            detail_values[field_name] = " - ".join(values) if values else None

        return detail_values

    @staticmethod
    def get_by_doi(doi: str) -> Document:
        query = """
            SELECT d.id, d.doi, d.title, d.text as abstract, d.summary, d.raw,
                   d.facility_id, f.name AS facility_name
            FROM document d
            LEFT JOIN facility f ON d.facility_id = f.id
            WHERE d.doi = %s
        """
        with get_database_connection() as conn:
            cur = conn.execute(query, [doi])
            row = cur.fetchone()
            if row:
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    row_data = dict(zip(columns, row))
                    facility_id = row_data.get("facility_id")
                    row_data.update(
                        DocumentRepository._get_detail_field_values(
                            conn,
                            row_data.get("id"),
                            ["instrument_name", "publication_year", "authors"],
                            facility_id,
                        )
                    )
                    return Document.from_row(row_data)
                else:
                    raise RuntimeError("Database query returned no column information")
            raise RuntimeError(f"Document with doi {doi} not found.")

    @staticmethod
    def get_document_details_by_dois(dois: List[str]) -> List[DocumentTypedDict]:
        if not dois:
            return []

        query = """
            SELECT d.doi, d.title, d.text as abstract, f.name AS facility_name
            FROM document d
            LEFT JOIN facility f ON d.facility_id = f.id
            WHERE d.doi = ANY(%s)
        """
        with get_database_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, [dois])
                return cast(List[DocumentTypedDict], cursor.fetchall())
