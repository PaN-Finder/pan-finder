from fastapi import APIRouter
from pydantic import BaseModel

from ..engine import search, SearchResponse
from ..logging import get_logger

# Get logger for this module
logger = get_logger(__name__)

router = APIRouter(prefix="/search")


class SearchRequest(BaseModel):
    query: str


@router.post("/", response_model=SearchResponse)
async def search_with_ai(request: SearchRequest):
    result = await search(request.query)
    logger.info(
        f"Search completed - Query: '{result.original_query}', Results: {result.total_results}"
    )
    return result
