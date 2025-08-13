from psycopg.rows import dict_row
from typing import List, cast

from ..connection import get_db_connection
from .document import Document, DocumentTypedDict


class DocumentRepository:
    """
    Repository for CRUD operations on the document table.
    """

    @staticmethod
    def get_by_doi(doi: str) -> Document:
        query = """
            SELECT d.id, d.doi, d.title, d.text, d.summary, d.raw, f.name AS facility_name
            FROM document d
            LEFT JOIN facility f ON d.facility_id = f.id
            WHERE d.doi = %s
        """
        with get_db_connection() as conn:
            cur = conn.execute(query, [doi])
            row = cur.fetchone()
            if row:
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    return Document.from_row(dict(zip(columns, row)))
                else:
                    raise RuntimeError("Database query returned no column information")
            raise RuntimeError(f"Document with doi {doi} not found.")

    @staticmethod
    def get_document_details_by_dois(dois: List[str]) -> List[DocumentTypedDict]:
        if not dois:
            return []

        query = """
            SELECT d.doi, d.title, d.summary, f.name AS facility_name
            FROM document d
            LEFT JOIN facility f ON d.facility_id = f.id
            WHERE d.doi = ANY(%s)
        """
        with get_db_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(query, [dois])
                return cast(List[DocumentTypedDict], cursor.fetchall())
