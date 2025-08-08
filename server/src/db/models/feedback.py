from datetime import datetime
from typing import Optional, Any


class Feedback:
    """
    Model class representing a row in the 'feedback' table.
    """

    def __init__(
        self,
        id: Optional[int] = None,  # SERIAL PRIMARY KEY
        statistic_id: str = "",  # UUID as string
        feedback_type: str = "",  # 'positive' or 'negative'
        metadata: Any = None,
        created_at: Optional[datetime] = None,
    ):
        self.id = id
        self.statistic_id = statistic_id
        self.feedback_type = feedback_type
        self.metadata = metadata
        self.created_at = created_at

    @classmethod
    def from_row(cls, row: dict):
        """
        Create a Feedback instance from a database row (dict).
        """
        return cls(
            id=row.get("id"),
            statistic_id=str(row["statistic_id"]),
            feedback_type=row["feedback_type"],
            metadata=row["metadata"],
            created_at=row.get("created_at"),
        )

    def to_dict(self):
        """
        Convert the Feedback instance to a dict for database operations.
        """
        return {
            "id": self.id,
            "statistic_id": self.statistic_id,
            "feedback_type": self.feedback_type,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }
