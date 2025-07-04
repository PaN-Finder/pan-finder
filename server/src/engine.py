import json
import time
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI
from psycopg.rows import dict_row
from typing import cast, Any, List, Optional
from pydantic import BaseModel

from .database import get_connection_pool, get_db_connection
from .core.search_query_builder import SearchQueryBuilder
from .core.prompts import QueryExtractionPrompts
from .logging import get_logger
from .config import get_settings

settings = get_settings()


class EnhancedSearchResult(BaseModel):
    doi: str
    title: str
    overall_score: float
    similarity_score: float
    chunk_similarity_score: float
    full_match_score: float
    partial_match_score: float
    keyword_score: float


class SearchResponse(BaseModel):
    original_query: str
    structured_query: dict
    results: List[EnhancedSearchResult]
    total_results: int


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
                pool=get_connection_pool(), embedding_model=self.embedding_model
            )
        return self._query_builder

    async def search(self, query: str) -> SearchResponse:
        """
        Search function that combines OpenAI processing with the search query builder.

        Args:
            query: The search query string

        Returns:
            SearchResponse containing search results and metadata
        """
        start_time = time.time()

        # Input validation
        if not query or not query.strip():
            self._logger.warning("Empty or whitespace-only query provided")
            return SearchResponse(
                original_query=query,
                structured_query={"intention": "", "keywords": [], "filters": {}},
                results=[],
                total_results=0,
            )

        # Extract structured information from the query
        extraction_start = time.time()
        search_data = await self._extract_structured_query(query)
        extraction_time = time.time() - extraction_start

        # Generate SQL query and execute search
        search_start = time.time()
        search_results = await self._execute_search(search_data)
        search_time = time.time() - search_start

        total_time = time.time() - start_time

        self._logger.info(
            f"Search completed - Query: '{query}', "
            f"Extraction Time: {extraction_time:.3f}s, "
            f"Search Time: {search_time:.3f}s, "
            f"Total Time: {total_time:.3f}s, "
            f"Results Found: {len(search_results)}"
        )

        return SearchResponse(
            original_query=query,
            structured_query=search_data,
            results=search_results,
            total_results=len(search_results),
        )

    async def _extract_structured_query(self, query: str) -> dict:
        """
        Extract structured information from the query using OpenAI.

        Args:
            query: The search query string

        Returns:
            Dictionary containing structured query information
        """
        try:
            llm_response = self.openai_client.chat.completions.create(
                model=settings.azure_openai_model_name,
                messages=[
                    {
                        "role": "system",
                        "content": QueryExtractionPrompts.get_structured_query_extraction_prompt(),
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

            return self._parse_openai_response(response_content, query)

        except Exception as e:
            self._logger.error(f"OpenAI API error: {e}")
            return self._create_fallback_query_data(query)

    def _parse_openai_response(
        self, response_content: Optional[str], query: str
    ) -> dict:
        """
        Parse the OpenAI response content into structured query data.

        Args:
            response_content: Raw response from OpenAI
            query: Original query for fallback

        Returns:
            Dictionary containing structured query information
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

            return search_data

        except (json.JSONDecodeError, ValueError) as e:
            self._logger.error(f"Failed to parse OpenAI response as JSON: {e}")
            self._logger.debug(f"Raw response: {response_content}")

            # Fallback to simple processing if JSON parsing fails
            return {
                "intention": response_content if response_content else query,
                "keywords": query.split() if query else [],
                "filters": {},
            }

    def _create_fallback_query_data(self, query: str) -> dict:
        """
        Create fallback query data when OpenAI processing fails.

        Args:
            query: Original query string

        Returns:
            Dictionary with basic query structure
        """
        return {
            "intention": query,
            "keywords": query.split() if query else [],
            "filters": {},
        }

    async def _execute_search(self, search_data: dict) -> List[EnhancedSearchResult]:
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
            sql_query = self.query_builder.build_query(search_data)
            query_build_time = time.time() - query_build_start
            self._logger.debug(
                f"SQL query building took {query_build_time:.3f} seconds"
            )

            # Execute the query
            db_execution_start = time.time()
            results = await self._execute_database_query(sql_query)
            db_execution_time = time.time() - db_execution_start
            self._logger.debug(
                f"Database execution took {db_execution_time:.3f} seconds"
            )

            return results

        except Exception as e:
            self._logger.error(f"Search execution error: {e}")
            return []

    async def _execute_database_query(
        self, sql_query: str
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
        SELECT doi, title
        FROM document 
        WHERE doi = ANY(%s)
        """

        cursor.execute(document_query, [dois])
        return cursor.fetchall()

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


@lru_cache()
def get_search_engine() -> SearchEngine:
    """Get a cached SearchEngine instance."""
    return SearchEngine()


async def search(query: str) -> SearchResponse:
    """
    Convenience function for backward compatibility.

    Args:
        query: The search query string

    Returns:
        SearchResponse containing search results and metadata
    """
    engine = get_search_engine()
    return await engine.search(query)
