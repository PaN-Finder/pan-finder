from ..connection import get_db_connection
from .feedback import Feedback
import json


class FeedbackRepository:
    @staticmethod
    def insert(feedback: Feedback) -> int:
        """
        Insert a new feedback record into the database.
        Returns the new record's SERIAL id as an int.
        """
        query = """
			INSERT INTO feedback (statistic_id, feedback_type, metadata)
			VALUES (%s, %s, %s)
			RETURNING id
		"""
        with get_db_connection() as conn:
            cur = conn.execute(
                query,
                [
                    feedback.statistic_id,
                    feedback.feedback_type,
                    (
                        json.dumps(feedback.metadata)
                        if feedback.metadata is not None
                        else None
                    ),
                ],
            )
            row = cur.fetchone()
            if row:
                return int(row[0])
            raise RuntimeError("Failed to insert feedback record.")

    @staticmethod
    def select_by_statistic_id_and_metadata(
        statistic_id: str, metadata: dict
    ) -> Feedback | None:
        """
        Select feedback by statistic ID and metadata.
        Returns a Feedback instance or None if not found.
        """
        query = """
            SELECT * FROM feedback
            WHERE statistic_id = %s AND metadata = %s
        """
        with get_db_connection() as conn:
            cur = conn.execute(
                query,
                [
                    statistic_id,
                    json.dumps(metadata) if metadata is not None else None,
                ],
            )
            row = cur.fetchone()
            if row:
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                return Feedback.from_row(dict(zip(columns, row)))
            return None

    @staticmethod
    def update_feedback_type(feedback_id: int, feedback_type: str) -> Feedback | None:
        """
        Update the feedback type for an existing feedback record.
        Returns the updated Feedback instance or None if not found.
        """
        query = """
            UPDATE feedback
            SET feedback_type = %s
            WHERE id = %s
            RETURNING *
        """
        with get_db_connection() as conn:
            cur = conn.execute(query, [feedback_type, feedback_id])
            row = cur.fetchone()
            if row:
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                return Feedback.from_row(dict(zip(columns, row)))
            return None
