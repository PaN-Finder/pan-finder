import copy
import json
from fastapi import APIRouter, HTTPException, Path
import asyncio
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import AsyncGenerator

from ..engine import SearchResponse, get_search_engine
from ..models.statistics import Statistics
from ..models.statistics_repository import StatisticsRepository
from ..models.document_repository import DocumentRepository
from ..database import get_connection_pool
from ..setup_logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/search")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query (cannot be empty)")


class StructuredSearchRequest(BaseModel):
    structured_data: dict = Field(..., description="Structured search data")
    original_query: str = Field(
        min_length=1,
        description="Original user query that generated this structured data",
    )


class StreamEvent(BaseModel):
    event: str
    data: dict


@router.post("")
async def search_with_ai_stream(request: SearchRequest):
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
            evt = StreamEvent(
                event="analysis_started",
                data={"message": "Analysing your query", "query": request.query},
            )
            yield f"event: {evt.event}\ndata: {json.dumps(evt.data)}\n\n"
            await asyncio.sleep(
                0.1
            )  # Without this, the client does not receive the event

            engine = get_search_engine()

            # Step 2: Extract structured query (LLM processing)
            raw_query = request.query
            search_data = await engine.parse_query_to_structured_data(raw_query)
            raw_structured_data = copy.deepcopy(search_data)

            evt = StreamEvent(
                event="analysis_completed",
                data={"message": "Analysis completed"},
            )
            yield f"event: {evt.event}\ndata: {json.dumps(evt.data)}\n\n"
            await asyncio.sleep(
                0.1
            )  # Without this, the client does not receive the event

            # Step 3: Start database query
            evt = StreamEvent(
                event="database_query_started",
                data={"message": "Start querying database"},
            )
            yield f"event: {evt.event}\ndata: {json.dumps(evt.data)}\n\n"
            await asyncio.sleep(
                0.1
            )  # Without this, the client does not receive the event

            # Step 4: Execute search and stream final results
            search_results = await engine.execute_search(search_data)
            response = SearchResponse(
                original_query=raw_query,
                raw_structured_data=raw_structured_data,
                results=search_results,
                total_results=len(search_results),
            )

            # Store statistics
            try:
                stat = Statistics(
                    search_query=raw_query,
                    structured_data=raw_structured_data,
                    results=[result.model_dump() for result in search_results],
                    execution_time_ms=0,  # Optionally measure and store real execution time
                    is_modified=False,
                )
                StatisticsRepository.insert(stat)
            except Exception as e:
                logger.error(f"Failed to store statistics: {e}")

            evt = StreamEvent(event="results", data=response.model_dump())
            yield f"event: {evt.event}\ndata: {json.dumps(evt.data)}\n\n"
            await asyncio.sleep(
                0.1
            )  # Without this, the client does not receive the event

        except asyncio.CancelledError:
            logger.info(f"Search stream {connection_id} cancelled by client")
            return
        except Exception as e:
            logger.error(f"Error in streaming search {connection_id}: {e}")
            evt = StreamEvent(
                event="error", data={"message": f"Search failed: {str(e)}"}
            )
            yield f"event: {evt.event}\ndata: {json.dumps(evt.data)}\n\n"
            # Small delay to ensure error message is sent
            await asyncio.sleep(0.1)
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
async def search_with_structured_data(request: StructuredSearchRequest):
    """
    Search endpoint that accepts structured search data directly, bypassing LLM analysis.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        connection_id = id(asyncio.current_task())
        logger.info(
            f"Starting structured search stream {connection_id} for data: {request.structured_data}, original query: '{request.original_query}'"
        )

        try:
            # Step 1: Start database query (no LLM analysis needed)
            evt = StreamEvent(
                event="database_query_started",
                data={"message": "Start querying database"},
            )
            yield f"event: {evt.event}\ndata: {json.dumps(evt.data)}\n\n"
            await asyncio.sleep(0.1)

            engine = get_search_engine()

            structured_data = copy.deepcopy(request.structured_data)

            # Step 2: Execute search directly with structured data
            search_results = await engine.execute_search(request.structured_data)
            response = SearchResponse(
                original_query=request.original_query,
                raw_structured_data=structured_data,
                results=search_results,
                total_results=len(search_results),
            )

            # Store statistics
            try:
                stat = Statistics(
                    search_query=request.original_query,
                    structured_data=structured_data,
                    results=[result.model_dump() for result in search_results],
                    execution_time_ms=0,
                    is_modified=True,  # Mark as modified since user provided structured data
                )
                StatisticsRepository.insert(stat)
            except Exception as e:
                logger.error(f"Failed to store statistics: {e}")

            evt = StreamEvent(event="results", data=response.model_dump())
            yield f"event: {evt.event}\ndata: {json.dumps(evt.data)}\n\n"
            await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"Structured search stream {connection_id} cancelled by client")
            return
        except Exception as e:
            logger.error(f"Error in structured search stream {connection_id}: {e}")
            evt = StreamEvent(
                event="error", data={"message": f"Search failed: {str(e)}"}
            )
            yield f"event: {evt.event}\ndata: {json.dumps(evt.data)}\n\n"
            await asyncio.sleep(0.1)
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


@router.get("/document/{doi:path}")
async def get_document_details(
    doi: str = Path(..., min_length=1, description="Document DOI (cannot be empty)")
):
    """
    Get detailed document information by DOI.
    Returns: id, doi, title, text, summary, raw, facility_name
    """
    try:
        logger.info(f"Fetching document details for DOI: {doi}")
        document = DocumentRepository.get_by_doi(doi)
        if not document:
            raise HTTPException(
                status_code=404, detail=f"Document with DOI '{doi}' not found"
            )
        logger.info(f"Successfully fetched document details for DOI: {doi}")
        return document.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document details for DOI {doi}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch document details: {str(e)}"
        )
