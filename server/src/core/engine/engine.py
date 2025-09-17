import json
import time
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI
from psycopg.rows import dict_row
from psycopg.sql import Composed
from typing import Tuple, cast, Any, List, Optional, AsyncGenerator, Dict, Callable

from ...db.models.document import DocumentTypedDict
from ...db.models.document_repository import DocumentRepository
from ...db.models.search import StructuredQueryData, EnhancedSearchResult
from ...db.connection import get_connection_pool, get_db_connection
from ..search_query_builder import SearchQueryBuilder, SearchResult
from ..ai.prompts import AIPrompts
from ..ai.cache import LLMResponseCache
from ...utils import get_logger
from ...config import get_settings
from .scoring import Scoring
from .knee_point import KneePoint, KneePointResult

settings = get_settings()


class SearchEngine:
    """
    A search engine that combines OpenAI processing with database search capabilities.

    This class encapsulates the search functionality including query processing,
    structured query extraction, and result retrieval.
    """

    def __init__(
        self,
        openai_client: Optional[AzureOpenAI] = None,
        sentence_transformer: Optional[SentenceTransformer] = None,
        query_builder: Optional[SearchQueryBuilder] = None,
    ):
        """
        Initialize the SearchEngine with optional dependencies.

        Args:
            openai_client: Azure OpenAI client for query processing
            sentence_transformer: SentenceTransformer model for embeddings
            query_builder: SearchQueryBuilder for generating SQL queries
        """
        self._openai_client = openai_client
        self._sentence_transformer = sentence_transformer
        self._query_builder = query_builder
        self._logger = get_logger(self.__class__.__name__)
        self._llm_cache = LLMResponseCache(logger=self._logger)
        self._knee_point = KneePoint()

    @property
    def openai_client(self) -> AzureOpenAI:
        """Lazy-loaded OpenAI client."""
        if self._openai_client is None:
            self._openai_client = AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
            )
        return self._openai_client

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
                pool=get_connection_pool(),
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
        Parse a natural language query into structured components using OpenAI.

        Args:
            query: The search query string

        Returns:
            StructuredQueryData containing structured query information with intention, keywords, and filters
        """
        model_name = settings.azure_openai_model_name

        # Check if we have a cached response
        cached_response = self._llm_cache.get(model_name, query)
        if cached_response is not None:
            self._logger.debug(f"Using cached LLM response for query: {query}")
            return self._parse_openai_response(cached_response, query)

        # Short-circuit empty / whitespace-only queries to avoid unnecessary LLM calls
        if not query or not query.strip():
            return StructuredQueryData(intention="", keywords=[], filters={})

        def _do_call() -> Optional[str]:
            llm_response = self.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": AIPrompts.get_structured_query_extraction_prompt(),
                    },
                    {"role": "user", "content": query},
                ],
                max_tokens=500,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            return llm_response.choices[0].message.content

        response_content = self._retry_openai_call(
            _do_call, context="structured_query_extraction"
        )

        if response_content is None:
            # Fallback heuristics
            return StructuredQueryData(
                intention=query,
                keywords=[w for w in query.split() if w],
                filters={},
            )

        # Cache only on success
        self._llm_cache.put(model_name, query, response_content)
        return self._parse_openai_response(response_content, query)

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
            with get_db_connection() as conn:
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
                        summary=doc.get("summary") or "",
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
            "summary": result.summary,
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

    async def explain_search_results(
        self,
        query: str,
        search_results: List[EnhancedSearchResult],
        structured_data: StructuredQueryData,
    ) -> AsyncGenerator[str, None]:
        """Stream a qualitative explanation for the ranked (knee-point filtered) results.

        The method prepares a flattened list of relevant results (no grouping) and calls
        the LLM with the updated single-section explanation prompt. Responses are cached
        keyed on the query plus the serialized results for determinism.
        """
        model_name = settings.azure_openai_explanation_model_name

        # Prepare data (already knee-point filtered upstream)
        results_summary = {
            "total_results": len(search_results),
            "relevant": [
                self._build_result_dict(result, structured_data)
                for result in search_results
            ],
        }

        # Cache key
        results_json = json.dumps(results_summary, sort_keys=True)
        cache_key = f"{query}||{results_json}"

        cached_response = self._llm_cache.get(model_name, cache_key)
        if cached_response is not None:
            self._logger.debug("Using cached explanation for query: %s", query)
            yield cached_response
            return

        user_content = (
            'Original Query: "'
            + query
            + '"\n\nStructured Query Data (reference context only):\n'
            + json.dumps(structured_data.model_dump(), indent=2)
            + "\n\nRanked Relevant Results (already knee-point filtered, DO NOT mention that process):\n"
            + json.dumps(results_summary["relevant"], indent=2)
            + "\n\nInstructions Recap (do NOT repeat to user): Provide markdown with a single section `## Relevant Results` (or the no-results header) and up to 3 bullets, one sentence each, qualitative only."
        )

        def _start_stream():
            return self.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": AIPrompts.get_result_explanation_prompt(),
                    },
                    {"role": "user", "content": user_content},
                ],
                max_tokens=800,
                temperature=0.3,
                stream=True,
            )

        stream = self._retry_openai_call(
            _start_stream, context="result_explanation_stream"
        )
        if stream is None:
            fallback_explanation = self._create_fallback_explanation(
                query, len(search_results)
            )
            yield fallback_explanation
            return

        collected_content = ""
        try:
            for chunk in stream:
                if hasattr(chunk, "choices") and len(chunk.choices) > 0:
                    content = getattr(chunk.choices[0].delta, "content", "")
                    if content:
                        collected_content += content
                        yield content
                else:
                    self._logger.warning(
                        "Unexpected chunk format from OpenAI during streaming: %s",
                        chunk,
                    )
        except Exception as e:  # noqa: BLE001
            self._logger.error(
                "Streaming error from OpenAI (explanation). Yielding fallback. Error: %s",
                e,
            )
            if not collected_content:
                yield self._create_fallback_explanation(query, len(search_results))
        else:
            self._logger.debug("OpenAI streaming completed")
            if collected_content:
                self._llm_cache.put(model_name, cache_key, collected_content)

    def _retry_openai_call(
        self,
        func: Callable[[], Any],
        attempts: int = 3,
        base_backoff: float = 0.75,
        context: str = "openai_call",
    ) -> Optional[Any]:
        """Generic retry helper for OpenAI SDK calls.

        Parameters:
            func: Zero-arg callable performing the OpenAI SDK invocation.
            attempts: Max attempts.
            base_backoff: Initial backoff seconds (doubles each retry).
            context: Log context label.
        Returns:
            Result of func() or None if all attempts fail.
        """
        backoff = base_backoff
        for attempt in range(1, attempts + 1):
            try:
                return func()
            except Exception as e:
                self._logger.warning(
                    f"{context} attempt {attempt}/{attempts} failed: {e}"
                )
                if attempt == attempts:
                    break
                time.sleep(backoff)
                backoff *= 2
        self._logger.error(f"All {attempts} attempts failed for {context}.")
        return None

    def _create_fallback_explanation(self, query: str, result_count: int) -> str:
        """
        Create a fallback explanation when OpenAI processing fails.

        Args:
            query: Original query string
            result_count: Number of results found

        Returns:
            Basic explanation string
        """
        if result_count == 0:
            return f"No results were found for your search query '{query}'. You might want to try using different keywords or broader search terms."
        elif result_count == 1:
            return f"Found 1 result for your search query '{query}'. The result appears to be relevant to your search criteria."
        else:
            return f"Found {result_count} results for your search query '{query}'. The results are ranked by relevance to your search criteria, with the most relevant results appearing first."


@lru_cache()
def get_search_engine() -> SearchEngine:
    """Get a cached SearchEngine instance."""
    return SearchEngine()
