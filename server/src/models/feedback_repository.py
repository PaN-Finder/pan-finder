from ..database import get_db_connection
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
