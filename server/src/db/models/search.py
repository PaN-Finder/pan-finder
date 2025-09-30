"""
Search-related model classes.

This module contains Pydantic models used for search operations.
"""

from typing import Dict, List, Any
from pydantic import BaseModel


class StructuredQueryData(BaseModel):
    """
    Structured representation of a parsed search query.

    This model represents the structured data extracted from a natural language
    search query, containing the user's intention, relevant keywords, and any
    filters to apply to the search.
    """

    intention: str
    keywords: List[str]
    filters: Dict[str, Any]


class EnhancedSearchResult(BaseModel):
    """
    Enhanced search result with detailed scoring information.

    Contains document metadata and various scoring components
    used to rank and present search results.
    """

    doi: str
    title: str
    facility_name: str
    abstract: str
    overall_score: float
    similarity_score: float
    chunk_similarity_score: float
    full_match_score: float
    partial_match_score: float
    keyword_score: float
