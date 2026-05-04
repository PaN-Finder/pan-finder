"""
Unit tests for the Scoring class.
"""

import sys
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

server_path = Path(__file__).resolve().parents[4]
if str(server_path) not in sys.path:
    sys.path.insert(0, str(server_path))

with patch("src.config.get_settings") as mock_get_settings:
    _mock_settings = MagicMock(
        enable_turnstile=False,
        turnstile_secret_key=None,
        rrf_k_document=6,
        rrf_k_chunk=6,
        rrf_k_conditions_full=6,
        rrf_k_conditions_partial=6,
        rrf_k_keywords=10,
    )
    mock_get_settings.return_value = _mock_settings

    from src.core.engine.scoring import Scoring
    from src.core.search_query_builder import SubqueriesUsed
    from src.db.models.search import EnhancedSearchResult


RRF_K = {
    "document": _mock_settings.rrf_k_document,
    "chunk": _mock_settings.rrf_k_chunk,
    "conditions_full": _mock_settings.rrf_k_conditions_full,
    "conditions_partial": _mock_settings.rrf_k_conditions_partial,
    "keywords": _mock_settings.rrf_k_keywords,
}

MAX = {key: 1 / (1 + value) for key, value in RRF_K.items()}


def _all_false() -> SubqueriesUsed:
    return {
        "document": False,
        "chunk": False,
        "conditions_full": False,
        "conditions_partial": False,
        "keywords": False,
    }


def _subqueries_used(**overrides: bool) -> SubqueriesUsed:
    return cast(SubqueriesUsed, {**_all_false(), **overrides})


def _make_result(**kwargs) -> EnhancedSearchResult:
    defaults = {
        "doi": "10.0/test",
        "title": "Test",
        "facility_name": "Test",
        "abstract": "Test",
        "overall_score": 0.0,
        "document_score": 0.0,
        "chunk_score": 0.0,
        "conditions_full_score": 0.0,
        "conditions_partial_score": 0.0,
        "keywords_score": 0.0,
    }
    defaults.update(kwargs)
    return EnhancedSearchResult(**defaults)


def test_overall_score_max_all_false():
    assert Scoring.overall_score_max(_all_false()) == 0.0


def test_overall_score_max_similarity_only():
    subqueries_used = _subqueries_used(document=True, chunk=True)
    expected = MAX["document"] + MAX["chunk"]
    assert Scoring.overall_score_max(subqueries_used) == pytest.approx(expected)


def test_overall_score_max_keyword_only():
    subqueries_used = _subqueries_used(keywords=True)
    assert Scoring.overall_score_max(subqueries_used) == pytest.approx(MAX["keywords"])


def test_overall_score_max_filter_only():
    subqueries_used = _subqueries_used(conditions_full=True, conditions_partial=True)
    expected = MAX["conditions_full"] + MAX["conditions_partial"]
    assert Scoring.overall_score_max(subqueries_used) == pytest.approx(expected)


def test_overall_score_max_all_true():
    subqueries_used = cast(
        SubqueriesUsed,
        {
            "document": True,
            "chunk": True,
            "conditions_full": True,
            "conditions_partial": True,
            "keywords": True,
        },
    )
    assert Scoring.overall_score_max(subqueries_used) == pytest.approx(
        sum(MAX.values())
    )


def test_components_enabled_mirrors_subqueries_used():
    subqueries_used = _subqueries_used(document=True, keywords=True)
    assert Scoring.components_enabled(subqueries_used) == dict(subqueries_used)


def test_normalize_scores_empty_list():
    Scoring.normalize_scores([], _all_false())


def test_normalize_scores_all_false_zeros_everything():
    result = _make_result(
        overall_score=0.5,
        document_score=0.1,
        chunk_score=0.1,
        keywords_score=0.1,
        conditions_full_score=0.1,
        conditions_partial_score=0.1,
    )
    Scoring.normalize_scores([result], _all_false())
    assert result.document_score == 0.0
    assert result.chunk_score == 0.0
    assert result.keywords_score == 0.0
    assert result.conditions_full_score == 0.0
    assert result.conditions_partial_score == 0.0
    assert result.overall_score == 0.0


def test_normalize_scores_similarity_only():
    subqueries_used = _subqueries_used(document=True, chunk=True)
    raw_document = MAX["document"]
    raw_chunk = MAX["chunk"] / 2
    overall_raw = raw_document + raw_chunk
    overall_max = MAX["document"] + MAX["chunk"]

    result = _make_result(
        overall_score=overall_raw,
        document_score=raw_document,
        chunk_score=raw_chunk,
    )
    Scoring.normalize_scores([result], subqueries_used)

    assert result.document_score == pytest.approx(1.0)
    assert result.chunk_score == pytest.approx(0.5)
    assert result.keywords_score == 0.0
    assert result.conditions_full_score == 0.0
    assert result.conditions_partial_score == 0.0
    assert result.overall_score == pytest.approx(overall_raw / overall_max)


def test_normalize_scores_filter_only():
    subqueries_used = _subqueries_used(conditions_full=True, conditions_partial=True)
    raw_full = MAX["conditions_full"]
    raw_partial = MAX["conditions_partial"] / 2

    result = _make_result(
        overall_score=raw_full + raw_partial,
        conditions_full_score=raw_full,
        conditions_partial_score=raw_partial,
        keywords_score=0.9,
    )
    Scoring.normalize_scores([result], subqueries_used)

    assert result.conditions_full_score == pytest.approx(1.0)
    assert result.conditions_partial_score == pytest.approx(0.5)
    assert result.keywords_score == 0.0


def test_normalize_scores_keyword_only():
    subqueries_used = _subqueries_used(keywords=True)
    raw_keyword = MAX["keywords"] / 2

    result = _make_result(
        overall_score=raw_keyword,
        keywords_score=raw_keyword,
        document_score=0.5,
        conditions_full_score=0.5,
    )
    Scoring.normalize_scores([result], subqueries_used)

    assert result.keywords_score == pytest.approx(0.5)
    assert result.document_score == 0.0
    assert result.conditions_full_score == 0.0
    assert result.overall_score == pytest.approx(0.5)
