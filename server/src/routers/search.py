from fastapi import APIRouter, Depends

from pydantic import BaseModel
from typing import List

from ..engine import search
from ..logging import get_logger

# Get logger for this module
logger = get_logger(__name__)

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
    result: dict = Depends(search),
):
    logger.info(
        f"Search completed - Query: '{result.get('original_query', 'N/A')}', Results: {result.get('total_results', 0)}"
    )
    return result
