from datetime import datetime
from typing import Optional, Any, Dict, Sequence, Protocol


class ResultItem(Protocol):
    """Protocol for result items that can be serialized."""

    def model_dump(self) -> Dict[str, Any]: ...


class ExtendedResults:
    """Structure for search results with knee point filtering."""

    def __init__(
        self,
        relevant: Sequence[ResultItem],
        weakly_relevant: Sequence[ResultItem],
        knee_point: Optional[Any] = None,
    ):
        self.relevant = relevant
        self.weakly_relevant = weakly_relevant
        self.knee_point = knee_point

    @property
    def serializable_results(self) -> Dict[str, Any]:
        """Get results in serializable format for database storage."""
        return self.to_dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtendedResults":
        """Create ExtendedResults from dictionary data (from database)."""

        class SimpleResultItem:
            def __init__(self, data: dict):
                self.data = data

            def model_dump(self) -> Dict[str, Any]:
                return self.data

        return cls(
            relevant=[SimpleResultItem(item) for item in data.get("relevant", [])],
            weakly_relevant=[
                SimpleResultItem(item) for item in data.get("weakly_relevant", [])
            ],
            knee_point=data.get("knee_point"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for JSON serialization."""
        result = {
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
        if row.get("results") and isinstance(row["results"], dict):
            results = ExtendedResults.from_dict(row["results"])

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
            "results": self.results.serializable_results if self.results else None,
            "execution_time_ms": self.execution_time_ms,
            "modified_query_id": self.modified_query_id,
            "created_at": self.created_at,
        }
