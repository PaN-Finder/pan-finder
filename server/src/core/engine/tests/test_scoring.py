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
        rrf_k_similarity=6,
        rrf_k_chunk=6,
        rrf_k_full_match=6,
        rrf_k_partial_match=6,
        rrf_k_keyword=10,
    )
    mock_get_settings.return_value = _mock_settings

    from src.core.engine.scoring import Scoring
    from src.core.search_query_builder import SubqueriesUsed
    from src.db.models.search import EnhancedSearchResult


RRF_K = {
    "similarity": _mock_settings.rrf_k_similarity,
    "chunk_similarity": _mock_settings.rrf_k_chunk,
    "full_match": _mock_settings.rrf_k_full_match,
    "partial_match": _mock_settings.rrf_k_partial_match,
    "keyword": _mock_settings.rrf_k_keyword,
}

MAX = {key: 1 / (1 + value) for key, value in RRF_K.items()}


def _all_false() -> SubqueriesUsed:
    return {
        "similarity": False,
        "chunk_similarity": False,
        "full_match": False,
        "partial_match": False,
        "keyword": False,
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
        "similarity_score": 0.0,
        "chunk_similarity_score": 0.0,
        "full_match_score": 0.0,
        "partial_match_score": 0.0,
        "keyword_score": 0.0,
    }
    defaults.update(kwargs)
    return EnhancedSearchResult(**defaults)


def test_overall_score_max_all_false():
    assert Scoring.overall_score_max(_all_false()) == 0.0


def test_overall_score_max_similarity_only():
    subqueries_used = _subqueries_used(similarity=True, chunk_similarity=True)
    expected = MAX["similarity"] + MAX["chunk_similarity"]
    assert Scoring.overall_score_max(subqueries_used) == pytest.approx(expected)


def test_overall_score_max_keyword_only():
    subqueries_used = _subqueries_used(keyword=True)
    assert Scoring.overall_score_max(subqueries_used) == pytest.approx(MAX["keyword"])


def test_overall_score_max_filter_only():
    subqueries_used = _subqueries_used(full_match=True, partial_match=True)
    expected = MAX["full_match"] + MAX["partial_match"]
    assert Scoring.overall_score_max(subqueries_used) == pytest.approx(expected)


def test_overall_score_max_all_true():
    subqueries_used = cast(
        SubqueriesUsed,
        {
            "similarity": True,
            "chunk_similarity": True,
            "full_match": True,
            "partial_match": True,
            "keyword": True,
        },
    )
    assert Scoring.overall_score_max(subqueries_used) == pytest.approx(
        sum(MAX.values())
    )


def test_components_enabled_mirrors_subqueries_used():
    subqueries_used = _subqueries_used(similarity=True, keyword=True)
    assert Scoring.components_enabled(subqueries_used) == dict(subqueries_used)


def test_normalize_scores_empty_list():
    Scoring.normalize_scores([], _all_false())


def test_normalize_scores_all_false_zeros_everything():
    result = _make_result(
        overall_score=0.5,
        similarity_score=0.1,
        chunk_similarity_score=0.1,
        keyword_score=0.1,
        full_match_score=0.1,
        partial_match_score=0.1,
    )
    Scoring.normalize_scores([result], _all_false())
    assert result.similarity_score == 0.0
    assert result.chunk_similarity_score == 0.0
    assert result.keyword_score == 0.0
    assert result.full_match_score == 0.0
    assert result.partial_match_score == 0.0
    assert result.overall_score == 0.0


def test_normalize_scores_similarity_only():
    subqueries_used = _subqueries_used(similarity=True, chunk_similarity=True)
    raw_similarity = MAX["similarity"]
    raw_chunk = MAX["chunk_similarity"] / 2
    overall_raw = raw_similarity + raw_chunk
    overall_max = MAX["similarity"] + MAX["chunk_similarity"]

    result = _make_result(
        overall_score=overall_raw,
        similarity_score=raw_similarity,
        chunk_similarity_score=raw_chunk,
    )
    Scoring.normalize_scores([result], subqueries_used)

    assert result.similarity_score == pytest.approx(1.0)
    assert result.chunk_similarity_score == pytest.approx(0.5)
    assert result.keyword_score == 0.0
    assert result.full_match_score == 0.0
    assert result.partial_match_score == 0.0
    assert result.overall_score == pytest.approx(overall_raw / overall_max)


def test_normalize_scores_filter_only():
    subqueries_used = _subqueries_used(full_match=True, partial_match=True)
    raw_full = MAX["full_match"]
    raw_partial = MAX["partial_match"] / 2

    result = _make_result(
        overall_score=raw_full + raw_partial,
        full_match_score=raw_full,
        partial_match_score=raw_partial,
        keyword_score=0.9,
    )
    Scoring.normalize_scores([result], subqueries_used)

    assert result.full_match_score == pytest.approx(1.0)
    assert result.partial_match_score == pytest.approx(0.5)
    assert result.keyword_score == 0.0


def test_normalize_scores_keyword_only():
    subqueries_used = _subqueries_used(keyword=True)
    raw_keyword = MAX["keyword"] / 2

    result = _make_result(
        overall_score=raw_keyword,
        keyword_score=raw_keyword,
        similarity_score=0.5,
        full_match_score=0.5,
    )
    Scoring.normalize_scores([result], subqueries_used)

    assert result.keyword_score == pytest.approx(0.5)
    assert result.similarity_score == 0.0
    assert result.full_match_score == 0.0
    assert result.overall_score == pytest.approx(0.5)
