"""
Unit tests for the Scoring class.
"""

import sys
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

# Add the server directory to Python path so we can import from src.
server_path = Path(__file__).resolve().parents[4]
if str(server_path) not in sys.path:
    sys.path.insert(0, str(server_path))

# ---------------------------------------------------------------------------
# Mock get_settings so importing src.core.* does not require environment config.
# ---------------------------------------------------------------------------
with patch("src.config.get_settings") as mock_get_settings:
    _mock_settings = MagicMock(
        enable_turnstile=False,
        turnstile_secret_key=None,
        rrf_k_similarity=6,
        rrf_k_chunk=6,
        rrf_k_full_match=6,
        rrf_k_partial_match=6,
        rrf_k_keyword=10,
        rrf_k_value_vector=6,
    )
    mock_get_settings.return_value = _mock_settings

    from src.core.engine.scoring import Scoring
    from src.core.search_query_builder import SubqueriesUsed
    from src.db.models.search import EnhancedSearchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RRF_K = {
    "similarity": _mock_settings.rrf_k_similarity,
    "chunk_similarity": _mock_settings.rrf_k_chunk,
    "full_match": _mock_settings.rrf_k_full_match,
    "partial_match": _mock_settings.rrf_k_partial_match,
    "keyword": _mock_settings.rrf_k_keyword,
    "value_vector": _mock_settings.rrf_k_value_vector,
}

MAX = {k: 1 / (1 + v) for k, v in RRF_K.items()}


def _all_false() -> SubqueriesUsed:
    return {
        "similarity": False,
        "chunk_similarity": False,
        "full_match": False,
        "partial_match": False,
        "keyword": False,
        "value_vector": False,
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
        "value_vector_score": 0.0,
    }
    defaults.update(kwargs)
    return EnhancedSearchResult(**defaults)


# ---------------------------------------------------------------------------
# Tests: overall_score_max
# ---------------------------------------------------------------------------


def test_overall_score_max_all_false():
    """All subqueries inactive → max score is 0."""
    assert Scoring.overall_score_max(_all_false()) == 0.0


def test_overall_score_max_similarity_only():
    su = _subqueries_used(similarity=True, chunk_similarity=True)
    expected = MAX["similarity"] + MAX["chunk_similarity"]
    assert Scoring.overall_score_max(su) == pytest.approx(expected)


def test_overall_score_max_keyword_only():
    su = _subqueries_used(keyword=True)
    assert Scoring.overall_score_max(su) == pytest.approx(MAX["keyword"])


def test_overall_score_max_filter_without_value_vector():
    """Filter active but value_vector inactive → value_vector max NOT counted."""
    su = _subqueries_used(full_match=True, partial_match=True)
    expected = MAX["full_match"] + MAX["partial_match"]
    assert Scoring.overall_score_max(su) == pytest.approx(expected)


def test_overall_score_max_value_vector_only():
    """value_vector can be active independently of filter flags."""
    su = _subqueries_used(value_vector=True)
    assert Scoring.overall_score_max(su) == pytest.approx(MAX["value_vector"])


def test_overall_score_max_all_true():
    su = cast(
        SubqueriesUsed,
        {
            "similarity": True,
            "chunk_similarity": True,
            "full_match": True,
            "partial_match": True,
            "keyword": True,
            "value_vector": True,
        },
    )
    expected = sum(MAX.values())
    assert Scoring.overall_score_max(su) == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Tests: components_enabled
# ---------------------------------------------------------------------------


def test_components_enabled_mirrors_subqueries_used():
    su = _subqueries_used(similarity=True, keyword=True)
    assert Scoring.components_enabled(su) == dict(su)


def test_components_enabled_all_false():
    su = _all_false()
    enabled = Scoring.components_enabled(su)
    assert all(not v for v in enabled.values())


# ---------------------------------------------------------------------------
# Tests: normalize_scores
# ---------------------------------------------------------------------------


def test_normalize_scores_empty_list():
    """Empty results list should not raise."""
    Scoring.normalize_scores([], _all_false())


def test_normalize_scores_all_false_zeros_everything():
    """With no active subqueries, all scores are zeroed."""
    result = _make_result(
        overall_score=0.5,
        similarity_score=0.1,
        chunk_similarity_score=0.1,
        keyword_score=0.1,
        full_match_score=0.1,
        partial_match_score=0.1,
        value_vector_score=0.1,
    )
    Scoring.normalize_scores([result], _all_false())
    assert result.similarity_score == 0.0
    assert result.chunk_similarity_score == 0.0
    assert result.keyword_score == 0.0
    assert result.full_match_score == 0.0
    assert result.partial_match_score == 0.0
    assert result.value_vector_score == 0.0
    assert result.overall_score == 0.0


def test_normalize_scores_similarity_only():
    """Similarity scores are normalized; others remain zeroed."""
    su = _subqueries_used(similarity=True, chunk_similarity=True)
    raw_sim = MAX["similarity"]  # at max value → normalized to 1.0
    raw_chunk = MAX["chunk_similarity"] / 2  # half max → normalized to 0.5
    overall_raw = raw_sim + raw_chunk
    overall_max = MAX["similarity"] + MAX["chunk_similarity"]

    result = _make_result(
        overall_score=overall_raw,
        similarity_score=raw_sim,
        chunk_similarity_score=raw_chunk,
    )
    Scoring.normalize_scores([result], su)

    assert result.similarity_score == pytest.approx(1.0)
    assert result.chunk_similarity_score == pytest.approx(0.5)
    assert result.keyword_score == 0.0
    assert result.full_match_score == 0.0
    assert result.partial_match_score == 0.0
    assert result.value_vector_score == 0.0
    assert result.overall_score == pytest.approx(overall_raw / overall_max)


def test_normalize_scores_filter_active_value_vector_inactive():
    """full_match/partial_match normalized; value_vector zeroed when not in subqueries."""
    su = _subqueries_used(full_match=True, partial_match=True)
    raw_full = MAX["full_match"]
    raw_partial = MAX["partial_match"] / 2
    raw_vv = 0.99  # Non-zero in raw data — must be zeroed

    result = _make_result(
        overall_score=raw_full + raw_partial,
        full_match_score=raw_full,
        partial_match_score=raw_partial,
        value_vector_score=raw_vv,
    )
    Scoring.normalize_scores([result], su)

    assert result.full_match_score == pytest.approx(1.0)
    assert result.partial_match_score == pytest.approx(0.5)
    assert result.value_vector_score == 0.0  # zeroed because value_vector=False


def test_normalize_scores_value_vector_active():
    """value_vector score is normalized when the flag is True."""
    su = _subqueries_used(value_vector=True)
    raw_vv = MAX["value_vector"]  # at max → normalized to 1.0

    result = _make_result(
        overall_score=raw_vv,
        value_vector_score=raw_vv,
    )
    Scoring.normalize_scores([result], su)

    assert result.value_vector_score == pytest.approx(1.0)
    assert result.overall_score == pytest.approx(1.0)


def test_normalize_scores_value_vector_active_filter_inactive():
    """value_vector normalized independently from filter flags."""
    su = _subqueries_used(value_vector=True)
    raw_vv = MAX["value_vector"] / 2

    result = _make_result(
        overall_score=raw_vv,
        value_vector_score=raw_vv,
        full_match_score=0.5,  # should be zeroed
        partial_match_score=0.5,  # should be zeroed
    )
    Scoring.normalize_scores([result], su)

    assert result.value_vector_score == pytest.approx(0.5)
    assert result.full_match_score == 0.0
    assert result.partial_match_score == 0.0
