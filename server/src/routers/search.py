from fastapi import APIRouter, Depends

from pydantic import BaseModel
from typing import List

from ..engine import search, get_builder, get_openai_client
from ..core.search_query_builder import SearchQueryBuilder
from openai import AzureOpenAI

router = APIRouter(prefix="/search")


class EnhancedSearchResult(BaseModel):
    doi: str
    title: str
    overall_score: float
    similarity_score: float
    chunk_similarity_score: float
    full_match_score: float
    partial_match_score: float
    keyword_score: float


class SearchResponse(BaseModel):
    original_query: str
    structured_query: dict
    results: List[EnhancedSearchResult]
    total_results: int


@router.get("/", response_model=SearchResponse)
async def search_with_ai(
    query: str,
    builder: SearchQueryBuilder = Depends(get_builder),
    openai_client: AzureOpenAI = Depends(get_openai_client),
):
    """
    Perform a search with the given query and return enhanced results.

    Args:
        query (str): The search query string.

    Returns:
        SearchResponse: A response model containing the original query,
                        structured query, and search results.
    """
    return await search(query, builder, openai_client)
