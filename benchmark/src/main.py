import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from openai import AzureOpenAI
from sentence_transformers import SentenceTransformer

from plotting import (
    plot_avarage_scores_per_dataset as plot_average_scores_per_dataset,  # alias for readability
    plot_overall_changes,
    plot_score_distribution_boxplot,
)

# Make server code importable without modifying server files
server_dir = Path(__file__).parent.parent.parent / "server"
sys.path.insert(0, str(server_dir))

from src.core.search_query_builder import SearchQueryBuilder
from src.db.connection import get_connection_pool, get_db_connection
from src.config import get_settings

logging.getLogger("benchmark")

# Global cache for LLM responses (loaded from file)
llm_response_cache: Dict[str, str] = {}


def root_dir() -> Path:
    """Project root directory."""
    return Path(__file__).resolve().parents[2]


# Define cache file path
CACHE_FILE_PATH = root_dir() / "benchmark" / "cache" / "llm_cache.json"
settings = get_settings()


def load_system_prompt(model: str, version: str) -> str:
    filepath = root_dir() / "benchmark" / "prompts" / model / version
    return filepath.read_text()


# Load prompt globally
llm_model = "gpt-4.1-mini"
system_prompt_version = "1_0_7.md"
extract_prompt = load_system_prompt(llm_model, system_prompt_version)


def load_llm_cache() -> None:
    """Load the LLM response cache from disk (if present)."""
    global llm_response_cache
    if CACHE_FILE_PATH.exists():
        try:
            with open(CACHE_FILE_PATH, "r") as f:
                llm_response_cache = json.load(f)
            logging.info("LLM cache loaded from %s", str(CACHE_FILE_PATH))
        except (json.JSONDecodeError, IOError) as e:
            logging.info("Error loading LLM cache: %s. Starting with empty cache.", e)
            llm_response_cache = {}
    else:
        logging.info("LLM cache file not found. Starting with empty cache.")
        llm_response_cache = {}


def save_llm_cache() -> None:
    """Persist the LLM response cache to disk."""
    try:
        # Ensure parent directory exists
        CACHE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE_PATH, "w") as f:
            json.dump(llm_response_cache, f, indent=2)
    except IOError as e:
        logging.info("Error saving LLM cache: %s", e)


def load_rrf_score_k_values() -> List[Dict[str, Any]]:
    filepath = root_dir() / "benchmark" / "rrf_score_k_values_matrix.json"
    return json.loads(filepath.read_text())


def load_datasets() -> Dict[str, List[Dict[str, Any]]]:
    """Load all query datasets, returning parsed JSON per file name."""
    base_dir = root_dir() / "benchmark" / "queries"
    datasets: Dict[str, List[Dict[str, Any]]] = {}
    for filepath in sorted(base_dir.glob("*.json")):
        datasets[filepath.name] = json.loads(filepath.read_text())
    return datasets


def extract_json_from_response(text: str) -> str:
    """Extract JSON object from a text blob that may include code fences.

    Note: With response_format=json_object this should be unnecessary, but kept
    minimal for resilience when reading existing cache entries.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Response does not contain a valid JSON object")
    return text[start : end + 1]


def get_openai_client_instance() -> AzureOpenAI:
    """Returns a singleton instance of the AzureOpenAI client."""
    if not hasattr(get_openai_client_instance, "_client"):
        get_openai_client_instance._client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
    return get_openai_client_instance._client


def get_llm_response(prompt: str, query: str, **kwargs) -> str | None:
    """Get response from OpenAI API, using file-backed cache if available."""

    cache_key = f"{llm_model}_{system_prompt_version}|{query}|{json.dumps(kwargs, sort_keys=True)}"
    if cache_key in llm_response_cache:
        logging.info("LLM Cache Hit: %s", query)
        return llm_response_cache[cache_key]

    logging.info("LLM Cache Miss: %s", query)
    response = get_openai_client_instance().chat.completions.create(
        model=llm_model,
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
            {"role": "user", "content": query},
        ],
        max_tokens=500,
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    answer: str | None = response.choices[0].message.content

    if answer is not None:
        llm_response_cache[cache_key] = answer
        save_llm_cache()  # Save cache after adding a new entry
    return answer


def process_query(
    query_obj: Dict[str, Any], doi: str, builder: SearchQueryBuilder
) -> Tuple[float, float, float, float, float, float, float, float]:
    query_text = query_obj.get("query", "").strip()
    if not query_text:
        raise ValueError("Query text is empty")

    min_position: int = int(query_obj.get("min_position", 0))

    response = get_llm_response(
        extract_prompt, query_text, temperature=0, max_tokens=500
    )
    if response is None:
        raise ValueError("LLM response is None")

    logging.debug("DOI: %s", doi)
    logging.info("Query: %s", query_text)

    # Prefer direct JSON when provided, fallback to extracting
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        data = json.loads(extract_json_from_response(response))

    query = builder.build_query(data)
    try:
        logging.debug("SQL Query: %s", query.as_string())
    except Exception:
        logging.debug("SQL Query constructed (requires DB to render string)")

    with get_db_connection() as conn, conn.cursor() as cursor:
        start_time = time.time()
        cursor.execute(query)
        results = cursor.fetchall()
        elapsed_time = time.time() - start_time

        df = pd.DataFrame(
            results,
            columns=[
                "Doi",
                "Overall Score",
                "Similarity Score",
                "Chunk Similarity Score",
                "Full Match Score",
                "Partial Match Score",
                "Keyword Score",
            ],
        ).astype(
            {
                "Overall Score": float,
                "Similarity Score": float,
                "Chunk Similarity Score": float,
                "Full Match Score": float,
                "Partial Match Score": float,
                "Keyword Score": float,
            }
        )

    logging.info("%s", df.to_string(index=True))

    # Find the position of target DOI
    position = next((i for i, row in enumerate(results) if row[0] == doi), -1)

    # Score: full credit if within min_position, then linear decay up to 20 ranks, clamped at 0
    if position < 0:
        score = 0.0
    else:
        offset = max(0, position - min_position)
        score = max(0.0, 1.0 - (offset / 20.0))

    if position != -1:
        (
            overall,
            sim_score,
            chunk_score,
            full_match_score,
            partial_match_score,
            keyword_score,
        ) = (
            float(results[position][1]),
            float(results[position][2]),
            float(results[position][3]),
            float(results[position][4]),
            float(results[position][5]),
            float(results[position][6]),
        )
    else:
        overall = sim_score = chunk_score = full_match_score = partial_match_score = (
            keyword_score
        ) = 0.0

    logging.info(
        "Score: %.3f | Position: %d | Min: %d | Runtime: %.3fs",
        score,
        position,
        min_position,
        elapsed_time,
    )

    return (
        score,
        overall,
        elapsed_time,
        sim_score,
        chunk_score,
        full_match_score,
        partial_match_score,
        keyword_score,
    )


def process_document(
    doc: Dict[str, Any], builder: SearchQueryBuilder
) -> Tuple[List[float], List[float], List[Dict[str, float]]]:
    doi = doc.get("doi", "N/A")
    scores = []
    runtimes = []
    breakdowns = []  # to store detailed score breakdown per query
    for query_obj in doc.get("queries", []):
        (
            score,
            overall,
            runtime,
            sim_score,
            chunk_score,
            full_match_score,
            partial_match_score,
            keyword_score,
        ) = process_query(query_obj, doi, builder)
        scores.append(score)
        runtimes.append(runtime)
        breakdowns.append(
            {
                "overall": overall,
                "similarity": sim_score,
                "chunk_score": chunk_score,
                "full_match_score": full_match_score,
                "partial_match_score": partial_match_score,
                "keyword": keyword_score,
            }
        )
    return scores, runtimes, breakdowns


def process_dataset(
    dataset_name: str, dataset: List[Dict[str, Any]], builder: SearchQueryBuilder
) -> Tuple[List[float], List[float], List[Dict[str, float]]]:
    logging.info("Dataset: %s", dataset_name)
    dataset_scores = []
    dataset_runtimes = []
    dataset_breakdowns = []
    for doc in dataset:
        scores, runtimes, breakdowns = process_document(doc, builder)
        dataset_scores.extend(scores)
        dataset_runtimes.extend(runtimes)
        dataset_breakdowns.extend(breakdowns)
    return dataset_scores, dataset_runtimes, dataset_breakdowns


def get_sentence_transformer(model: str = "all-MiniLM-L12-v2") -> SentenceTransformer:
    model_path = root_dir() / "models" / model
    return SentenceTransformer(str(model_path), device="cpu")


def main() -> None:
    # Basic logging setup for the benchmark script
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load cache and inputs
    load_llm_cache()
    rrf_score_k_values = load_rrf_score_k_values()
    datasets = load_datasets()
    sentence_transformer = get_sentence_transformer()

    all_test_results: List[Dict[str, Any]] = []
    overall_test_metrics: Dict[str, Dict[str, float]] = {}
    all_scores_by_test_config: Dict[str, List[float]] = {}

    # Run each RRF configuration across all datasets
    for rrf_config in rrf_score_k_values:
        test_name = rrf_config.get("test_name", "unknown_test")
        logging.info("=== Test: %s ===", test_name)
        logging.info("RRF k-values: %s", rrf_config)

        builder = SearchQueryBuilder(
            sentence_transformer=sentence_transformer,
            pool=get_connection_pool(),
            rrf_k_similarity=rrf_config.get("rrf_k_similarity", 60),
            rrf_k_chunk=rrf_config.get("rrf_k_chunk", 60),
            rrf_k_full_match=rrf_config.get("rrf_k_full_match", 60),
            rrf_k_partial_match=rrf_config.get("rrf_k_partial_match", 60),
            rrf_k_keyword=rrf_config.get("rrf_k_keyword", 60),
            logger=logging.getLogger("search_query_builder"),
        )

        test_all_scores: List[float] = []
        test_all_runtimes: List[float] = []
        test_total_queries = 0

        for dataset_name, dataset in datasets.items():
            ds_scores, ds_runtimes, ds_breakdowns = process_dataset(
                dataset_name, dataset, builder
            )

            # Aggregate per dataset
            ds_total_queries = len(ds_scores)
            ds_avg_score = (
                (sum(ds_scores) / ds_total_queries) if ds_total_queries else 0.0
            )

            all_test_results.append(
                {
                    "test_name": test_name,
                    "dataset_name": dataset_name.replace(".json", ""),
                    "avg_score": round(ds_avg_score, 4),
                    "avg_score_percent": round(ds_avg_score * 100.0, 2),
                }
            )

            test_total_queries += ds_total_queries
            test_all_scores.extend(ds_scores)
            test_all_runtimes.extend(ds_runtimes)

        avg_score = (
            (sum(test_all_scores) / test_total_queries) if test_total_queries else 0.0
        )
        avg_runtime = (
            (sum(test_all_runtimes) / test_total_queries) if test_total_queries else 0.0
        )

        logging.info(
            "Overall avg score: %.4f | avg runtime: %.3fs", avg_score, avg_runtime
        )

        overall_test_metrics[test_name] = {
            "avg_score": avg_score * 100.0,
            "avg_runtime": avg_runtime,
        }

        if test_all_scores:
            all_scores_by_test_config[test_name] = test_all_scores

    results_dir = root_dir() / "benchmark" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_scores_data_path = results_dir / f"raw_scores_by_test_config_{timestamp}.json"
    try:
        with open(raw_scores_data_path, "w") as f:
            json.dump(all_scores_by_test_config, f, indent=2)
    except IOError as e:
        logging.info("Error saving raw scores data: %s", e)

    plot_score_distribution_boxplot(
        raw_scores_data_path,
        results_dir / f"score_distribution_boxplot_{timestamp}.png",
    )

    results_df = pd.DataFrame(all_test_results)
    plot_average_scores_per_dataset(
        results_df,
        overall_test_metrics,
        results_dir / f"average_scores_per_dataset_{timestamp}.png",
    )
    results_df.to_csv(
        results_dir / f"results_{timestamp}.csv",
        index=False,
        quoting=csv.QUOTE_NONNUMERIC,
    )

    plot_overall_changes(results_dir, results_dir / "overall_changes.png")


if __name__ == "__main__":
    main()
