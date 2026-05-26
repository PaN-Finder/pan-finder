import csv
import json
import logging
import os
import time
from datetime import datetime
from typing import Any

import pandas as pd
from helper import get_llm_client, get_sentence_transformer, load_system_prompt
from paths import benchmark_dir, include_server_modules
from plotting import (
    plot_average_scores_per_dataset,
    plot_overall_changes,
    plot_score_distribution_boxplot,
)

include_server_modules()
# ruff: noqa: E402
from src.config import get_settings
from src.core.ai.llm_client import LLMClient, LLMMessage
from src.core.search_query_builder import SearchQueryBuilder
from src.db.connection import get_database_connection, get_database_pool

logging.getLogger("multi_config_evaluator")

# Define cache file path
CACHE_FILE_PATH = benchmark_dir() / "cache" / "llm_cache.json"
settings = get_settings()

llm_model = "gpt-4.1-mini"
system_prompt_version = "1_0_11.md"

# Global LLM client with file caching
llm_client: LLMClient = get_llm_client(llm_model)

# Load prompt globally
extract_prompt = load_system_prompt(llm_model, system_prompt_version)


def load_rrf_score_k_values() -> list[dict[str, Any]]:
    filepath = benchmark_dir() / "rrf_score_k_values_matrix.json"
    configs: list[dict[str, Any]] = json.loads(filepath.read_text())
    disabled_configs = [
        config.get("test_name", "unknown_test")
        for config in configs
        if config.get("disabled", False)
    ]
    if disabled_configs:
        logging.info("Skipping disabled RRF configs: %s", ", ".join(disabled_configs))
    return [config for config in configs if not config.get("disabled", False)]


def load_datasets() -> dict[str, list[dict[str, Any]]]:
    """Load all query datasets, returning parsed JSON per file name."""
    base_dir = benchmark_dir() / "queries" / "synthetic"
    datasets: dict[str, list[dict[str, Any]]] = {}
    for filepath in sorted(base_dir.glob("*.json")):
        datasets[filepath.name] = json.loads(filepath.read_text())
    return datasets


async def get_llm_response(prompt: str, query: str, **kwargs) -> str | None:
    """Get response from LLM using LLMClient with built-in caching."""
    messages = [
        LLMMessage(role="system", content=prompt),
        LLMMessage(role="user", content=query),
    ]

    # Create metadata for this specific cache entry
    cache_metadata = {
        "llm_model": llm_model,
        "system_prompt_version": system_prompt_version,
        **kwargs,
    }

    request = llm_client.create_request(
        messages=messages,
        max_tokens=kwargs.get("max_tokens", 500),
        temperature=kwargs.get("temperature", 0.1),
        response_format={"type": "json_object"},
        cache_metadata=cache_metadata,
    )

    try:
        response = await llm_client.complete(request)

        return response.content
    except Exception as e:
        logging.error("LLM request failed: %s", e)
        return None


async def process_query(
    query_obj: dict[str, Any], doi: str, builder: SearchQueryBuilder
) -> tuple[float, float, float, float, float, float, float, float]:
    query_text = query_obj.get("query", "").strip()
    if not query_text:
        raise ValueError("Query text is empty")

    min_position: int = int(query_obj.get("min_position", 0))

    response = await get_llm_response(
        extract_prompt, query_text, temperature=0, max_tokens=500
    )
    if response is None:
        raise ValueError("LLM response is None")

    logging.debug("DOI: %s", doi)
    logging.info("Query: %s", query_text)

    data = json.loads(response)
    query, subqueries_used = builder.build_query(data)
    logging.debug("Activated subqueries: %s", subqueries_used)
    try:
        logging.debug("SQL Query: %s", query.as_string())
    except Exception:
        logging.debug("SQL Query constructed (requires DB to render string)")

    with get_database_connection() as conn, conn.cursor() as cursor:
        start_time = time.time()
        # print(query.as_string())
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


async def process_document(
    doc: dict[str, Any], builder: SearchQueryBuilder
) -> tuple[list[float], list[float], list[dict[str, float]]]:
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
        ) = await process_query(query_obj, doi, builder)
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


async def process_dataset(
    dataset_name: str, dataset: list[dict[str, Any]], builder: SearchQueryBuilder
) -> tuple[list[float], list[float], list[dict[str, float]]]:
    logging.info("Dataset: %s", dataset_name)
    dataset_scores = []
    dataset_runtimes = []
    dataset_breakdowns = []
    for doc in dataset:
        scores, runtimes, breakdowns = await process_document(doc, builder)
        dataset_scores.extend(scores)
        dataset_runtimes.extend(runtimes)
        dataset_breakdowns.extend(breakdowns)
    return dataset_scores, dataset_runtimes, dataset_breakdowns


async def process_rrf_config(
    rrf_config: dict[str, Any],
    datasets: dict[str, list[dict[str, Any]]],
    sentence_transformer,
) -> tuple[str, list[dict[str, Any]], dict[str, float], list[float]]:
    """Process a single RRF configuration across all datasets."""
    test_name = rrf_config.get("test_name", "unknown_test")
    logging.info("=== Test: %s ===", test_name)
    logging.info("RRF k-values: %s", rrf_config)

    builder = SearchQueryBuilder(
        sentence_transformer=sentence_transformer,
        pool=get_database_pool("default"),
        rrf_k_document=rrf_config.get("rrf_k_document", 60),
        rrf_k_chunk=rrf_config.get("rrf_k_chunk", 60),
        rrf_k_conditions_full=rrf_config.get("rrf_k_conditions_full", 60),
        rrf_k_conditions_partial=rrf_config.get("rrf_k_conditions_partial", 60),
        rrf_k_keywords=rrf_config.get("rrf_k_keywords", 60),
        value_vector_keys=settings.value_vector_keys,
        logger=logging.getLogger("search_query_builder"),
    )

    test_results: list[dict[str, Any]] = []
    test_all_scores: list[float] = []
    test_all_runtimes: list[float] = []
    test_total_queries = 0

    for dataset_name, dataset in datasets.items():
        ds_scores, ds_runtimes, ds_breakdowns = await process_dataset(
            dataset_name, dataset, builder
        )

        # Aggregate per dataset
        ds_total_queries = len(ds_scores)
        ds_avg_score = (sum(ds_scores) / ds_total_queries) if ds_total_queries else 0.0

        test_results.append(
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

    logging.info("Overall avg score: %.4f | avg runtime: %.3fs", avg_score, avg_runtime)

    test_metrics = {
        "avg_score": avg_score * 100.0,
        "avg_runtime": avg_runtime,
    }

    return test_name, test_results, test_metrics, test_all_scores


async def main() -> None:
    # Basic logging setup for the benchmark script
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)

    # Load inputs (LLM client will handle its own caching)
    rrf_score_k_values = load_rrf_score_k_values()
    datasets = load_datasets()
    sentence_transformer = get_sentence_transformer()

    all_test_results: list[dict[str, Any]] = []
    overall_test_metrics: dict[str, dict[str, float]] = {}
    all_scores_by_test_config: dict[str, list[float]] = {}

    # Run all RRF configurations in parallel
    tasks = [
        process_rrf_config(rrf_config, datasets, sentence_transformer)
        for rrf_config in rrf_score_k_values
    ]

    results = await asyncio.gather(*tasks)

    # Aggregate results from all configurations
    for test_name, test_results, test_metrics, test_all_scores in results:
        all_test_results.extend(test_results)
        overall_test_metrics[test_name] = test_metrics
        if test_all_scores:
            all_scores_by_test_config[test_name] = test_all_scores

    results_dir = benchmark_dir() / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_scores_data_path = results_dir / f"raw_scores_by_test_config_{timestamp}.json"
    try:
        with open(raw_scores_data_path, "w") as f:
            json.dump(all_scores_by_test_config, f, indent=2)
    except OSError as e:
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
    import asyncio

    asyncio.run(main())
