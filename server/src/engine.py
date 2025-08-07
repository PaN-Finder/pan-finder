import json
import time
import math
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI
from psycopg.rows import dict_row
from typing import cast, Any, List, Optional, AsyncGenerator, Dict
from pydantic import BaseModel

from .database import get_connection_pool, get_db_connection
from .core.search_query_builder import SearchQueryBuilder
from .core.prompts import AIPrompts
from .core.llm_cache import LLMResponseCache
from .setup_logging import get_logger
from .config import get_settings

settings = get_settings()


class StructuredQueryData(BaseModel):
    """
    Structured representation of a parsed search query.

    This model represents the structured data extracted from a natural language
    search query, containing the user's intention, relevant keywords, and any
    filters to apply to the search.
    """

    intention: str
    keywords: List[str]
    filters: Dict[str, Any]


class MaxScores:
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
        """
        Calculate the overall maximum score based on individual max scores and query data.
        This is used to normalize the overall score of search results.

        Args:
            query_data: StructuredQueryData containing structured query information
        """

        total_max_score = 0.0

        # Include similarity scores only if intention is not empty
        if query_data.intention and query_data.intention.strip():
            total_max_score += MaxScores.similarity_score_max
            total_max_score += MaxScores.chunk_similarity_score_max

        # Include keyword score only if keywords are provided
        if query_data.keywords and len(query_data.keywords) > 0:
            total_max_score += MaxScores.keyword_score_max

        # Include full_match and partial_match scores only if filters are provided
        if query_data.filters and len(query_data.filters) > 0:
            total_max_score += MaxScores.full_match_score_max
            total_max_score += MaxScores.partial_match_score_max

        return total_max_score


class EnhancedSearchResult(BaseModel):
    doi: str
    title: str
    summary: str
    overall_score: float
    similarity_score: float
    chunk_similarity_score: float
    full_match_score: float
    partial_match_score: float
    keyword_score: float


class SearchEngine:
    """
    A search engine that combines OpenAI processing with database search capabilities.

    This class encapsulates the search functionality including query processing,
    structured query extraction, and result retrieval.
    """

    def __init__(
        self,
        openai_client: Optional[AzureOpenAI] = None,
        embedding_model: Optional[SentenceTransformer] = None,
        query_builder: Optional[SearchQueryBuilder] = None,
    ):
        """
        Initialize the SearchEngine with optional dependencies.

        Args:
            openai_client: Azure OpenAI client for query processing
            embedding_model: SentenceTransformer model for embeddings
            query_builder: SearchQueryBuilder for generating SQL queries
        """
        self._openai_client = openai_client
        self._embedding_model = embedding_model
        self._query_builder = query_builder
        self._logger = get_logger(self.__class__.__name__)
        self._llm_cache = LLMResponseCache(logger=self._logger)

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
    def embedding_model(self) -> SentenceTransformer:
        """Lazy-loaded embedding model."""
        if self._embedding_model is None:
            self._embedding_model = SentenceTransformer(
                settings.embedding_model_path, device="cpu"
            )
        return self._embedding_model

    @property
    def query_builder(self) -> SearchQueryBuilder:
        """Lazy-loaded search query builder."""
        if self._query_builder is None:
            self._query_builder = SearchQueryBuilder(
                pool=get_connection_pool(),
                embedding_model=self.embedding_model,
                rrf_k_similarity=settings.rrf_k_similarity,
                rrf_k_chunk=settings.rrf_k_chunk,
                rrf_k_full_match=settings.rrf_k_full_match,
                rrf_k_partial_match=settings.rrf_k_partial_match,
                rrf_k_keyword=settings.rrf_k_keyword,
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

        try:
            llm_response = self.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": AIPrompts.get_structured_query_extraction_prompt(),
                    },
                    {
                        "role": "user",
                        "content": query,
                    },
                ],
                max_tokens=500,
                temperature=0.1,  # Low temperature for consistent structured output
                response_format={"type": "json_object"},
            )

            # Extract and parse the response content
            response_content = llm_response.choices[0].message.content

            # Cache the response if it's valid
            if response_content is not None:
                self._llm_cache.put(model_name, query, response_content)

            return self._parse_openai_response(response_content, query)

        except Exception as e:
            self._logger.error(f"OpenAI API error: {e}")
            return StructuredQueryData(
                intention=query, keywords=query.split() if query else [], filters={}
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
    ) -> List[EnhancedSearchResult]:
        """
        Execute the search using the structured query data.

        Args:
            search_data: Structured query information

        Returns:
            List of enhanced search results
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
            self._normalize_scores(results, search_data)

            return results

        except Exception as e:
            self._logger.error(f"Search execution error: {e}")
            return []

    def _execute_database_query(self, sql_query: str) -> List[EnhancedSearchResult]:
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
                    raw_results = cursor.fetchall()

                    self._logger.debug(f"Raw search results count: {len(raw_results)}")

                    # Get document details if we have results
                    if raw_results:
                        document_details = self._get_document_details(
                            cursor, raw_results
                        )
                        search_results = self._process_search_results(
                            raw_results, document_details
                        )

        except Exception as e:
            self._logger.error(f"Database query error: {e}")

        return search_results

    def _get_document_details(self, cursor, raw_results: List[dict]) -> List[dict]:
        """
        Get document details for the search results.

        Args:
            cursor: Database cursor
            raw_results: Raw search results from the query

        Returns:
            List of document details
        """
        dois = [row["doi"] for row in raw_results]

        # Use parameterized query for document details
        document_query = """
        SELECT doi, title, summary
        FROM document 
        WHERE doi = ANY(%s)
        """

        cursor.execute(document_query, [dois])
        return cursor.fetchall()

    def _normalize_scores(
        self, results: List[EnhancedSearchResult], query_data: StructuredQueryData
    ) -> None:
        """
        Normalize the scores of search results to a 0-1 range.

        Args:
            results: List of EnhancedSearchResult objects to normalize
        """
        if not results:
            return

        for result in results:
            self._logger.debug(
                f"Overall score (raw number from query): {result.overall_score}"
            )

            # Normalize individual scores to a 0-1 range
            result.similarity_score /= MaxScores.similarity_score_max
            result.chunk_similarity_score /= MaxScores.chunk_similarity_score_max
            result.keyword_score /= MaxScores.keyword_score_max
            result.full_match_score /= MaxScores.full_match_score_max
            result.partial_match_score /= MaxScores.partial_match_score_max

            # Normalize overall score based on the maximum possible score
            overall_max = MaxScores.overall_score_max(query_data)
            if overall_max > 0:
                result.overall_score /= overall_max
            else:
                result.overall_score = 0.0

            self._logger.debug(
                f"Dinamicly normalized score 0-1 range: {result.overall_score}"
            )

            # Boost Overall Score (to enhance low scores)
            # Apply logarithmic transformation to boost low scores while keeping them under 1
            # Formula: y = ln(b*x+1) / ln(b+1) where b controls the boost strength
            boost_factor = 4.0  # Adjust this to control how much boost to apply
            result.overall_score = math.log(
                boost_factor * result.overall_score + 1
            ) / math.log(boost_factor + 1)

            self._logger.debug(f"Overall score after boosting: {result.overall_score}")

    def _process_search_results(
        self, raw_results: List[dict], document_details: List[dict]
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
                        summary=doc.get("summary", ""),
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

    def _group_results_by_relevance(
        self, search_results: List[EnhancedSearchResult]
    ) -> dict:
        """
        Group search results into high, medium, and low relevance based on overall_score.

        Score ranges (0-1 scale where 1 is best):
        - High: 0.7 and above (highly relevant)
        - Medium: 0.4 to 0.7 (moderately relevant)
        - Low: below 0.4 (less relevant)

        Args:
            search_results: List of search results to group

        Returns:
            Dictionary with high, medium, low relevance groups
        """
        if not search_results:
            return {"high": [], "medium": [], "low": []}

        # Define absolute thresholds based on 0-1 score scale
        high_threshold = 0.7  # High relevance: 70% and above
        medium_threshold = 0.4  # Medium relevance: 40-70%
        # Low relevance: below 40%

        groups = {"high": [], "medium": [], "low": []}

        for result in search_results:
            if result.overall_score >= high_threshold:
                groups["high"].append(result)
            elif result.overall_score >= medium_threshold:
                groups["medium"].append(result)
            else:
                groups["low"].append(result)

        return groups

    async def explain_search_results(
        self, query: str, search_results: List[EnhancedSearchResult]
    ) -> AsyncGenerator[str, None]:
        """
        Generate a streaming explanation of search results using OpenAI.

        Args:
            query: The original search query
            search_results: List of search results to explain

        Yields:
            Streaming explanation content
        """
        model_name = settings.azure_openai_model_name

        # Group results by relevance
        relevance_groups = self._group_results_by_relevance(search_results)

        # Prepare the results data for the LLM
        results_summary = {
            "total_results": len(search_results),
            "relevance_groups": {
                "high": {
                    "count": len(relevance_groups["high"]),
                    "results": [
                        {
                            "title": result.title,
                            "doi": result.doi,
                            "summary": result.summary,
                            "overall_score": result.overall_score,
                            "similarity_score": result.similarity_score,
                            "chunk_similarity_score": result.chunk_similarity_score,
                            "full_match_score": result.full_match_score > 0,
                            "partial_match_score": result.partial_match_score,
                            "keyword_score": result.keyword_score,
                        }
                        for result in relevance_groups["high"][
                            :5
                        ]  # Limit to top 5 per group
                    ],
                },
                "medium": {
                    "count": len(relevance_groups["medium"]),
                    "results": [
                        {
                            "title": result.title,
                            "doi": result.doi,
                            "summary": result.summary,
                            "overall_score": result.overall_score,
                            "similarity_score": result.similarity_score,
                            "chunk_similarity_score": result.chunk_similarity_score,
                            "full_match_score": result.full_match_score > 0,
                            "partial_match_score": result.partial_match_score,
                            "keyword_score": result.keyword_score,
                        }
                        for result in relevance_groups["medium"][
                            :3
                        ]  # Limit to top 3 per group
                    ],
                },
                "low": {
                    "count": len(relevance_groups["low"]),
                    "results": [
                        {
                            "title": result.title,
                            "doi": result.doi,
                            "summary": result.summary,
                            "overall_score": result.overall_score,
                            "similarity_score": result.similarity_score,
                            "chunk_similarity_score": result.chunk_similarity_score,
                            "full_match_score": result.full_match_score > 0,
                            "partial_match_score": result.partial_match_score,
                            "keyword_score": result.keyword_score,
                        }
                        for result in relevance_groups["low"][
                            :2
                        ]  # Limit to top 2 per group
                    ],
                },
            },
        }

        # Create cache key from query and results summary
        results_json = json.dumps(results_summary, sort_keys=True)
        cache_key = f"{query}||{results_json}"

        # Check if we have a cached response
        cached_response = self._llm_cache.get(model_name, cache_key)
        if cached_response is not None:
            self._logger.debug(f"Using cached explanation for query: {query}")
            # Yield cached response as a single chunk
            yield cached_response
            return

        try:
            # Prepare the prompt with query and results
            user_content = f"""
            Original Query: "{query}"
            
            Search Results Summary:
            - Total results found: {results_summary['total_results']}
            - High relevance results: {results_summary['relevance_groups']['high']['count']}
            - Medium relevance results: {results_summary['relevance_groups']['medium']['count']}
            - Low relevance results: {results_summary['relevance_groups']['low']['count']}
            
            Results by Relevance Groups:
            {json.dumps(results_summary['relevance_groups'], indent=2)}
            
            Please explain these search results in relation to the user's query, organizing your explanation by relevance groups (high, medium, low).
            """

            stream = self.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": AIPrompts.get_result_explanation_prompt(),
                    },
                    {
                        "role": "user",
                        "content": user_content,
                    },
                ],
                max_tokens=800,
                temperature=0.3,  # Slightly higher temperature for more natural explanations
                stream=True,  # Enable streaming
            )

            # Stream the response and collect for caching
            collected_content = ""
            for chunk in stream:
                if hasattr(chunk, "choices") and len(chunk.choices) > 0:
                    content = getattr(chunk.choices[0].delta, "content", "")
                    if content:
                        collected_content += content
                        yield content
                    else:
                        self._logger.warning("Received empty content chunk from OpenAI")
                else:
                    self._logger.warning(
                        "Unexpected chunk format from OpenAI: %s", chunk
                    )

            self._logger.debug("OpenAI streaming completed")

            # Cache the complete response if it's valid
            if collected_content:
                self._llm_cache.put(model_name, cache_key, collected_content)

        except Exception as e:
            self._logger.error(f"OpenAI API error during explanation: {e}")
            fallback_explanation = self._create_fallback_explanation(
                query, len(search_results)
            )
            yield fallback_explanation

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
