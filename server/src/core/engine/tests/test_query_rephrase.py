"""Unit tests for SearchEngine query rephrasing."""

import sys
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

server_path = Path(__file__).resolve().parents[4]
if str(server_path) not in sys.path:
    sys.path.insert(0, str(server_path))

with patch("src.config.get_settings") as mock_get_settings:
    mock_get_settings.return_value = MagicMock(
        enable_turnstile=False,
        turnstile_secret_key=None,
        embedding_model_path="unused",
        rrf_k_document=6,
        rrf_k_chunk=6,
        rrf_k_conditions_full=6,
        rrf_k_conditions_partial=6,
        rrf_k_keywords=10,
        value_vector_keys=(),
    )
    from src.core.engine import engine as engine_module

    SearchEngine = engine_module.SearchEngine


@pytest.mark.asyncio
async def test_rephrase_query_for_search_uses_llm_response():
    llm_client = MagicMock()
    llm_client.create_request.return_value = {"request": "value"}
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content="Retrieve all organ records associated with donor ID LADAF-2021-17."
        )
    )

    with patch.object(
        engine_module.settings,
        "rephrase_model_name",
        "gpt-5.4-mini",
    ):
        engine = SearchEngine(llm_client=llm_client)

        rewritten = await engine.rephrase_query_for_search(
            "Show me all organs from donor LADAF-2021-17"
        )

    assert (
        rewritten
        == "Retrieve all organ records associated with donor ID LADAF-2021-17."
    )
    llm_client.create_request.assert_called_once_with(
        messages=[
            ANY,
            ANY,
        ],
        model="gpt-5.4-mini",
        max_tokens=200,
        temperature=0.0,
    )
    llm_client.complete.assert_called_once_with({"request": "value"})


@pytest.mark.asyncio
async def test_rephrase_query_for_search_falls_back_on_empty_response():
    llm_client = MagicMock()
    llm_client.create_request.return_value = {"request": "value"}
    llm_client.complete = AsyncMock(return_value=MagicMock(content="   "))

    engine = SearchEngine(llm_client=llm_client)

    original_query = "Show me all organs from donor LADAF-2021-17"
    rewritten = await engine.rephrase_query_for_search(original_query)

    assert rewritten == original_query


@pytest.mark.asyncio
async def test_rephrase_query_for_search_falls_back_on_llm_error():
    llm_client = MagicMock()
    llm_client.create_request.return_value = {"request": "value"}
    llm_client.complete = AsyncMock(side_effect=RuntimeError("boom"))

    engine = SearchEngine(llm_client=llm_client)

    original_query = "Show me all organs from donor LADAF-2021-17"
    rewritten = await engine.rephrase_query_for_search(original_query)

    assert rewritten == original_query
