"""
Unit tests for the KneePoint class.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add the server directory to Python path so we can import from src
server_path = Path(__file__).resolve().parents[4]
if str(server_path) not in sys.path:
    sys.path.insert(0, str(server_path))

from src.core.engine.knee_point import KneePoint
from src.db.models.search import EnhancedSearchResult


def make_result(score: float, doi: str = "d") -> EnhancedSearchResult:
    """Helper to create a mocked search result object with a given score."""
    return MagicMock(overall_score=score, doi=f"{doi}:{score:.3f}")


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


def test_small_n_kept_as_is():
    """Test that if there are fewer results than the minimum, all are kept."""
    filter = KneePoint(min_top_score=0.25, min_results=3)
    high_score = 0.5  # Above the threshold
    # Create 2 results, which is less than the min_results of 3
    results = [make_result(high_score), make_result(high_score * 0.9)]
    out = filter.filter(results)
    assert len(out) == len(results)
    assert [r.overall_score for r in out] == sorted(
        [r.overall_score for r in results], reverse=True
    )


def test_knee_detected_truncates_tail():
    """Test that a clear knee point correctly truncates the tail of the results."""
    filter = KneePoint(min_top_score=0.25, min_results=3, linearity_epsilon=0.02)
    # A clear knee exists after the third item
    scores = [0.95, 0.88, 0.72, 0.35, 0.34, 0.33, 0.30, 0.29]
    results = [make_result(s, doi=f"k{i}") for i, s in enumerate(scores)]
    out = filter.filter(results)
    kept_scores = [r.overall_score for r in out]

    # We expect to trim some, but not all, results
    assert 1 <= len(out) < len(results)
    # The kept items should be the highest-scoring ones
    assert kept_scores[0] == max(scores)
    # The algorithm should find the knee at index 3 (score 0.35)
    assert len(out) == 3
    assert kept_scores == [0.95, 0.88, 0.72]


def test_near_linear_keeps_all():
    """Test that a near-linear decay in scores results in keeping all items."""
    filter = KneePoint(min_top_score=0.25, min_results=3, linearity_epsilon=0.02)

    # Scores with a perfectly linear decay
    scores = [0.90, 0.80, 0.70, 0.60, 0.50]
    results = [make_result(s, doi=f"l{i}") for i, s in enumerate(scores)]
    out = filter.filter(results)

    # No clear knee, so all results should be kept
    assert len(out) == len(results)
    assert [r.overall_score for r in out] == sorted(scores, reverse=True)


def test_unsorted_input_is_handled():
    """Test that the function correctly handles unsorted input."""
    filter = KneePoint(min_top_score=0.25, min_results=3, linearity_epsilon=0.02)
    scores = [0.35, 0.95, 0.33, 0.88, 0.72, 0.34, 0.30, 0.29]  # Unsorted
    results = [make_result(s, doi=f"u{i}") for i, s in enumerate(scores)]
    out = filter.filter(results)
    kept_scores = [r.overall_score for r in out]

    # The function should sort the results and find the knee correctly
    assert len(out) == 3
    assert kept_scores == [0.95, 0.88, 0.72]


def test_all_scores_identical_keeps_all():
    """Test that if all scores are identical, all results are kept."""
    filter = KneePoint(min_top_score=0.25, min_results=3, linearity_epsilon=0.02)
    scores = [0.8] * 5
    results = [make_result(s, doi=f"i{i}") for i, s in enumerate(scores)]
    out = filter.filter(results)

    # With identical scores, the line is flat, so all should be kept
    assert len(out) == len(results)
    assert [r.overall_score for r in out] == scores


def test_custom_parameters():
    """Test that custom parameters work correctly."""
    # Test with more restrictive parameters
    filter = KneePoint(
        min_top_score=0.5,  # Higher threshold
        min_results=5,  # More results needed
        linearity_epsilon=0.001,  # Very strict linearity
    )

    # Test that higher threshold drops results
    scores = [0.4, 0.3, 0.2]  # All below 0.5 threshold
    results = [make_result(s, doi=f"c{i}") for i, s in enumerate(scores)]
    out = filter.filter(results)
    assert out == []

    # Test that minimum results requirement works
    scores = [0.9, 0.8, 0.7, 0.6]  # 4 results, less than min_results=5
    results = [make_result(s, doi=f"c{i}") for i, s in enumerate(scores)]
    out = filter.filter(results)
    assert len(out) == len(results)  # All kept because below minimum


def test_edge_case_single_result():
    """Test behavior with a single result."""
    filter = KneePoint(min_top_score=0.25, min_results=3)

    # Single result above threshold
    results = [make_result(0.8)]
    out = filter.filter(results)
    assert len(out) == 1
    assert out[0].overall_score == 0.8

    # Single result below threshold
    results = [make_result(0.1)]
    out = filter.filter(results)
    assert out == []


def test_edge_case_two_results():
    """Test behavior with exactly two results."""
    filter = KneePoint(min_top_score=0.25, min_results=3)

    results = [make_result(0.8), make_result(0.6)]
    out = filter.filter(results)
    assert len(out) == 2  # Both kept because below min_results
    assert [r.overall_score for r in out] == [0.8, 0.6]
