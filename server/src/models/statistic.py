from datetime import datetime
from typing import Optional, Any


class Statistic:
    """
    Model class representing a row in the 'statistic' table.
    """

    def __init__(
        self,
        id: Optional[str] = None,  # UUID as string
        search_query: str = "",
        structured_data: Any = None,
        results: Any = None,
        execution_time_ms: int = 0,
        modified_query_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        self.id = id
        self.search_query = search_query
        self.structured_data = structured_data
        self.results = results
        self.execution_time_ms = execution_time_ms
        self.modified_query_id = modified_query_id
        self.created_at = created_at

    @classmethod
    def from_row(cls, row: dict):
        """
        Create a Statistic instance from a database row (dict).
        """
        return cls(
            id=str(row.get("id")),
            search_query=row["search_query"],
            structured_data=row["structured_data"],
            results=row["results"],
            execution_time_ms=row["execution_time_ms"],
            modified_query_id=str(row.get("modified_query_id")),
            created_at=row.get("created_at"),
        )

    def to_dict(self):
        """
        Convert the Statistic instance to a dict for database operations.
        """
        return {
            "id": self.id,
            "search_query": self.search_query,
            "structured_data": self.structured_data,
            "results": self.results,
            "execution_time_ms": self.execution_time_ms,
            "modified_query_id": self.modified_query_id,
            "created_at": self.created_at,
        }
