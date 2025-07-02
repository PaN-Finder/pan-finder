import os
import json
from dotenv import load_dotenv

from fastapi import Depends
from sentence_transformers import SentenceTransformer
from openai import AzureOpenAI
from psycopg.rows import dict_row
from typing import cast, Any

from .database import get_db, get_db_connection
from .core.search_query_builder import SearchQueryBuilder


load_dotenv()

embedding_model = SentenceTransformer("/code/models/all-MiniLM-L12-v2", device="cpu")


def load_prompt_content():
    """Load the structured query extraction prompt from file."""
    prompt_path = os.path.join(os.path.dirname(__file__), "core", "prompts", "1_0_5.md")

    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


# Dependency for OpenAI client
def get_openai_client():
    """Dependency function to get OpenAI client."""
    api_url = os.getenv("AZURE_OPENAI_ENDPOINT")
    if not api_url:
        raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    if not api_key:
        raise ValueError("AZURE_OPENAI_API_KEY environment variable is required")
    return AzureOpenAI(
        api_key=api_key, azure_endpoint=api_url, api_version="2024-12-01-preview"
    )


# Dependency for FastAPI to get Query Builder
def get_builder():
    """Dependency function for FastAPI routes."""
    return SearchQueryBuilder(postgres_client=None, embedding_model=embedding_model)


async def search(
    query: str,
    builder: SearchQueryBuilder,
    openai_client: AzureOpenAI,
):
    """
    Search function that combines OpenAI processing with the search query builder.
    This function can be used in router endpoints.
    """
    # Load the structured query extraction prompt
    system_prompt = load_prompt_content()

    # Use OpenAI to extract structured information from the query
    try:
        llm_response = openai_client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
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
            print(f"Failed to parse OpenAI response as JSON: {e}")
            print(f"Raw response: {response_content}")

            # Fallback to simple processing if JSON parsing fails
            search_data = {
                "intention": response_content if response_content else query,
                "keywords": query.split() if query else [],
                "filters": {},
            }

    except Exception as e:
        print(f"OpenAI API error: {e}")

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
            # Set autocommit mode for read operations
            conn.autocommit = True

            with conn.cursor(row_factory=dict_row) as cursor:
                # Execute the search query
                # We need to use the cursor's execute method with proper typing
                # Cast to Any to bypass the type checker for the dynamically generated SQL
                cursor.execute(cast(Any, sql_query))
                raw_results = cursor.fetchall()

                print(f"Raw search results: {raw_results}")

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
        print(f"Database query error: {e}")
        search_results = []

    return {
        "original_query": query,
        "structured_query": search_data,
        "results": search_results,
        "total_results": len(search_results),
    }
