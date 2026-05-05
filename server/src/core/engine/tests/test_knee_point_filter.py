"""
Unit tests for the KneePoint class.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the server directory to Python path so we can import from src
server_path = Path(__file__).resolve().parents[4]
if str(server_path) not in sys.path:
    sys.path.insert(0, str(server_path))

# Mock get_settings to prevent environment variable requirements
with patch("src.config.get_settings") as mock_get_settings:
    mock_get_settings.return_value = MagicMock(
        enable_turnstile=False,
        turnstile_secret_key=None,
        rrf_k_document=6,
        rrf_k_chunk=6,
        rrf_k_conditions_full=6,
        rrf_k_conditions_partial=6,
        rrf_k_keywords=10,
    )
    from src.core.engine.knee_point import KneePoint
    from src.db.models.search import EnhancedSearchResult


def make_result(score: float, doi: str = "d") -> EnhancedSearchResult:
    """Helper to create a mocked search result object with a given score."""
    return MagicMock(overall_score=score, doi=f"{doi}:{score:.3f}")


def run_filter(scores: list[float], **filter_kwargs):
    """Run the filter and return both stats and kept score values."""
    filter_ = KneePoint(**filter_kwargs)
    results = [make_result(score, doi=f"r{i}") for i, score in enumerate(scores)]
    stats = filter_.filter_with_stats(results)
    kept_scores = [result.overall_score for result in stats.filtered_results]
    return stats, kept_scores


def test_empty_results_returns_empty():
    """Test that an empty list of results returns an empty list."""
    filter = KneePoint()
    out = filter.filter([])
    assert out == []


def test_low_top_score_drops_all():
    """Test that if the top score is below the threshold, all results are dropped."""
    filter = KneePoint(min_top_score=0.25)
    low_score = 0.24  # Below the threshold
    results = [
        make_result(low_score),
        make_result(low_score - 0.01),
        make_result(max(low_score - 0.02, 0.0)),
    ]
    out = filter.filter(results)
    assert out == []


@pytest.mark.parametrize(
    ("scores", "expected_kept"),
    [
        ([0.8], [0.8]),
        ([0.8, 0.6], [0.8, 0.6]),
    ],
)
def test_small_n_kept_as_is(scores: list[float], expected_kept: list[float]):
    """Test that results below the min_results threshold are kept as-is."""
    stats, kept_scores = run_filter(scores, min_top_score=0.25, min_results=3)

    assert stats.min_results_threshold_met is False
    assert kept_scores == expected_kept


def test_small_n_below_top_score_still_drops_all():
    """Test that the top-score threshold still applies when result count is small."""
    stats, kept_scores = run_filter([0.1], min_top_score=0.25, min_results=3)

    assert stats.min_top_score_threshold_met is False
    assert kept_scores == []


def test_knee_detected_truncates_tail():
    """Test that a clear knee point correctly truncates the tail of the results."""
    scores = [0.95, 0.88, 0.72, 0.35, 0.34, 0.33, 0.30, 0.29]
    stats, kept_scores = run_filter(
        scores,
        min_top_score=0.25,
        min_results=3,
        linearity_epsilon=0.02,
    )
    out = stats.filtered_results

    # We expect to trim some, but not all, results
    assert 1 <= len(out) < len(scores)
    # The kept items should be the highest-scoring ones
    assert kept_scores[0] == max(scores)
    # The algorithm finds the knee at index 3 with knee_point_value 0.35.
    # Since 0.35 is lower than the previous score (0.72), it marks the start
    # of the drop and is excluded from the filtered results.
    assert stats.knee_index == 3
    assert stats.knee_point_value == 0.35
    assert len(out) == 3
    assert kept_scores == [0.95, 0.88, 0.72]


def test_near_linear_keeps_all():
    """Test that a near-linear decay in scores results in keeping all items."""
    scores = [0.90, 0.80, 0.70, 0.60, 0.50]
    _, kept_scores = run_filter(
        scores,
        min_top_score=0.25,
        min_results=3,
        linearity_epsilon=0.02,
    )

    # No clear knee, so all results should be kept
    assert kept_scores == sorted(scores, reverse=True)


def test_unsorted_input_is_handled():
    """Test that the function correctly handles unsorted input."""
    filter = KneePoint(min_top_score=0.25, min_results=3, linearity_epsilon=0.02)
    scores = [0.35, 0.95, 0.33, 0.88, 0.72, 0.34, 0.30, 0.29]  # Unsorted
    results = [make_result(s, doi=f"u{i}") for i, s in enumerate(scores)]
    out = filter.filter(results)
    kept_scores = [r.overall_score for r in out]

    # The function should sort the results and find the knee correctly.
    # 0.35 marks the start of the drop and is excluded.
    assert len(out) == 3
    assert kept_scores == [0.95, 0.88, 0.72]


def test_all_scores_identical_keeps_all():
    """Test that if all scores are identical, all results are kept."""
    scores = [0.8] * 5
    _, kept_scores = run_filter(
        scores,
        min_top_score=0.25,
        min_results=3,
        linearity_epsilon=0.02,
    )

    # With identical scores, the line is flat, so all should be kept
    assert kept_scores == scores


@pytest.mark.parametrize(
    ("scores", "expected_knee_value", "expected_kept"),
    [
        ([1.0] * 6 + [0.4375] * 5, 1.0, [1.0] * 6),
        ([1.0, 0.8, 0.8, 0.8, 0.8, 0.3, 0.3], 0.8, [1.0, 0.8, 0.8, 0.8, 0.8]),
        ([1.0, 0.3, 0.3, 0.3, 0.3], 0.3, [1.0, 0.3, 0.3, 0.3, 0.3]),
    ],
)
def test_plateau_boundary_keeps_all_ties(
    scores: list[float],
    expected_knee_value: float,
    expected_kept: list[float],
):
    """Test that all items sharing the knee-score plateau stay together."""
    stats, kept_scores = run_filter(
        scores,
        min_top_score=0.25,
        min_results=3,
        linearity_epsilon=0.02,
    )

    assert stats.knee_point_value == expected_knee_value
    assert kept_scores == expected_kept


def test_nearly_equal_scores_are_treated_as_same_plateau():
    """Test that tiny floating-point differences do not split a tied plateau."""
    scores = [1.0, 0.4375000000001, 0.4375, 0.4375, 0.2]
    stats, kept_scores = run_filter(
        scores,
        min_top_score=0.25,
        min_results=3,
        linearity_epsilon=0.02,
    )

    # The knee point is effectively the 0.4375 plateau, despite tiny float noise.
    assert stats.knee_point_value == scores[1]
    assert len(kept_scores) == 4
    assert kept_scores[-1] == 0.4375
    assert 0.2 not in kept_scores
