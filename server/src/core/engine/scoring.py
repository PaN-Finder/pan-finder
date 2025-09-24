from typing import Dict, List

from ...db.models.search import EnhancedSearchResult, StructuredQueryData
from ...config import get_settings
from ...utils import get_logger

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

    @staticmethod
    def overall_score_max(query_data: StructuredQueryData) -> float:
        total_max_score = 0.0
        if query_data.intention and query_data.intention.strip():
            total_max_score += Scoring.similarity_score_max
            total_max_score += Scoring.chunk_similarity_score_max
        if query_data.keywords and len(query_data.keywords) > 0:
            total_max_score += Scoring.keyword_score_max
        if query_data.filters and len(query_data.filters) > 0:
            total_max_score += Scoring.full_match_score_max
            total_max_score += Scoring.partial_match_score_max
        return total_max_score

    @staticmethod
    def components_enabled(query_data: StructuredQueryData) -> Dict[str, bool]:
        return {
            "similarity": bool(query_data.intention and query_data.intention.strip()),
            "chunk_similarity": bool(
                query_data.intention and query_data.intention.strip()
            ),
            "keyword": bool(query_data.keywords),
            "full_match": bool(query_data.filters),
            "partial_match": bool(query_data.filters),
        }

    @staticmethod
    def normalize_scores(
        results: List[EnhancedSearchResult], query_data: StructuredQueryData
    ) -> None:
        if not results:
            return

        enabled = Scoring.components_enabled(query_data)

        logger.debug(
            "Normalizing scores | enabled_components=%s | similarity_max=%.6f | chunk_similarity_max=%.6f | keyword_max=%.6f | full_match_max=%.6f | partial_match_max=%.6f | overall_max=%.6f | results_count=%d",
            enabled,
            Scoring.similarity_score_max,
            Scoring.chunk_similarity_score_max,
            Scoring.keyword_score_max,
            Scoring.full_match_score_max,
            Scoring.partial_match_score_max,
            Scoring.overall_score_max(query_data),
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

            overall_max = Scoring.overall_score_max(query_data)
            result.overall_score = (
                safe_div(result.overall_score, overall_max) if overall_max > 0 else 0.0
            )

        logger.debug("Normalized Search Results:")
        logger.debug("=" * 120)
        logger.debug(
            f"{'DOI':<30} {'Overall':<8} {'Similarity':<10} {'Chunk':<8} {'Keyword':<8} {'FullMatch':<9} {'Partial':<8}"
        )
        logger.debug("-" * 120)
        for result in results:
            logger.info(
                f"{result.doi:<30} {result.overall_score:<8.6f} {result.similarity_score:<10.6f} "
                f"{result.chunk_similarity_score:<8.6f} {result.keyword_score:<8.6f} "
                f"{result.full_match_score:<9.6f} {result.partial_match_score:<8.6f}"
            )
        logger.debug("=" * 120)
