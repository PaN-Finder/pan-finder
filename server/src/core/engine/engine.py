import json
import time
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, cast

from psycopg.rows import dict_row
from psycopg.sql import Composed
from sentence_transformers import SentenceTransformer

from ...config import get_settings
from ...db.connection import get_database_connection, get_database_pool
from ...db.models.document import DocumentTypedDict
from ...db.models.document_repository import DocumentRepository
from ...db.models.search import EnhancedSearchResult, StructuredQueryData
from ...utils import get_logger
from ..ai.llm_client import LLMClient, LLMMessage, create_llm_client
from ..ai.prompts import AIPrompts
from ..search_query_builder import SearchQueryBuilder, SearchResult
from .knee_point import KneePoint, KneePointResult
from .scoring import Scoring

settings = get_settings()


class SearchEngine:
    """
    A search engine that combines OpenAI processing with database search capabilities.

    This class encapsulates the search functionality including query processing,
    structured query extraction, and result retrieval.
    """

    def __init__(
        self,
        sentence_transformer: Optional[SentenceTransformer] = None,
        query_builder: Optional[SearchQueryBuilder] = None,
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Initialize the SearchEngine with optional dependencies.

        Args:
            sentence_transformer: SentenceTransformer model for embeddings
            query_builder: SearchQueryBuilder for generating SQL queries
            llm_client: LLM client for AI completions
        """

        self._sentence_transformer = sentence_transformer
        self._query_builder = query_builder
        self._logger = get_logger(self.__class__.__name__)
        self._knee_point = KneePoint()

        # Initialize LLM client
        if llm_client is not None:
            self._llm_client = llm_client
        else:
            # Create default LLM client with hybrid cache
            self._llm_client = create_llm_client(
                cache_type="memory",
            )

    @property
    def sentence_transformer(self) -> SentenceTransformer:
        """Lazy-loaded sentence transformer model."""
        if self._sentence_transformer is None:
            self._sentence_transformer = SentenceTransformer(
                settings.embedding_model_path, device="cpu"
            )
        return self._sentence_transformer

    @property
    def query_builder(self) -> SearchQueryBuilder:
        """Lazy-loaded search query builder."""
        if self._query_builder is None:
            self._query_builder = SearchQueryBuilder(
                pool=get_database_pool("default"),
                sentence_transformer=self.sentence_transformer,
                rrf_k_similarity=settings.rrf_k_similarity,
                rrf_k_chunk=settings.rrf_k_chunk,
                rrf_k_full_match=settings.rrf_k_full_match,
                rrf_k_partial_match=settings.rrf_k_partial_match,
                rrf_k_keyword=settings.rrf_k_keyword,
                logger=get_logger("SearchQueryBuilder"),
            )
        return self._query_builder

    async def parse_query_to_structured_data(self, query: str) -> StructuredQueryData:
        """
        Parse a natural language query into structured components using LLM.

        Args:
            query: The search query string

        Returns:
            StructuredQueryData containing structured query information with intention, keywords, and filters
        """
        # Short-circuit empty / whitespace-only queries to avoid unnecessary LLM calls
        if not query or not query.strip():
            return StructuredQueryData(intention="", keywords=[], filters={})

        try:
            # Create LLM request
            messages = [
                LLMMessage(
                    role="system",
                    content=AIPrompts.get_structured_query_extraction_prompt(),
                ),
                LLMMessage(role="user", content=query),
            ]

            request = self._llm_client.create_request(
                messages=messages,
                max_tokens=500,
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            # Get response from LLM
            response = await self._llm_client.complete(request)
            return self._parse_openai_response(response.content, query)

        except Exception as e:
            self._logger.error(f"LLM query parsing failed: {e}")
            # Fallback heuristics
            return StructuredQueryData(
                intention=query,
                keywords=[w for w in query.split() if w],
                filters={},
            )

    def _parse_openai_response(
        self, response_content: Optional[str], query: str
    ) -> StructuredQueryData:
        """
        Parse the OpenAI response content into structured query data.

        Args:
            response_content: Raw response from OpenAI
            query: Original query for fallback

        Returns:
            StructuredQueryData containing structured query information
        """
        try:
            if response_content is None:
                raise ValueError("Empty response from OpenAI")

            search_data = json.loads(response_content)

            # Validate the response has required fields
            if not isinstance(search_data, dict):
                raise ValueError("Response is not a dictionary")

            # Ensure required fields exist
            search_data.setdefault("intention", "")
            search_data.setdefault("keywords", [])
            search_data.setdefault("filters", {})

            return StructuredQueryData(
                intention=search_data["intention"],
                keywords=search_data["keywords"],
                filters=search_data["filters"],
            )

        except (json.JSONDecodeError, ValueError) as e:
            self._logger.error(f"Failed to parse OpenAI response as JSON: {e}")
            self._logger.debug(f"Raw response: {response_content}")

            # Fallback to simple processing if JSON parsing fails
            return StructuredQueryData(
                intention=response_content if response_content else query,
                keywords=query.split() if query else [],
                filters={},
            )

    async def execute_search(
        self, search_data: StructuredQueryData
    ) -> Tuple[List[EnhancedSearchResult], Composed, Optional[KneePointResult]]:
        """
        Execute the search using the structured query data.

        Args:
            search_data: Structured query information
            return_knee_stats: Whether to return knee point statistics

        Returns:
            Tuple of (enhanced search results, SQL query, optional knee point stats)
        """
        try:
            # Generate SQL query
            query_build_start = time.time()
            sql_query = self.query_builder.build_query(search_data.model_dump())
            query_build_time = time.time() - query_build_start
            self._logger.debug(
                f"SQL query building took {query_build_time:.3f} seconds"
            )

            # Execute the query
            db_execution_start = time.time()
            results = self._execute_database_query(sql_query)
            db_execution_time = time.time() - db_execution_start
            self._logger.debug(
                f"Database execution took {db_execution_time:.3f} seconds"
            )

            # Normalize scores to a 0-1 range
            Scoring.normalize_scores(results, search_data)

            # Apply knee-point filtering to discard low-relevance tail
            knee_result = self._knee_point.filter_with_stats(results)

            return (results, sql_query, knee_result)

        except Exception as e:
            self._logger.error(f"Search execution error: {e}")
            return [], sql_query, None

    def _execute_database_query(
        self, sql_query: Composed
    ) -> List[EnhancedSearchResult]:
        """
        Execute the database query and process results.

        Args:
            sql_query: SQL query to execute

        Returns:
            List of enhanced search results
        """
        search_results = []

        try:
            with get_database_connection() as conn:
                with conn.cursor(row_factory=dict_row) as cursor:
                    # Execute the search query
                    cursor.execute(cast(Any, sql_query))
                    raw_results: List[SearchResult] = cast(
                        List[SearchResult], cursor.fetchall()
                    )

                    self._logger.debug(f"Raw search results count: {len(raw_results)}")

                    # Get document details if we have results
                    if raw_results:
                        document_details = (
                            DocumentRepository.get_document_details_by_dois(
                                dois=[result["doi"] for result in raw_results]
                            )
                        )
                        search_results = self._process_search_results(
                            raw_results, document_details
                        )

        except Exception as e:
            self._logger.error(f"Database query error: {e}")

        return search_results

    def _process_search_results(
        self, raw_results: List[SearchResult], document_details: List[DocumentTypedDict]
    ) -> List[EnhancedSearchResult]:
        """
        Process and combine search results with document details.

        Args:
            raw_results: Raw search results
            document_details: Document details from database

        Returns:
            List of enhanced search results
        """
        # Create a mapping of DOI to document details
        doc_map = {doc["doi"]: doc for doc in document_details}
        search_results = []

        # Combine search scores with document details
        for result in raw_results:
            doi = result["doi"]
            if doi in doc_map:
                doc = doc_map[doi]
                search_results.append(
                    EnhancedSearchResult(
                        doi=doi,
                        title=doc.get("title", ""),
                        facility_name=doc.get("facility_name") or "",
                        abstract=doc.get("abstract") or "",
                        overall_score=float(result.get("overall_score", 0)),
                        similarity_score=float(result.get("similarity_score", 0)),
                        chunk_similarity_score=float(
                            result.get("chunk_similarity_score", 0)
                        ),
                        full_match_score=float(result.get("full_match_score", 0)),
                        partial_match_score=float(result.get("partial_match_score", 0)),
                        keyword_score=float(result.get("keyword_score", 0)),
                    )
                )

        return search_results

    def _build_result_dict(
        self, result: EnhancedSearchResult, structured_data: StructuredQueryData
    ) -> dict:
        """
        Build result dictionary with scores dynamically based on structured data components.
        Follows the same logic as MaxScores.overall_score_max.

        Args:
            result: EnhancedSearchResult to build dictionary for
            structured_data: StructuredQueryData containing query components

        Returns:
            Dictionary with relevant score fields based on query components
        """
        result_dict: Dict[str, Any] = {
            "title": result.title,
            "doi": result.doi,
            "abstract": result.abstract,
            "overall_score": result.overall_score,
        }

        # Include similarity scores only if intention is not empty
        if structured_data.intention and structured_data.intention.strip():
            result_dict["similarity_score"] = result.similarity_score
            result_dict["chunk_similarity_score"] = result.chunk_similarity_score

        # Include keyword score only if keywords are provided
        if structured_data.keywords and len(structured_data.keywords) > 0:
            result_dict["keyword_score"] = result.keyword_score

        # Include full_match and partial_match scores only if filters are provided
        if structured_data.filters and len(structured_data.filters) > 0:
            # Preserve numeric scores; *add* boolean convenience flag
            result_dict["full_match_score"] = result.full_match_score
            result_dict["full_match"] = result.full_match_score > 0
            result_dict["partial_match_score"] = result.partial_match_score

        return result_dict

    async def explain_relevancy_of_document(
        self,
        query: str,
        document: EnhancedSearchResult,
        structured_data: StructuredQueryData,
    ) -> AsyncGenerator[str, None]:
        """
        Generate an explanation of why the selected document was considered relevant to the query.
        """
        doc_dict = self._build_result_dict(document, structured_data)
        user_content = (
            'Original Query: "'
            + query
            + '"\n\nStructured Query Data (reference context only):\n'
            + json.dumps(structured_data.model_dump(), indent=2)
            + "\n\nDocument:\n"
            + json.dumps(doc_dict, indent=2)
        )
        try:
            messages = [
                LLMMessage(role="system", content=AIPrompts.get_explanation_prompt()),
                LLMMessage(role="user", content=user_content),
            ]

            request = self._llm_client.create_request(
                messages=messages,
                max_tokens=1500,
                temperature=0.3,
                model=settings.explanation_model_name,
                stream=True,
            )

            # Stream the response
            async for chunk in self._llm_client.complete_stream(request):
                yield chunk

        except Exception as e:
            self._logger.error(f"LLM explanation failed: {e}")
            yield "Could not generate explanation due to an internal error."


@lru_cache()
def get_search_engine() -> SearchEngine:
    """Get a cached SearchEngine instance."""
    return SearchEngine()
