import copy
import json
import asyncio
from typing import AsyncGenerator, Dict, List
from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..engine import EnhancedSearchResult, StructuredQueryData, get_search_engine
from ..models.statistic import Statistic
from ..models.statistic_repository import StatisticRepository
from ..setup_logging import get_logger
from ..routers.session import verify_session

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
async def search_with_ai_stream(
    request: SearchRequest,
    x_session_id: str = Header(..., alias="X-Session-ID"),
) -> StreamingResponse:
    verify_session(x_session_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        connection_id = id(asyncio.current_task())
        logger.info(
            f"Starting search stream {connection_id} for query: {request.query}"
        )

        try:
            # Step 1: Analysis started
            async for event in sse_yield(StreamEvent(event="analysis_started")):
                yield event

            engine = get_search_engine()

            # Step 2: Extract structured query (LLM processing)
            raw_query = request.query
            search_data = await engine.parse_query_to_structured_data(raw_query)
            raw_structured_data = search_data.model_dump()

            async for event in sse_yield(StreamEvent(event="analysis_completed")):
                yield event

            # Step 3: Start database query
            async for event in sse_yield(StreamEvent(event="data_fetching")):
                yield event

            # Step 4: Execute search and stream final results
            search_results = await engine.execute_search(search_data)

            # Store statistics
            stat_id = None
            try:
                stat = Statistic(
                    search_query=raw_query,
                    structured_data=raw_structured_data,
                    results=[result.model_dump() for result in search_results],
                    execution_time_ms=0,  # Optionally measure and store real execution time
                )
                stat_id = StatisticRepository.insert(stat)
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

            if len(search_results) > 0:
                # Step 5: Stream explanation
                async for event in sse_yield(StreamEvent(event="explanation_started")):
                    yield event

                try:
                    async for explanation_chunk in engine.explain_search_results(
                        raw_query, search_results, search_data
                    ):
                        async for event in sse_yield(
                            StreamEvent(
                                event="explanation_chunk",
                                data={"content": explanation_chunk},
                            )
                        ):
                            yield event

                except Exception as e:
                    logger.error(f"Failed to generate explanation: {e}")
                    async for event in sse_yield(
                        StreamEvent(
                            event="explanation_error",
                            data={
                                "message": "Unable to generate explanation for these results."
                            },
                        )
                    ):
                        yield event

            async for event in sse_yield(StreamEvent(event="search_completed")):
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
    x_session_id: str = Header(..., alias="X-Session-ID"),
) -> StreamingResponse:
    """
    Search endpoint that accepts structured search data directly, bypassing LLM analysis.
    """
    # Verify session before processing
    verify_session(x_session_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        connection_id = id(asyncio.current_task())
        logger.info(
            f"Starting structured search stream {connection_id} for data: {request.structured_data} with modified query ID: {request.modified_query_id}"
        )

        try:
            # Step 1: Find the original query in database
            async for event in sse_yield(StreamEvent(event="analysis_started")):
                yield event

            original = StatisticRepository.select_by_id(request.modified_query_id)
            if not original:
                raise ValueError(
                    f"Original query with ID {request.modified_query_id} not found."
                )

            async for event in sse_yield(StreamEvent(event="analysis_completed")):
                yield event

            # Step 2: Start database query (no LLM analysis needed)
            async for event in sse_yield(StreamEvent(event="data_fetching")):
                yield event

            engine = get_search_engine()
            structured_data: StructuredQueryData = StructuredQueryData(
                **copy.deepcopy(request.structured_data)
            )

            # Step 3: Execute search directly with structured data
            search_results = await engine.execute_search(structured_data)

            stat_id = None
            try:
                stat = Statistic(
                    search_query=original.search_query,
                    structured_data=request.structured_data,
                    results=[result.model_dump() for result in search_results],
                    execution_time_ms=0,
                    modified_query_id=request.modified_query_id,
                )
                stat_id = StatisticRepository.insert(stat)
            except Exception as e:
                logger.error(f"Failed to store statistics: {e}")

            response = SearchResponse(
                id=stat_id,
                raw_structured_data=request.structured_data,
                results=search_results,
                total_results=len(search_results),
            )

            async for event in sse_yield(
                StreamEvent(event="results", data=response.model_dump())
            ):
                yield event

            if len(search_results) == 0:
                # Step 4: Stream explanation
                async for event in sse_yield(StreamEvent(event="explanation_started")):
                    yield event

                try:
                    async for explanation_chunk in engine.explain_search_results(
                        original.search_query, search_results, structured_data
                    ):
                        async for event in sse_yield(
                            StreamEvent(
                                event="explanation_chunk",
                                data={"content": explanation_chunk},
                            )
                        ):
                            yield event

                except Exception as e:
                    logger.error(f"Failed to generate explanation: {e}")
                    async for event in sse_yield(
                        StreamEvent(
                            event="explanation_error",
                            data={
                                "message": "Unable to generate explanation for these results."
                            },
                        )
                    ):
                        yield event

            async for event in sse_yield(StreamEvent(event="search_completed")):
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
