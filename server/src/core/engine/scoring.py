import math
from typing import Dict, List

from ...db.models.search import EnhancedSearchResult, StructuredQueryData
from ...config import get_settings

settings = get_settings()


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

            boost_factor = 4.0
            boosted = math.log(boost_factor * result.overall_score + 1) / math.log(
                boost_factor + 1
            )
            result.overall_score = max(0.0, min(1.0, boosted))
