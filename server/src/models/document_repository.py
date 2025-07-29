from ..database import get_db_connection
from .document import Document


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
