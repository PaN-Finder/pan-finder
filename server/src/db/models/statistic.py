from datetime import datetime
from typing import Optional, Any, Dict, List

from src.db.models.search import EnhancedSearchResult


class ExtendedResults:
    """Structure for search results with knee point filtering."""

    def __init__(
        self,
        relevant: List[EnhancedSearchResult],
        weakly_relevant: List[EnhancedSearchResult],
        knee_point: float | None = None,
    ):
        self.relevant = relevant
        self.weakly_relevant = weakly_relevant
        self.knee_point = knee_point

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtendedResults":
        """Create ExtendedResults from dictionary data (from database)."""

        return cls(
            relevant=[
                EnhancedSearchResult(**item)
                for item in data.get("relevant", [])
                if item is not None
            ],
            weakly_relevant=[
                EnhancedSearchResult(**item)
                for item in data.get("weakly_relevant", [])
                if item is not None
            ],
            knee_point=data.get("knee_point"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON serialization."""
        result: Dict[str, Any] = {
            "relevant": [r.model_dump() for r in self.relevant],
            "weakly_relevant": [r.model_dump() for r in self.weakly_relevant],
        }
        if self.knee_point is not None:
            result["knee_point"] = self.knee_point
        return result

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]


class Statistic:
    """
    Model class representing a row in the 'statistic' table.
    """

    def __init__(
        self,
        id: Optional[str] = None,  # UUID as string
        search_query: str = "",
        sql_query: str = "",  # The actual SQL query executed against the database
        structured_data: Any = None,
        results: Optional[ExtendedResults] = None,
        execution_time_ms: int = 0,
        modified_query_id: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        self.id = id
        self.search_query = search_query
        self.sql_query = sql_query
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
        # Convert dict results back to ExtendedResults if present
        results = None
        results_data = row.get("results")

        if results_data is not None and isinstance(results_data, dict):
            results = ExtendedResults.from_dict(results_data)

        return cls(
            id=str(row.get("id")),
            search_query=row["search_query"],
            sql_query=row.get("sql_query", ""),
            structured_data=row["structured_data"],
            results=results,
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
            "sql_query": self.sql_query,
            "structured_data": self.structured_data,
            "results": self.results.to_dict() if self.results else None,
            "execution_time_ms": self.execution_time_ms,
            "modified_query_id": self.modified_query_id,
            "created_at": self.created_at,
        }
