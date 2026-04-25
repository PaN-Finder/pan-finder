from typing import Optional, TypedDict


class DocumentTypedDict(TypedDict):
    id: Optional[int]
    doi: str
    title: str
    abstract: Optional[str]
    summary: Optional[str]
    raw: Optional[str]
    facility_name: Optional[str]
    publication_year: Optional[str]
    instrument_name: Optional[str]
    authors: Optional[str]


class Document:
    """
    Model class representing a row in the 'document' table.
    """

    def __init__(
        self,
        id: Optional[int] = None,
        doi: str = "",
        title: str = "",
        abstract: Optional[str] = None,
        summary: Optional[str] = None,
        raw: Optional[str] = None,
        facility_name: Optional[str] = None,
        publication_year: Optional[str] = None,
        instrument_name: Optional[str] = None,
        authors: Optional[str] = None,
    ):
        self.id = id
        self.doi = doi
        self.title = title
        self.abstract = abstract
        self.summary = summary
        self.raw = raw
        self.facility_name = facility_name
        self.publication_year = publication_year
        self.instrument_name = instrument_name
        self.authors = authors

    @classmethod
    def from_row(cls, row: dict):
        """
        Create a Document instance from a database row (dict).
        """
        return cls(
            id=row.get("id"),
            doi=row["doi"],
            title=row["title"],
            abstract=row.get("abstract"),
            summary=row.get("summary"),
            raw=row.get("raw"),
            facility_name=row.get("facility_name"),
            publication_year=row.get("publication_year"),
            instrument_name=row.get("instrument_name"),
            authors=row.get("authors"),
        )

    def to_dict(self):
        """
        Convert the Document instance to a dict for database operations.
        """
        return {
            "id": self.id,
            "doi": self.doi,
            "title": self.title,
            "abstract": self.abstract,
            "summary": self.summary,
            "raw": self.raw,
            "facility_name": self.facility_name,
            "publication_year": self.publication_year,
            "instrument_name": self.instrument_name,
            "authors": self.authors,
        }
