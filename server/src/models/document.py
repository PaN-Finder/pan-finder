from typing import Optional


class Document:
    """
    Model class representing a row in the 'document' table.
    """

    def __init__(
        self,
        id: Optional[int] = None,
        doi: str = "",
        title: str = "",
        text: Optional[str] = None,
        summary: Optional[str] = None,
        raw: Optional[str] = None,
        facility_name: Optional[str] = None,
    ):
        self.id = id
        self.doi = doi
        self.title = title
        self.text = text
        self.summary = summary
        self.raw = raw
        self.facility_name = facility_name

    @classmethod
    def from_row(cls, row: dict):
        """
        Create a Document instance from a database row (dict).
        """
        return cls(
            id=row.get("id"),
            doi=row["doi"],
            title=row["title"],
            text=row.get("text"),
            summary=row.get("summary"),
            raw=row.get("raw"),
            facility_name=row.get("facility_name"),
        )

    def to_dict(self):
        """
        Convert the Document instance to a dict for database operations.
        """
        return {
            "id": self.id,
            "doi": self.doi,
            "title": self.title,
            "text": self.text,
            "summary": self.summary,
            "raw": self.raw,
            "facility_name": self.facility_name,
        }
