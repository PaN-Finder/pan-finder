import copy
import json
import asyncio
from typing import AsyncGenerator, Dict, List
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..engine import EnhancedSearchResult, get_search_engine
from ..models.statistics import Statistics
from ..models.statistics_repository import StatisticsRepository
from ..setup_logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/search")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query (cannot be empty)")


class SearchResponse(BaseModel):
    id: str | None
    raw_structured_data: dict
    results: List[EnhancedSearchResult]
    total_results: int


class StructuredSearchRequest(BaseModel):
    modified_query_id: str = Field(
        ..., description="ID of the modified query (required)"
    )
    structured_data: Dict = Field(..., description="Structured search data")


class StreamEvent(BaseModel):
    event: str
    data: dict | None = None


# --- Helper functions for streaming events ---
async def sse_yield(evt: StreamEvent):
    """Async generator that yields a formatted SSE event and sleeps briefly."""
    yield f"event: {evt.event}\ndata: {json.dumps(evt.data)}\n\n"
    await asyncio.sleep(0.1)  # Ensure client receives the event


@router.post("")
async def search_with_ai_stream(request: SearchRequest) -> StreamingResponse:
    """
    Streaming search endpoint that sends Server-Sent Events (SSE) with real-time updates:
    1. Analysing your query
    2. Analyse done (LLM response got)
    3. Start querying database
    4. Results
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        connection_id = id(asyncio.current_task())
        logger.info(
            f"Starting search stream {connection_id} for query: {request.query}"
        )

        try:
            # Step 1: Analysis started
            async for event in sse_yield(StreamEvent(event="analysing_query")):
                yield event

            engine = get_search_engine()

            # Step 2: Extract structured query (LLM processing)
            raw_query = request.query
            search_data = await engine.parse_query_to_structured_data(raw_query)
            raw_structured_data = copy.deepcopy(search_data)

            async for event in sse_yield(StreamEvent(event="analysing_done")):
                yield event

            # Step 3: Start database query
            async for event in sse_yield(StreamEvent(event="fetching_data")):
                yield event

            # Step 4: Execute search and stream final results
            search_results = await engine.execute_search(search_data)

            # Store statistics
            stat_id = None
            try:
                stat = Statistics(
                    search_query=raw_query,
                    structured_data=raw_structured_data,
                    results=[result.model_dump() for result in search_results],
                    execution_time_ms=0,  # Optionally measure and store real execution time
                )
                stat_id = StatisticsRepository.insert(stat)
            except Exception as e:
                logger.error(f"Failed to store statistics: {e}")

            response = SearchResponse(
                id=stat_id,
                raw_structured_data=raw_structured_data,
                results=search_results,
                total_results=len(search_results),
            )

            async for event in sse_yield(
                StreamEvent(event="results", data=response.model_dump())
            ):
                yield event

        except asyncio.CancelledError:
            logger.info(f"Search stream {connection_id} cancelled by client")
            # Yield a cancelled event if desired, or just end the stream
            return
        except Exception as e:
            logger.error(f"Error in streaming search {connection_id}: {e}")
            async for event in sse_yield(
                StreamEvent(event="error", data={"message": f"Search failed: {str(e)}"})
            ):
                yield event
            return
        finally:
            logger.info(f"Search stream {connection_id} ended")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for real-time streaming
        },
    )


@router.post("/structured")
async def search_with_structured_data(
    request: StructuredSearchRequest,
) -> StreamingResponse:
    """
    Search endpoint that accepts structured search data directly, bypassing LLM analysis.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        connection_id = id(asyncio.current_task())
        logger.info(
            f"Starting structured search stream {connection_id} for data: {request.structured_data} with modified query ID: {request.modified_query_id}"
        )

        try:
            # Step 1: Find the original query in database
            async for event in sse_yield(StreamEvent(event="analysing_query")):
                yield event

            original = StatisticsRepository.select_by_id(request.modified_query_id)
            if not original:
                raise ValueError(
                    f"Original query with ID {request.modified_query_id} not found."
                )

            async for event in sse_yield(StreamEvent(event="analysing_done")):
                yield event

            # Step 2: Start database query (no LLM analysis needed)
            async for event in sse_yield(StreamEvent(event="fetching_data")):
                yield event

            engine = get_search_engine()
            structured_data = copy.deepcopy(request.structured_data)

            # Step 3: Execute search directly with structured data
            search_results = await engine.execute_search(request.structured_data)

            stat_id = None
            try:
                stat = Statistics(
                    search_query=original.search_query,
                    structured_data=structured_data,
                    results=[result.model_dump() for result in search_results],
                    execution_time_ms=0,
                    modified_query_id=request.modified_query_id,
                )
                stat_id = StatisticsRepository.insert(stat)
            except Exception as e:
                logger.error(f"Failed to store statistics: {e}")

            response = SearchResponse(
                id=stat_id,
                raw_structured_data=structured_data,
                results=search_results,
                total_results=len(search_results),
            )

            async for event in sse_yield(
                StreamEvent(event="results", data=response.model_dump())
            ):
                yield event

        except asyncio.CancelledError:
            logger.info(f"Structured search stream {connection_id} cancelled by client")
            return
        except Exception as e:
            logger.error(f"Error in structured search stream {connection_id}: {e}")
            async for event in sse_yield(
                StreamEvent(event="error", data={"message": f"Search failed: {str(e)}"})
            ):
                yield event
            return
        finally:
            logger.info(f"Structured search stream {connection_id} ended")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for real-time streaming
        },
    )
