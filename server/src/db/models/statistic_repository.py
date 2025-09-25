from ..connection import get_database_connection
from .statistic import Statistic
import json


class StatisticRepository:
    """
    Repository for CRUD operations on the statistic table.
    """

    """ Select row by id"""

    @staticmethod
    def select_by_id(stat_id: str) -> Statistic:
        """
        Select a statistic record by its UUID.
        Returns a Statistic instance or raises an error if not found.
        """
        query = "SELECT * FROM statistic WHERE id = %s"
        with get_database_connection() as conn:
            cur = conn.execute(query, (stat_id,))
            row = cur.fetchone()
            if row:
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    return Statistic.from_row(dict(zip(columns, row)))
                else:
                    raise RuntimeError("Database query returned no column information")
            raise ValueError(f"Statistics record with id {stat_id} not found.")

    @staticmethod
    def insert(stat: Statistic) -> str:
        """
        Insert a new statistic record into the database.
        Returns the new record's UUID as a string.
        """
        query = """
            INSERT INTO statistic (search_query, sql_query, structured_data, results, execution_time_ms, modified_query_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        with get_database_connection() as conn:
            cur = conn.execute(
                query,
                [
                    stat.search_query,
                    stat.sql_query,
                    json.dumps(stat.structured_data),
                    json.dumps(
                        stat.results.serializable_results if stat.results else None
                    ),
                    stat.execution_time_ms,
                    stat.modified_query_id,
                ],
            )
            row = cur.fetchone()
            if row:
                return str(row[0])
            raise RuntimeError("Failed to insert statistic record.")
