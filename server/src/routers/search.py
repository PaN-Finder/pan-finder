from fastapi import APIRouter, Depends

from ..engine import search, SearchResponse
from ..logging import get_logger

# Get logger for this module
logger = get_logger(__name__)

router = APIRouter(prefix="/search")


@router.get("/", response_model=SearchResponse)
async def search_with_ai(
    result: SearchResponse = Depends(search),
):
    logger.info(
        f"Search completed - Query: '{result.original_query}', Results: {result.total_results}"
    )
    return result
