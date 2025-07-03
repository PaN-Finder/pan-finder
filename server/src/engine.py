import json
from fastapi import Depends
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI
from psycopg.rows import dict_row
from typing import cast, Any, Dict

from .database import get_connection_pool, get_db_connection
from .core.search_query_builder import SearchQueryBuilder
from .core.prompts import QueryExtractionPrompts
from .logging_config import get_logger
from .config import get_settings

logger = get_logger(__name__)
settings = get_settings()


@lru_cache()
def get_openai_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )


@lru_cache()
def get_embedding_model() -> SentenceTransformer:
    """Get the embedding model for text similarity calculations."""
    return SentenceTransformer(settings.embedding_model_path, device="cpu")


@lru_cache()
def get_builder(
    pool=Depends(get_connection_pool),
    embedding_model: SentenceTransformer = Depends(get_embedding_model),
) -> SearchQueryBuilder:
    """Get the search query builder with injected dependencies."""
    return SearchQueryBuilder(pool=pool, embedding_model=embedding_model)


async def search(
    query: str,
    builder: SearchQueryBuilder = Depends(get_builder),
    openai_client: AzureOpenAI = Depends(get_openai_client),
) -> Dict[str, Any]:
    """
    Search function that combines OpenAI processing with the search query builder.
    This function can be used in router endpoints.

    Args:
        query: The search query string
        builder: SearchQueryBuilder instance for generating SQL queries
        openai_client: Azure OpenAI client for query processing

    Returns:
        Dictionary containing search results and metadata
    """
    # Input validation
    if not query or not query.strip():
        logger.warning("Empty or whitespace-only query provided")
        return {
            "original_query": query,
            "structured_query": {"intention": "", "keywords": [], "filters": {}},
            "results": [],
            "total_results": 0,
            "error": "Query cannot be empty",
        }

    # Use OpenAI to extract structured information from the query
    try:
        llm_response = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": QueryExtractionPrompts.get_structured_query_extraction_prompt(),
                },
                {
                    "role": "user",
                    "content": f"Please analyze this query and return the structured JSON: {query}",
                },
            ],
            max_tokens=500,
            temperature=0.1,  # Low temperature for consistent structured output
            response_format={"type": "json_object"},
        )

        # Extract the response content
        response_content = llm_response.choices[0].message.content

        # Parse the JSON response
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

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse OpenAI response as JSON: {e}")
            logger.debug(f"Raw response: {response_content}")

            # Fallback to simple processing if JSON parsing fails
            search_data = {
                "intention": response_content if response_content else query,
                "keywords": query.split() if query else [],
                "filters": {},
            }

    except Exception as e:
        logger.error(f"OpenAI API error: {e}")

        # Fallback to simple processing if OpenAI fails
        search_data = {
            "intention": query,
            "keywords": query.split() if query else [],
            "filters": {},
        }

    # Use the builder to generate the SQL query
    sql_query = builder.build_query(search_data)

    # Execute the query using the database client
    search_results = []
    try:
        with get_db_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cursor:
                # Execute the search query
                # We need to use the cursor's execute method with proper typing
                # Cast to Any to bypass the type checker for the dynamically generated SQL
                cursor.execute(cast(Any, sql_query))
                raw_results = cursor.fetchall()

                logger.debug(f"Raw search results count: {len(raw_results)}")

                # Initialize document_details to avoid variable scope issues
                document_details = []

                # Get document details for each DOI returned by the search
                if raw_results:
                    dois = [row["doi"] for row in raw_results]

                    # Use parameterized query for document details
                    document_query = """
                    SELECT doi, title
                    FROM document 
                    WHERE doi = ANY(%s)
                    """

                    cursor.execute(document_query, [dois])
                    document_details = cursor.fetchall()

                # Create a mapping of DOI to document details
                doc_map = {doc["doi"]: doc for doc in document_details}

                # Combine search scores with document details
                for result in raw_results:
                    doi = result["doi"]
                    if doi in doc_map:
                        doc = doc_map[doi]
                        search_results.append(
                            {
                                "doi": doi,
                                "title": doc.get("title", ""),
                                "overall_score": float(result.get("overall_score", 0)),
                                "similarity_score": float(
                                    result.get("similarity_score", 0)
                                ),
                                "chunk_similarity_score": float(
                                    result.get("chunk_similarity_score", 0)
                                ),
                                "full_match_score": float(
                                    result.get("full_match_score", 0)
                                ),
                                "partial_match_score": float(
                                    result.get("partial_match_score", 0)
                                ),
                                "keyword_score": float(result.get("keyword_score", 0)),
                            }
                        )

    except Exception as e:
        # Log the error and return empty results
        logger.error(f"Database query error: {e}")
        search_results = []

    return {
        "original_query": query,
        "structured_query": search_data,
        "results": search_results,
        "total_results": len(search_results),
    }
