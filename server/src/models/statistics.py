from datetime import datetime
from typing import Optional, Any


class Statistics:
    """
    Model class representing a row in the 'statistics' table.
    """

    def __init__(
        self,
        id: Optional[int] = None,
        search_query: str = "",
        structured_data: Any = None,
        results: Any = None,
        execution_time_ms: int = 0,
        is_modified: bool = False,
        created_at: Optional[datetime] = None,
    ):
        self.id = id
        self.search_query = search_query
        self.structured_data = structured_data
        self.results = results
        self.execution_time_ms = execution_time_ms
        self.is_modified = is_modified
        self.created_at = created_at

    @classmethod
    def from_row(cls, row: dict):
        """
        Create a Statistics instance from a database row (dict).
        """
        return cls(
            id=row.get("id"),
            search_query=row["search_query"],
            structured_data=row["structured_data"],
            results=row["results"],
            execution_time_ms=row["execution_time_ms"],
            is_modified=row.get("is_modified", False),
            created_at=row.get("created_at"),
        )

    def to_dict(self):
        """
        Convert the Statistics instance to a dict for database operations.
        """
        return {
            "id": self.id,
            "search_query": self.search_query,
            "structured_data": self.structured_data,
            "results": self.results,
            "execution_time_ms": self.execution_time_ms,
            "is_modified": self.is_modified,
            "created_at": self.created_at,
        }
