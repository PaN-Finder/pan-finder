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

    document_score_max = 1 / (1 + settings.rrf_k_document)
    chunk_score_max = 1 / (1 + settings.rrf_k_chunk)
    conditions_full_score_max = 1 / (1 + settings.rrf_k_conditions_full)
    conditions_partial_score_max = 1 / (1 + settings.rrf_k_conditions_partial)
    keywords_score_max = 1 / (1 + settings.rrf_k_keywords)

    @staticmethod
    def overall_score_max(subqueries_used: SubqueriesUsed) -> float:
        total_max_score = 0.0
        if subqueries_used["document"]:
            total_max_score += Scoring.document_score_max
        if subqueries_used["chunk"]:
            total_max_score += Scoring.chunk_score_max
        if subqueries_used["keywords"]:
            total_max_score += Scoring.keywords_score_max
        if subqueries_used["conditions_full"]:
            total_max_score += Scoring.conditions_full_score_max
        if subqueries_used["conditions_partial"]:
            total_max_score += Scoring.conditions_partial_score_max
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
            "Normalizing scores | enabled_components=%s | document_max=%.6f | chunk_max=%.6f | keywords_max=%.6f | conditions_full_max=%.6f | conditions_partial_max=%.6f | overall_max=%.6f | results_count=%d",
            enabled,
            Scoring.document_score_max,
            Scoring.chunk_score_max,
            Scoring.keywords_score_max,
            Scoring.conditions_full_score_max,
            Scoring.conditions_partial_score_max,
            Scoring.overall_score_max(subqueries_used),
            len(results),
        )

        def safe_div(value: float, denom: float) -> float:
            if denom <= 0:
                return 0.0
            return value / denom

        for result in results:
            if enabled["document"]:
                result.document_score = safe_div(
                    result.document_score, Scoring.document_score_max
                )
                result.chunk_score = safe_div(
                    result.chunk_score, Scoring.chunk_score_max
                )
            else:
                result.document_score = 0.0
                result.chunk_score = 0.0

            if enabled["keywords"]:
                result.keywords_score = safe_div(
                    result.keywords_score, Scoring.keywords_score_max
                )
            else:
                result.keywords_score = 0.0

            if enabled["conditions_full"]:
                result.conditions_full_score = safe_div(
                    result.conditions_full_score, Scoring.conditions_full_score_max
                )
                result.conditions_partial_score = safe_div(
                    result.conditions_partial_score,
                    Scoring.conditions_partial_score_max,
                )
            else:
                result.conditions_full_score = 0.0
                result.conditions_partial_score = 0.0

            overall_max = Scoring.overall_score_max(subqueries_used)
            result.overall_score = (
                safe_div(result.overall_score, overall_max) if overall_max > 0 else 0.0
            )
