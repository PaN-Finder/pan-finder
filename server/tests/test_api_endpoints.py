import datetime
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers.mock_settings import (
    MockSettings,
    create_common_patches,
    reload_app_modules_with_settings,
)

from src.db.models.document_repository import DocumentRepository
from src.db.models.search import EnhancedSearchResult, StructuredQueryData

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
    doc = {
        "id": 1,
        "doi": "10.1000/test",
        "title": "Test Doc",
        "abstract": "Some text",
        "facility_name": "Facility A",
        "publication_year": "2024",
        "instrument_name": "Instrument A",
        "authors": "Ada Lovelace",
    }
    mock_document = MagicMock()
    mock_document.to_dict.return_value = doc

    with patch(
        "src.routers.document.DocumentRepository.get_by_doi",
        return_value=mock_document,
    ) as mock_repo:
        response = await async_client.get("/document/10.1000/test")

    assert response.status_code == 200
    assert response.json() == doc
    mock_repo.assert_called_once_with("10.1000/test")


def test_document_repository_get_by_doi_loads_mapped_detail_fields():
    document_cursor = MagicMock()
    document_cursor.fetchone.return_value = (
        1,
        "10.1000/test",
        "Test Doc",
        "Some text",
        None,
        None,
        1,
        "Facility A",
    )
    document_cursor.description = [
        ("id",),
        ("doi",),
        ("title",),
        ("abstract",),
        ("summary",),
        ("raw",),
        ("facility_id",),
        ("facility_name",),
    ]

    detail_cursor = MagicMock()
    detail_cursor.fetchall.return_value = [
        ("instruments.name", "Instrument A"),
        ("publicationYear", "2024"),
        ("authors.name", "Ada Lovelace"),
    ]

    conn = MagicMock()
    conn.execute.side_effect = [document_cursor, detail_cursor]

    context_manager = MagicMock()
    context_manager.__enter__.return_value = conn
    context_manager.__exit__.return_value = None

    with patch(
        "src.db.models.document_repository.get_database_connection",
        return_value=context_manager,
    ):
        document = DocumentRepository.get_by_doi("10.1000/test")

    assert document.instrument_name == "Instrument A"
    assert document.publication_year == "2024"
    assert document.authors == "Ada Lovelace"
    assert document.facility_name == "Facility A"
    assert conn.execute.call_args_list[1].args[1] == [
        1,
        ["instruments.name", "publicationYear", "authors.name"],
        ["instruments.name", "publicationYear", "authors.name"],
    ]


def test_document_repository_get_by_doi_deduplicates_combined_and_individual_author_rows():
    """When the DB contains both a combined comma-separated row and individual rows
    for the same authors (a known ingestor artifact), the result must only list each
    name once."""
    document_cursor = MagicMock()
    document_cursor.fetchone.return_value = (
        5,
        "10.1000/test-combined",
        "Test Doc Combined",
        "Some text",
        None,
        None,
        2,
        "Facility B",
    )
    document_cursor.description = [
        ("id",),
        ("doi",),
        ("title",),
        ("abstract",),
        ("summary",),
        ("raw",),
        ("facility_id",),
        ("facility_name",),
    ]

    detail_cursor = MagicMock()
    # Combined row comes first (lower id), then individual rows
    detail_cursor.fetchall.return_value = [
        (
            "creator",
            "Else Marie Friis, Peter R. Crane, Kaj Raunsgaard Pedersen, Federica Marone",
        ),
        ("creator", "Else Marie Friis"),
        ("creator", "Peter R. Crane"),
        ("creator", "Kaj Raunsgaard Pedersen"),
        ("creator", "Federica Marone"),
    ]

    conn = MagicMock()
    conn.execute.side_effect = [document_cursor, detail_cursor]

    context_manager = MagicMock()
    context_manager.__enter__.return_value = conn
    context_manager.__exit__.return_value = None

    with patch(
        "src.db.models.document_repository.get_database_connection",
        return_value=context_manager,
    ):
        document = DocumentRepository.get_by_doi("10.1000/test-combined")

    assert (
        document.authors
        == "Else Marie Friis - Peter R. Crane - Kaj Raunsgaard Pedersen - Federica Marone"
    )


def test_document_repository_get_by_doi_deduplicates_multi_row_author_values():
    document_cursor = MagicMock()
    document_cursor.fetchone.return_value = (
        2,
        "10.1000/test-creator",
        "Test Doc Creator",
        "Some text",
        None,
        None,
        2,
        "Facility B",
    )
    document_cursor.description = [
        ("id",),
        ("doi",),
        ("title",),
        ("abstract",),
        ("summary",),
        ("raw",),
        ("facility_id",),
        ("facility_name",),
    ]

    detail_cursor = MagicMock()
    detail_cursor.fetchall.return_value = [
        ("creationLocation", "Instrument B"),
        ("publicationYear", "2023"),
        ("creator", "Ada Lovelace"),
        ("creator", "Alan Turing"),
        ("authors", "Ada Lovelace"),
        ("authors", " alan turing "),
    ]

    conn = MagicMock()
    conn.execute.side_effect = [document_cursor, detail_cursor]

    context_manager = MagicMock()
    context_manager.__enter__.return_value = conn
    context_manager.__exit__.return_value = None

    with patch(
        "src.db.models.document_repository.get_database_connection",
        return_value=context_manager,
    ):
        document = DocumentRepository.get_by_doi("10.1000/test-creator")

    assert document.instrument_name == "Instrument B"
    assert document.publication_year == "2023"
    assert document.authors == "Ada Lovelace - Alan Turing"


def test_document_repository_get_by_doi_deduplicates_multi_row_instrument_values():
    document_cursor = MagicMock()
    document_cursor.fetchone.return_value = (
        3,
        "10.1000/test-instrument",
        "Test Doc Instrument",
        "Some text",
        None,
        None,
        5,
        "Facility C",
    )
    document_cursor.description = [
        ("id",),
        ("doi",),
        ("title",),
        ("abstract",),
        ("summary",),
        ("raw",),
        ("facility_id",),
        ("facility_name",),
    ]

    detail_cursor = MagicMock()
    detail_cursor.fetchall.return_value = [
        ("beamline", "ID01"),
        ("beamline", "ID02"),
        ("beamline", " id01 "),
        ("publicationYear", "2022"),
    ]

    conn = MagicMock()
    conn.execute.side_effect = [document_cursor, detail_cursor]

    context_manager = MagicMock()
    context_manager.__enter__.return_value = conn
    context_manager.__exit__.return_value = None

    with patch(
        "src.db.models.document_repository.get_database_connection",
        return_value=context_manager,
    ):
        document = DocumentRepository.get_by_doi("10.1000/test-instrument")

    assert document.instrument_name == "ID01 - ID02"
    assert document.publication_year == "2022"
    assert document.authors is None


def test_document_repository_get_by_doi_loads_publication_year_for_mapped_facility():
    document_cursor = MagicMock()
    document_cursor.fetchone.return_value = (
        4,
        "10.1000/test-year",
        "Test Doc Year",
        "Some text",
        None,
        None,
        2,
        "Facility D",
    )
    document_cursor.description = [
        ("id",),
        ("doi",),
        ("title",),
        ("abstract",),
        ("summary",),
        ("raw",),
        ("facility_id",),
        ("facility_name",),
    ]

    detail_cursor = MagicMock()
    detail_cursor.fetchall.return_value = [
        ("publicationYear", "2021"),
    ]

    conn = MagicMock()
    conn.execute.side_effect = [document_cursor, detail_cursor]

    context_manager = MagicMock()
    context_manager.__enter__.return_value = conn
    context_manager.__exit__.return_value = None

    with patch(
        "src.db.models.document_repository.get_database_connection",
        return_value=context_manager,
    ):
        document = DocumentRepository.get_by_doi("10.1000/test-year")

    assert document.instrument_name is None
    assert document.publication_year == "2021"
    assert document.authors is None


def test_document_repository_get_by_doi_returns_no_optional_fields_for_unmapped_facility():
    document_cursor = MagicMock()
    document_cursor.fetchone.return_value = (
        2,
        "10.1000/test-2",
        "Test Doc 2",
        "Some text",
        None,
        None,
        99,
        "Facility B",
    )
    document_cursor.description = [
        ("id",),
        ("doi",),
        ("title",),
        ("abstract",),
        ("summary",),
        ("raw",),
        ("facility_id",),
        ("facility_name",),
    ]

    conn = MagicMock()
    conn.execute.return_value = document_cursor

    context_manager = MagicMock()
    context_manager.__enter__.return_value = conn
    context_manager.__exit__.return_value = None

    with patch(
        "src.db.models.document_repository.get_database_connection",
        return_value=context_manager,
    ):
        document = DocumentRepository.get_by_doi("10.1000/test-2")

    assert document.instrument_name is None
    assert document.publication_year is None
    assert document.authors is None
    assert conn.execute.call_count == 1


@pytest.mark.asyncio
async def test_get_raw_document_parsed(async_client: AsyncClient):
    # raw contains valid JSON -> endpoint should return parsed JSON
    mock_document = MagicMock()
    mock_document.raw = '{"foo": "bar", "num": 1}'

    with patch(
        "src.routers.document.DocumentRepository.get_by_doi",
        return_value=mock_document,
    ) as mock_repo:
        # When `/raw` route is declared before the catch-all details route, use an unencoded DOI
        response = await async_client.get("/document/raw/10.1000/test")

    assert response.status_code == 200
    assert response.json() == {"foo": "bar", "num": 1}
    mock_repo.assert_called_once_with("10.1000/test")


@pytest.mark.asyncio
async def test_get_raw_document_returns_raw_string_when_not_json(
    async_client: AsyncClient,
):
    # raw is not valid JSON -> endpoint should return the raw string (JSON string encoded)
    raw_text = "not a json blob"
    mock_document = MagicMock()
    mock_document.raw = raw_text

    with patch(
        "src.routers.document.DocumentRepository.get_by_doi",
        return_value=mock_document,
    ) as mock_repo:
        # Use unencoded DOI path now that `/raw` is the more specific route
        response = await async_client.get("/document/raw/10.1000/test")

    assert response.status_code == 200
    # FastAPI will return a JSON string for a returned Python str, so response.json() yields the original string
    assert response.json() == raw_text
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
@pytest.mark.parametrize(
    "classification", ["Match", "Relevant", "Suggested", "Not_Relevant"]
)
async def test_feedback_submit_success(async_client: AsyncClient, classification: str):
    statistic = make_statistic_with_results(["10.1000/xyz123"])
    feedback_obj = MagicMock()
    feedback_obj.to_dict.return_value = {
        "id": "fb1",
        "statistic_id": "stat1",
        "feedback_type": classification,
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
                "feedback_type": classification,
                "doi": "10.1000/xyz123",
            },
        )
    assert response.status_code == 200
    assert response.json()["id"] == "fb1"
    assert response.json()["feedback_type"] == classification


@pytest.mark.asyncio
async def test_feedback_submit_invalid_value_rejected(async_client: AsyncClient):
    response = await async_client.post(
        "/feedback/submit",
        json={
            "statistic_id": "stat1",
            "feedback_type": "positive",
            "doi": "10.1000/xyz123",
        },
    )
    assert response.status_code == 422


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
            abstract="An abstract about graphene.",
            overall_score=0.9,
            document_score=0.8,
            chunk_score=0.7,
            conditions_full_score=0.6,
            conditions_partial_score=0.5,
            keywords_score=0.4,
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
