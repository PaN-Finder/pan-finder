import json
from fastapi import APIRouter
import asyncio
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import AsyncGenerator

from ..engine import SearchResponse, get_search_engine
from ..logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/search")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query (cannot be empty)")


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
            search_data = await engine.extract_structured_query(raw_query)

            evt = StreamEvent(
                event="analysis_completed",
                data={"message": "Analysis completed", "structured_query": search_data},
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
                structured_query=search_data,
                results=search_results,
                total_results=len(search_results),
            )
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
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type, Cache-Control",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for real-time streaming
        },
    )
