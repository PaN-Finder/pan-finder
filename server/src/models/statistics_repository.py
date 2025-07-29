from ..database import get_db_connection
from .statistics import Statistics
import json


class StatisticsRepository:
    """
    Repository for CRUD operations on the statistics table.
    """

    @staticmethod
    def insert(stat: Statistics) -> int:
        """
        Insert a new statistics record into the database.
        Returns the new record's ID.
        """
        query = """
            INSERT INTO statistics (search_query, structured_data, results, execution_time_ms, is_modified)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """
        with get_db_connection() as conn:
            # psycopg3: use conn.execute, returns a cursor
            cur = conn.execute(
                query,
                [
                    stat.search_query,
                    json.dumps(stat.structured_data),
                    json.dumps(stat.results),
                    stat.execution_time_ms,
                    stat.is_modified,
                ],
            )
            row = cur.fetchone()
            if row:
                return row[0]
            raise RuntimeError("Failed to insert statistics record.")

    @staticmethod
    def update(stat: Statistics) -> bool:
        if stat.id is None:
            raise ValueError("Statistics ID is required for update.")
        query = """
            UPDATE statistics
            SET search_query = %s, structured_data = %s, results = %s, execution_time_ms = %s, is_modified = %s
            WHERE id = %s
        """
        with get_db_connection() as conn:
            cur = conn.execute(
                query,
                [
                    stat.search_query,
                    json.dumps(stat.structured_data),
                    json.dumps(stat.results),
                    stat.execution_time_ms,
                    stat.is_modified,
                    stat.id,
                ],
            )
            return cur.rowcount > 0
