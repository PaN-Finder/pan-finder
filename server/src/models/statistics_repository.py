from ..database import get_db_connection
from .statistics import Statistics
import json


class StatisticsRepository:
    """
    Repository for CRUD operations on the statistics table.
    """

    """ Select row by id"""

    @staticmethod
    def select_by_id(stat_id: str) -> Statistics:
        """
        Select a statistics record by its UUID.
        Returns a Statistics instance or raises an error if not found.
        """
        query = "SELECT * FROM statistics WHERE id = %s"
        with get_db_connection() as conn:
            cur = conn.execute(query, (stat_id,))
            row = cur.fetchone()
            if row:
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    return Statistics.from_row(dict(zip(columns, row)))
                else:
                    raise RuntimeError("Database query returned no column information")
            raise ValueError(f"Statistics record with id {stat_id} not found.")

    @staticmethod
    def insert(stat: Statistics) -> str:
        """
        Insert a new statistics record into the database.
        Returns the new record's UUID as a string.
        """
        query = """
            INSERT INTO statistics (search_query, structured_data, results, execution_time_ms, modified_query_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        with get_db_connection() as conn:
            cur = conn.execute(
                query,
                [
                    stat.search_query,
                    json.dumps(stat.structured_data),
                    json.dumps(stat.results),
                    stat.execution_time_ms,
                    stat.modified_query_id,
                ],
            )
            row = cur.fetchone()
            if row:
                return str(row[0])
            raise RuntimeError("Failed to insert statistics record.")
