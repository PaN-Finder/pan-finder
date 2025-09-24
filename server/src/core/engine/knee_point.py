"""
Knee point filter for search results.

This module provides functionality to filter out weakly-relevant results from a list
of search results using a simple knee (elbow) detection algorithm.
"""

from typing import List, TypeVar, Protocol, NamedTuple

from ...db.models.search import EnhancedSearchResult

# Generic type for objects that have an overall_score attribute
T = TypeVar("T", bound="ScoredResult")


class ScoredResult(Protocol):
    """Protocol for objects that have an overall_score attribute."""

    overall_score: float


class KneePointResult(NamedTuple):
    """Result of knee point filtering with detailed statistics."""

    filtered_results: List[EnhancedSearchResult]
    original_count: int
    filtered_count: int
    knee_index: int
    knee_point_value: float
    max_distance: float
    top_score: float
    linearity_threshold_met: bool
    min_results_threshold_met: bool
    min_top_score_threshold_met: bool


class KneePoint:
    """
    A filter that removes weakly-relevant tail results using knee point detection.

    This class implements a simple, dependency-free knee (elbow) detection algorithm
    that identifies the point where result quality drops significantly and filters
    out results after that point.
    """

    def __init__(
        self,
        min_top_score: float = 0.25,
        min_results: int = 3,
        linearity_epsilon: float = 0.02,
    ):
        """
        Initialize the knee point filter with configurable parameters.

        Args:
            min_top_score: Minimum score threshold for the best result. If the top
                         score is below this, all results are dropped.
            min_results: Minimum number of results required to attempt knee detection.
                        If fewer results exist, all are kept (unless top score is too low).
            linearity_epsilon: If the maximum distance from the line connecting first
                             and last points is below this threshold, the curve is
                             considered nearly linear and all results are kept.
        """
        self.min_top_score = min_top_score
        self.min_results = min_results
        self.linearity_epsilon = linearity_epsilon

    def filter(self, results: List[EnhancedSearchResult]) -> List[EnhancedSearchResult]:
        """
        Filter out the weakest tail items using a simple knee (elbow) heuristic.

        Algorithm (simple & dependency-free):
        1. Sort results by descending overall_score (they should already be sorted, but ensure).
        2. If top score < min_top_score => return empty list (nothing good enough).
        3. If fewer than min_results => return as-is (unless top < threshold above).
        4. Treat points as (index, score). Compute distance of each point to the straight line
           connecting first and last point. Knee = point with maximum distance.
        5. If max distance < linearity_epsilon -> scores roughly linear => keep all.
        6. Keep items up to and including knee index; discard remainder (tail after sharp drop).

        This is intentionally lightweight (no external libs) and robust for small N (~20).

        Args:
            results: List of objects with overall_score attribute to filter

        Returns:
            Filtered list of results with weak tail results removed
        """
        result = self.filter_with_stats(results)
        return result.filtered_results

    def filter_with_stats(self, results: List[EnhancedSearchResult]) -> KneePointResult:
        """
        Filter out the weakest tail items and return detailed statistics.

        Args:
            results: List of objects with overall_score attribute to filter

        Returns:
            KneePointResult containing filtered results and statistics
        """
        original_count = len(results)

        if not results:
            return KneePointResult(
                filtered_results=results,
                original_count=0,
                filtered_count=0,
                knee_index=-1,
                knee_point_value=0.0,
                max_distance=0.0,
                top_score=0.0,
                linearity_threshold_met=True,
                min_results_threshold_met=True,
                min_top_score_threshold_met=True,
            )

        # Defensive copy sort (stable)
        results_sorted = sorted(results, key=lambda r: r.overall_score, reverse=True)

        top_score = results_sorted[0].overall_score
        min_top_score_threshold_met = top_score >= self.min_top_score

        if not min_top_score_threshold_met:
            # Top score too low -> drop all
            return KneePointResult(
                filtered_results=[],
                original_count=original_count,
                filtered_count=0,
                knee_index=-1,
                knee_point_value=0.0,
                max_distance=0.0,
                top_score=top_score,
                linearity_threshold_met=False,
                min_results_threshold_met=True,
                min_top_score_threshold_met=False,
            )

        n = len(results_sorted)
        min_results_threshold_met = n >= self.min_results

        if not min_results_threshold_met:
            return KneePointResult(
                filtered_results=results_sorted,
                original_count=original_count,
                filtered_count=n,
                knee_index=n - 1,
                knee_point_value=(
                    results_sorted[-1].overall_score if results_sorted else 0.0
                ),
                max_distance=0.0,
                top_score=top_score,
                linearity_threshold_met=True,
                min_results_threshold_met=False,
                min_top_score_threshold_met=True,
            )

        # Coordinates
        x0, y0 = 0.0, results_sorted[0].overall_score
        x1, y1 = float(n - 1), results_sorted[-1].overall_score
        dx = x1 - x0
        dy = y1 - y0
        denom = (dx**2 + dy**2) ** 0.5 or 1.0

        max_dist = -1.0
        knee_index = n - 1  # default keep all
        for i, item in enumerate(results_sorted):
            x = float(i)
            y = item.overall_score
            # Perpendicular distance from point to line between first & last point
            # |dy*x - dx*y + x1*y0 - y1*x0| / sqrt(dx^2 + dy^2)
            dist = abs(dy * x - dx * y + x1 * y0 - y1 * x0) / denom
            if dist > max_dist:
                max_dist = dist
                knee_index = i

        linearity_threshold_met = max_dist < self.linearity_epsilon

        if linearity_threshold_met:
            # Almost linear decay -> no clear knee -> keep all
            kept = results_sorted
        else:
            kept = results_sorted[
                :knee_index
            ]  # reults before knee point (excliding knee point)

        # Calculate the knee point value (score at the knee index)
        knee_point_value = (
            results_sorted[knee_index].overall_score
            if knee_index >= 0 and knee_index < len(results_sorted)
            else 0.0
        )

        return KneePointResult(
            filtered_results=kept,
            original_count=original_count,
            filtered_count=len(kept),
            knee_index=knee_index,
            knee_point_value=knee_point_value,
            max_distance=max_dist,
            top_score=top_score,
            linearity_threshold_met=linearity_threshold_met,
            min_results_threshold_met=min_results_threshold_met,
            min_top_score_threshold_met=min_top_score_threshold_met,
        )
