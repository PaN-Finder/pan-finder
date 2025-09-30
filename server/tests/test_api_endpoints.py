import datetime
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from httpx import AsyncClient, ASGITransport
import pytest_asyncio

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.models.search import EnhancedSearchResult, StructuredQueryData
from helpers.mock_settings import (
    MockSettings,
    create_common_patches,
    reload_app_modules_with_settings,
)


# Create mock settings with Turnstile disabled for API endpoint tests
mock_settings = MockSettings(enable_turnstile=False)

# Start all common patches
patches = create_common_patches(mock_settings)


# ----------------------------
# Async test client fixture
# ----------------------------
@pytest_asyncio.fixture
async def async_client():
    # Reload app modules with mock settings (reload routers so verify_session sees disabled Turnstile)
    server_module = reload_app_modules_with_settings(mock_settings, reload_routers=True)

    async with AsyncClient(
        transport=ASGITransport(app=server_module.app), base_url="http://localhost"
    ) as ac:
        yield ac


# ----------------------------
# Test cases
# ----------------------------
@pytest.mark.asyncio
async def test_health_endpoint_success(async_client: AsyncClient):
    response = await async_client.get("/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "healthy"
    assert payload["database"] == "healthy"
    assert "version" in payload


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    response = await async_client.get("/")

    assert response.status_code == 200
    payload = response.json()

    assert payload["message"] == "Welcome to Pan-Finder API"
    assert "version" in payload


# ----------------------------
# Document endpoint tests
# ----------------------------
@pytest.mark.asyncio
async def test_document_details_found(async_client: AsyncClient):
    mock_document = MagicMock()
    mock_document.to_dict.return_value = {"id": "doc1", "doi": "10.1000/test"}

    with patch(
        "src.routers.document.DocumentRepository.get_by_doi",
        return_value=mock_document,
    ) as mock_repo:
        response = await async_client.get("/document/10.1000/test")

    assert response.status_code == 200
    assert response.json() == {"id": "doc1", "doi": "10.1000/test"}
    mock_repo.assert_called_once_with("10.1000/test")


# ----------------------------
# Feedback endpoints
# ----------------------------
def make_statistic_with_results(doi_list):
    class DummyResult:
        def __init__(self, doi):
            self.doi = doi

        def model_dump(self):
            return {"doi": self.doi}

    class DummyResults:
        def __init__(self, dois):
            self.relevant = [DummyResult(d) for d in dois]
            self.weakly_relevant = []

    class DummyStatistic:
        def __init__(self, dois):
            self.results = DummyResults(dois)

    return DummyStatistic(doi_list)


@pytest.mark.asyncio
async def test_feedback_submit_success(async_client: AsyncClient):
    statistic = make_statistic_with_results(["10.1000/xyz123"])
    feedback_obj = MagicMock()
    feedback_obj.to_dict.return_value = {
        "id": "fb1",
        "statistic_id": "stat1",
        "feedback_type": "positive",
        "metadata": {"doi": "10.1000/xyz123"},
        "created_at": str(datetime.datetime.now()),
    }

    with (
        patch(
            "src.routers.feedback.StatisticRepository.select_by_id",
            return_value=statistic,
        ),
        patch(
            "src.routers.feedback.FeedbackRepository.select_by_statistic_id_and_metadata",
            return_value=None,
        ),
        patch("src.routers.feedback.FeedbackRepository.insert", return_value="fb1"),
        patch("src.routers.feedback.Feedback", return_value=feedback_obj),
    ):
        response = await async_client.post(
            "/feedback/submit",
            json={
                "statistic_id": "stat1",
                "feedback_type": "positive",
                "doi": "10.1000/xyz123",
            },
        )
    assert response.status_code == 200
    assert response.json()["id"] == "fb1"
    assert response.json()["feedback_type"] == "positive"


# ----------------------------
# Search endpoints
# ----------------------------


class _DummySQL:
    def as_string(self) -> str:
        return "SELECT 1"


@pytest.mark.asyncio
async def test_search_endpoint_logic():
    """Test search endpoint logic directly without HTTP streaming complexity."""
    from src.routers.search import SearchRequest

    structured = StructuredQueryData(
        intention="find graphene",
        keywords=["graphene"],
        filters={},
    )
    results = [
        EnhancedSearchResult(
            doi="10.1000/abc",
            title="Graphene Study",
            facility_name="Facility A",
            summary="A summary",
            overall_score=0.9,
            similarity_score=0.8,
            chunk_similarity_score=0.7,
            full_match_score=0.6,
            partial_match_score=0.5,
            keyword_score=0.4,
        )
    ]

    class DummyEngine:
        async def parse_query_to_structured_data(self, raw_query):
            return structured

        async def execute_search(self, data):
            return results, _DummySQL(), None

        async def explain_search_results(
            self, raw_query, relevant_results, search_data
        ):
            yield "Explanation chunk"

    async def immediate_sleep(*_args, **_kwargs):
        return None

    with (
        patch("src.routers.search.verify_session", return_value=None),
        patch("src.routers.search.get_search_engine", return_value=DummyEngine()),
        patch(
            "src.routers.search.StatisticRepository.insert", return_value="stat-123"
        ) as mock_insert,
        patch("src.routers.search.asyncio.sleep", new=immediate_sleep),
        patch("src.routers.search.asyncio.current_task", return_value=MagicMock()),
    ):
        # Import the endpoint function directly
        from src.routers.search import search_with_ai_stream

        request = SearchRequest(query="graphene")
        streaming_response = await search_with_ai_stream(request, x_session_id=None)

        # Verify we get a StreamingResponse
        from fastapi.responses import StreamingResponse

        assert isinstance(streaming_response, StreamingResponse)
        assert streaming_response.media_type == "text/event-stream"

        # Consume the generator to trigger the logic
        events_collected = []

        async for chunk in streaming_response.body_iterator:
            # Decode bytes to string
            chunk_str = chunk.decode() if isinstance(chunk, bytes) else chunk
            events_collected.append(chunk_str)
            # Stop after we've collected enough events to trigger insert
            if (
                len(events_collected) >= 5
            ):  # Should cover analysis, data_fetching, results
                break

        # Check SSE events
        assert events_collected[0].startswith("event: analysis_started")
        assert events_collected[1].startswith("event: analysis_completed")
        assert events_collected[2].startswith("event: data_fetching")
        assert events_collected[3].startswith("event: results")
        assert events_collected[4].startswith("event: explanation_started")

        # Parse the results event to verify the data
        results_line = events_collected[3].split("\n")[1]  # Get the data line
        results_data = json.loads(
            results_line.split(": ", 1)[1]
        )  # Get JSON after "data: "
        assert results_data["id"] == "stat-123"
        assert results_data["raw_structured_data"] == structured.model_dump()
        assert results_data["relevant_results"][0]["doi"] == "10.1000/abc"
        assert results_data["weakly_relevant_results"] == []
        assert results_data["total_results"] == 1

        # Verify the core logic was executed
        mock_insert.assert_called_once()
