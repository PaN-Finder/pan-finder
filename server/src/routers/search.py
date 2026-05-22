import asyncio
import copy
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..core.engine import get_search_engine
from ..db.models.search import EnhancedSearchResult, StructuredQueryData
from ..db.models.statistic import ExtendedResults, Statistic
from ..db.models.statistic_repository import StatisticRepository
from ..routers.session import verify_session
from ..utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/search")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query (cannot be empty)")


class SearchResponse(BaseModel):
    id: str | None
    raw_structured_data: dict
    relevant_results: list[EnhancedSearchResult] = []
    weakly_relevant_results: list[EnhancedSearchResult] = []
    total_results: int


class RephraseResponse(BaseModel):
    original_query: str
    rewritten_query: str


class StructuredSearchRequest(BaseModel):
    modified_query_id: str = Field(
        ..., description="ID of the modified query (required)"
    )
    structured_data: dict = Field(..., description="Structured search data")


class StreamEvent(BaseModel):
    event: str
    data: dict | None = None


class ExplainRequest(BaseModel):
    statistic_id: str = Field(
        ..., description="ID of the statistic to which the document explanation relates"
    )
    doi: str = Field(..., min_length=1, description="DOI of the document to explain")


class RephraseRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Query text to rewrite")


# --- Helper functions for streaming events ---
async def sse_yield(evt: StreamEvent):
    """Async generator that yields a formatted SSE event and sleeps briefly."""
    yield f"event: {evt.event}\ndata: {json.dumps(evt.data)}\n\n"
    await asyncio.sleep(0.1)  # Ensure client receives the event


@router.post("/rephrase")
async def rephrase_query(
    request: RephraseRequest,
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
) -> RephraseResponse:
    verify_session(x_session_id)

    engine = get_search_engine()
    rewritten_query = await engine.rephrase_query_for_search(request.query)

    return RephraseResponse(
        original_query=request.query,
        rewritten_query=rewritten_query or request.query,
    )


@router.post("")
async def search_with_ai_stream(
    request: SearchRequest,
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
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
            search_results, sql_query, knee_point_result = await engine.execute_search(
                search_data
            )

            relevant_results: list[EnhancedSearchResult] = (
                knee_point_result.filtered_results
                if knee_point_result
                else search_results
            )
            weakly_relevant_results: list[EnhancedSearchResult] = (
                [r for r in search_results if r not in relevant_results]
                if knee_point_result
                else []
            )

            # Store statistics
            stat_id = None
            try:
                stat = Statistic(
                    search_query=raw_query,
                    sql_query=sql_query.as_string(),
                    structured_data=raw_structured_data,
                    results=ExtendedResults(
                        relevant=relevant_results,
                        weakly_relevant=weakly_relevant_results,
                        knee_point=(
                            knee_point_result.knee_point_value
                            if knee_point_result
                            else None
                        ),
                    ),
                    execution_time_ms=0,  # Optionally measure and store real execution time
                )
                stat_id = StatisticRepository.insert(stat)
            except Exception as e:
                logger.error(f"Failed to store statistics: {e}")

            response = SearchResponse(
                id=stat_id,
                raw_structured_data=raw_structured_data,
                relevant_results=relevant_results,
                weakly_relevant_results=weakly_relevant_results,
                total_results=len(search_results),
            )

            async for event in sse_yield(
                StreamEvent(event="results", data=response.model_dump())
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


@router.post("/explain")
async def explain_search_result(
    request: ExplainRequest,
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
) -> StreamingResponse:
    """
    Endpoint to explain why a specific document was returned for a given search query.
    Streams explanation chunks as they are generated.
    """
    verify_session(x_session_id)

    logger.info(
        f"Verifying statistic ID: {request.statistic_id} for document DOI: {request.doi}"
    )

    # Fetch statistic row to ensure it exists
    statistic = StatisticRepository.select_by_id(request.statistic_id)

    if not statistic:
        logger.error(f"Statistic with ID {request.statistic_id} not found.")
        raise HTTPException(status_code=404, detail="Statistic not found.")

    # Check if doi is in the statistic's result data (to prevent invalid explanations)
    if statistic.results is None:
        all_results = []
    else:
        all_results = list(statistic.results.relevant) + list(
            statistic.results.weakly_relevant
        )

    ## extract document from results
    doc = next(
        (
            result
            for result in all_results
            if getattr(result, "doi", None) == request.doi
        ),
        None,
    )

    if not doc:
        logger.error(
            f"DOI {request.doi} not found in statistic results for ID {request.statistic_id}."
        )
        raise HTTPException(
            status_code=400, detail="DOI not found in statistic results."
        )

    async def event_generator() -> AsyncGenerator[str, None]:
        connection_id = id(asyncio.current_task())

        logger.info(
            f"Starting explanation stream {connection_id} for query: {statistic.search_query} and document DOI: {request.doi}"
        )

        try:
            async for event in sse_yield(StreamEvent(event="explanation_started")):
                yield event

            engine = get_search_engine()
            structured_data = StructuredQueryData(
                **copy.deepcopy(statistic.structured_data)
            )

            async for explanation_chunk in engine.explain_relevancy_of_document(
                statistic.search_query,
                doc,
                structured_data,
            ):
                async for event in sse_yield(
                    StreamEvent(
                        event="explanation_chunk",
                        data={
                            "doi": request.doi,
                            "content": explanation_chunk,
                        },
                    )
                ):
                    yield event

            async for event in sse_yield(StreamEvent(event="explanation_completed")):
                yield event

        except asyncio.CancelledError:
            logger.info(f"Explanation stream {connection_id} cancelled by client")
            return
        except Exception as e:
            logger.error(f"Error in explanation stream {connection_id}: {e}")
            async for event in sse_yield(
                StreamEvent(
                    event="error", data={"message": f"Explanation failed: {str(e)}"}
                )
            ):
                yield event
            return
        finally:
            logger.info(f"Explanation stream {connection_id} ended")

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
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
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
            search_results, sql_query, knee_point_result = await engine.execute_search(
                structured_data
            )

            relevant_results: list[EnhancedSearchResult] = (
                knee_point_result.filtered_results if knee_point_result else []
            )
            weakly_relevant_results: list[EnhancedSearchResult] = (
                [r for r in search_results if r not in relevant_results]
                if knee_point_result
                else search_results
            )

            stat_id = None
            try:
                stat = Statistic(
                    search_query=original.search_query,
                    sql_query=sql_query.as_string(),
                    structured_data=request.structured_data,
                    results=ExtendedResults(
                        relevant=relevant_results,
                        weakly_relevant=weakly_relevant_results,
                        knee_point=(
                            knee_point_result.knee_point_value
                            if knee_point_result
                            else None
                        ),
                    ),
                    execution_time_ms=0,
                    modified_query_id=request.modified_query_id,
                )
                stat_id = StatisticRepository.insert(stat)
            except Exception as e:
                logger.error(f"Failed to store statistics: {e}")

            response = SearchResponse(
                id=stat_id,
                raw_structured_data=request.structured_data,
                relevant_results=relevant_results,
                weakly_relevant_results=weakly_relevant_results,
                total_results=len(search_results),
            )

            async for event in sse_yield(
                StreamEvent(event="results", data=response.model_dump())
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
