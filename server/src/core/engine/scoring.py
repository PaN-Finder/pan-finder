from ...config import get_settings
from ...db.models.search import EnhancedSearchResult
from ...utils import get_logger
from ..search_query_builder import SubqueriesUsed

settings = get_settings()
logger = get_logger(__name__)


class Scoring:
    """
    Class to hold maximum scores based on RRF parameters.
    These are used to normalize the search result scores.
    """

    similarity_score_max = 1 / (1 + settings.rrf_k_similarity)
    chunk_similarity_score_max = 1 / (1 + settings.rrf_k_chunk)
    full_match_score_max = 1 / (1 + settings.rrf_k_full_match)
    partial_match_score_max = 1 / (1 + settings.rrf_k_partial_match)
    keyword_score_max = 1 / (1 + settings.rrf_k_keyword)
    value_vector_score_max = 1 / (1 + settings.rrf_k_value_vector)

    @staticmethod
    def overall_score_max(subqueries_used: SubqueriesUsed) -> float:
        total_max_score = 0.0
        if subqueries_used["similarity"]:
            total_max_score += Scoring.similarity_score_max
        if subqueries_used["chunk_similarity"]:
            total_max_score += Scoring.chunk_similarity_score_max
        if subqueries_used["keyword"]:
            total_max_score += Scoring.keyword_score_max
        if subqueries_used["full_match"]:
            total_max_score += Scoring.full_match_score_max
        if subqueries_used["partial_match"]:
            total_max_score += Scoring.partial_match_score_max
        if subqueries_used["value_vector"]:
            total_max_score += Scoring.value_vector_score_max
        return total_max_score

    @staticmethod
    def components_enabled(subqueries_used: SubqueriesUsed) -> SubqueriesUsed:
        return subqueries_used

    @staticmethod
    def normalize_scores(
        results: list[EnhancedSearchResult], subqueries_used: SubqueriesUsed
    ) -> None:
        if not results:
            return

        enabled = Scoring.components_enabled(subqueries_used)

        logger.debug(
            "Normalizing scores | enabled_components=%s | similarity_max=%.6f | chunk_similarity_max=%.6f | keyword_max=%.6f | full_match_max=%.6f | partial_match_max=%.6f | value_vector_max=%.6f | overall_max=%.6f | results_count=%d",
            enabled,
            Scoring.similarity_score_max,
            Scoring.chunk_similarity_score_max,
            Scoring.keyword_score_max,
            Scoring.full_match_score_max,
            Scoring.partial_match_score_max,
            Scoring.value_vector_score_max,
            Scoring.overall_score_max(subqueries_used),
            len(results),
        )

        def safe_div(value: float, denom: float) -> float:
            if denom <= 0:
                return 0.0
            return value / denom

        for result in results:
            if enabled["similarity"]:
                result.similarity_score = safe_div(
                    result.similarity_score, Scoring.similarity_score_max
                )
                result.chunk_similarity_score = safe_div(
                    result.chunk_similarity_score, Scoring.chunk_similarity_score_max
                )
            else:
                result.similarity_score = 0.0
                result.chunk_similarity_score = 0.0

            if enabled["keyword"]:
                result.keyword_score = safe_div(
                    result.keyword_score, Scoring.keyword_score_max
                )
            else:
                result.keyword_score = 0.0

            if enabled["full_match"]:
                result.full_match_score = safe_div(
                    result.full_match_score, Scoring.full_match_score_max
                )
                result.partial_match_score = safe_div(
                    result.partial_match_score, Scoring.partial_match_score_max
                )
            else:
                result.full_match_score = 0.0
                result.partial_match_score = 0.0

            if enabled["value_vector"]:
                result.value_vector_score = safe_div(
                    result.value_vector_score, Scoring.value_vector_score_max
                )
            else:
                result.value_vector_score = 0.0

            overall_max = Scoring.overall_score_max(subqueries_used)
            result.overall_score = (
                safe_div(result.overall_score, overall_max) if overall_max > 0 else 0.0
            )
