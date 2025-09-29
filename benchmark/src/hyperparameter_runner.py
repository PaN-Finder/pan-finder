import json
import time
import argparse
import pandas as pd
from datetime import datetime
import uuid
import os
import logging

from helper import get_sentence_transformer, load_system_prompt
from paths import include_server_modules
from multi_config_evaluator import get_llm_response
from benchmarks_metrics_at_1k import metrics_at_1k

include_server_modules()
from src.core.search_query_builder import SearchQueryBuilder
from src.db.connection import (
    get_database_pool,
    get_database_connection,
    register_database,
    DatabaseConfig,
)

logging.getLogger("hyperparameter_runner")


async def process_test_pair(
    hyperparameters: dict,
    system_prompt: str,
    user_prompt: str,
    doi: str,
    builder: SearchQueryBuilder,
) -> dict:

    start_query_components_extraction = time.time()
    response = await get_llm_response(
        system_prompt,
        user_prompt,
        temperature=hyperparameters["application"]["openai"]["temperature"],
        max_tokens=hyperparameters["application"]["openai"]["max_tokens"],
    )

    if response is None:
        raise ValueError("LLM response is None")

    user_prompt_components = json.loads(response)

    end_query_components_extraction = time.time()

    logging.info("DOI: %s", doi)
    logging.info("User Prompt: %s", user_prompt)
    logging.info("LLM Response: %s", response)
    logging.info("Formatted Data %s", user_prompt_components)

    start_query_building = time.time()
    query = builder.build_query(user_prompt_components)
    end_query_building = time.time()
    logging.info("SQL Query %s", query.as_string())

    start_query_execution = time.time()
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
    end_query_execution = time.time()

    dfResults = pd.DataFrame(
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

    logging.info("Results")
    logging.info(dfResults.to_string(index=True))

    index = next((i for i, result in enumerate(results) if result[0] == doi), -1)
    rank = index + 1
    logging.info(f"Rank: {rank} (Index: {index})")
    overall_score = results[index][1] if index != -1 else 0

    extraction_time = (
        end_query_components_extraction - start_query_components_extraction
    )
    building_time = end_query_building - start_query_building
    query_time = end_query_execution - start_query_execution
    run_time = extraction_time + building_time + query_time

    logging.info(f"Overall Score: {overall_score}, Total Run Time: {run_time:.3f}s\n\n")
    return {
        "rank": rank,
        "overall_score": overall_score,
        "components": user_prompt_components,
        "extraction_time": extraction_time,
        "building_time": building_time,
        "query_time": query_time,
        "run_time": run_time,
        "query": query,
        "results_set": dfResults.to_json(),
    }


def compute_test_pair_metrics(
    hyperparameters: dict,
    processed_data: dict,
    test_pair,
) -> dict:
    metrics_values = {
        name: metrics_at_1k[metric](
            r=processed_data["rank"],
            k=hyperparameters["results_set"]["results_set_size"],
            e=test_pair[3] if test_pair[3] > 0 else 1,
        )
        for name, metric in hyperparameters["metrics"]["test_pair_metrics"].items()
    }
    return metrics_values


def compute_and_insert_run_metrics(
    run_id: str,
    hyperparameters: dict,
):
    for name, metric in hyperparameters["metrics"]["run_metrics"].items():
        test_pair_sets = metric["test_pair_set"]

        if test_pair_sets == "all_sets":
            test_pair_sets = ["comprehensive", "synthetic", "expert"]
        elif not isinstance(test_pair_sets, list):
            test_pair_sets = [test_pair_sets]

        for test_pair_set in test_pair_sets:
            is_comprehensive = test_pair_set == "comprehensive"
            metric_prefix = "c" if is_comprehensive else test_pair_set[0:1]

            sql = """
                INSERT INTO run_metrics_values (id, runId, metric, value)
                SELECT %s, \
                       %s, \
                       %s, \
                       AVG(a.value)
                FROM test_pair_metrics_values AS a
                {joins}
                WHERE a.metric = %s AND a.runId = %s
                {additional_where} \
            """

            joins = ""
            additional_where = ""
            parameters = [
                str(uuid.uuid4()),
                run_id,
                metric_prefix + name,
                metric["test_pair_metric"],
                run_id,
            ]

            if not is_comprehensive:
                joins = """
                    JOIN benchmarks_run_test AS b ON b.testId = a.testId
                    JOIN test_pairs AS c ON c.tpId = b.tpId
                """
                additional_where = "AND c.type = 'positive' AND c.source = %s"
                parameters.append(test_pair_set)

            # Final SQL formatting with conditional parts
            final_sql = sql.format(joins=joins, additional_where=additional_where)

            with get_database_connection("pan-finder-benchmarks") as conn:
                with conn.cursor() as cursor:
                    cursor.execute(final_sql, parameters)
                    conn.commit()


def insert_test_pair_metrics(
    run_id: str,
    test_id: str,
    test_pair_metrics: dict,
):
    for metric in test_pair_metrics:
        with get_database_connection("pan-finder-benchmarks") as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO test_pair_metrics_values (id, runId, testId, metric, value)
                        VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        run_id,
                        test_id,
                        metric,
                        test_pair_metrics[metric],
                    ),
                )
                conn.commit()


def insert_test_pair_test(
    run_id,
    tp_id,
    intention,
    keywords,
    filters,
    rank,
    run_time,
    extraction_time,
    building_time,
    query_time,
    sql_query,
    results_set,
) -> str:
    test_id = str(uuid.uuid4())
    with get_database_connection("pan-finder-benchmarks") as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO benchmarks_run_test (testId, runId, tpId, intention, keywords, filters, rank, runTime, extractionTime, buildingTime, queryTime, sqlQuery, resultsSet)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    test_id,
                    run_id,
                    tp_id,
                    intention,
                    keywords,
                    filters,
                    rank,
                    run_time,
                    extraction_time,
                    building_time,
                    query_time,
                    sql_query.as_string(),
                    results_set,
                ),
            )
            conn.commit()
    return test_id


async def main(hyperparameters: dict):
    # Setup multiple database connections (additional benchmark db)
    benchmarks_db_config = DatabaseConfig(
        conninfo=os.getenv(
            "BENCHMARKS_DATABASE_URL",
            "postgresql://usr:pwd@localhost:5432/pan-finder-benchmarks",
        ),
        min_size=1,
        max_size=3,
        application_name="benchmark",
    )
    register_database("pan-finder-benchmarks", benchmarks_db_config)

    # Load prompt globally
    system_prompt = load_system_prompt(
        hyperparameters["application"]["system_prompt"]["model"],
        hyperparameters["application"]["system_prompt"]["version"],
    )

    # instantiate sentence transformer
    sentence_transformer = get_sentence_transformer(
        hyperparameters["application"]["embeddings"]["model"],
    )

    # Instantiate builder with the current configuration
    builder = SearchQueryBuilder(
        sentence_transformer=sentence_transformer,
        pool=get_database_pool("default"),
        rrf_k_similarity=hyperparameters["score_weights"].get("rrf_k_similarity", 60),
        rrf_k_chunk=hyperparameters["score_weights"].get("rrf_k_chunk", 60),
        rrf_k_full_match=hyperparameters["score_weights"].get("rrf_k_full_match", 60),
        rrf_k_partial_match=hyperparameters["score_weights"].get(
            "rrf_k_partial_match", 60
        ),
        rrf_k_keyword=hyperparameters["score_weights"].get("rrf_k_keyword", 60),
        # results_set_size=hyperparameters["results_set"].get("results_set_size", 20),
    )

    # generate a unique for this run
    run_id = str(uuid.uuid4())
    logging.info(f"- Running Benchmarks run: {run_id} ---")

    # insert benchmarks run
    with get_database_connection("pan-finder-benchmarks") as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO benchmarks_run (runId, startdate, hyperparameters)
                VALUES (%s, %s, %s)
                """,
                (
                    run_id,
                    datetime.now().isoformat(),
                    json.dumps(hyperparameters),
                ),
            )
            conn.commit()

        with conn.cursor() as tp_cursor:
            # execute query
            test_pairs_set = hyperparameters["test_pairs"].get(
                "test_pair_set", "comprehensive"
            )
            query = """
                SELECT tpId, userPrompt, targetDoi, expectedRank, promptId, expertName, groupId, source, type
                FROM test_pairs WHERE type = 'positive'
            """
            params = []
            if test_pairs_set in ["synthetic", "expert"]:
                query += f" AND source = %s"
                params.append(test_pairs_set)
            tp_cursor.execute(query, params)

            # loop on all the tests
            test_pair_counter = 1
            for test_pair in tp_cursor:
                test_pair_id = str(test_pair[0])
                logging.info(
                    f"--- Running Test Pair {test_pair_counter}: {test_pair_id} ---"
                )

                processed_data = await process_test_pair(
                    hyperparameters,
                    system_prompt,
                    test_pair[1],
                    test_pair[2],
                    builder,
                )

                tp_id = insert_test_pair_test(
                    run_id,
                    test_pair_id,
                    processed_data["components"]["intention"],
                    processed_data["components"]["keywords"],
                    json.dumps(processed_data["components"]["filters"]),
                    processed_data["rank"],
                    processed_data["run_time"],
                    processed_data["extraction_time"],
                    processed_data["building_time"],
                    processed_data["query_time"],
                    processed_data["query"],
                    processed_data["results_set"],
                )
                # compute all test pair metrics
                test_pair_metrics = compute_test_pair_metrics(
                    hyperparameters,
                    processed_data,
                    test_pair,
                )

                # insert test metrics
                insert_test_pair_metrics(
                    run_id,
                    tp_id,
                    test_pair_metrics,
                )

                test_pair_counter += 1

            # calculate run metrics
            compute_and_insert_run_metrics(
                run_id,
                hyperparameters,
            )

        # mark benchmarks run completed
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE benchmarks_run
                SET enddate = %s
                WHERE runId = %s
                """,
                (datetime.now().isoformat(), run_id),
            )
            conn.commit()

    logging.info(f"- Benchmarks run {run_id} completed ---")


if __name__ == "__main__":

    # Create ArgumentParser object
    parser = argparse.ArgumentParser(description="PaN-Finder single run benchmark")

    # Define command-line options and arguments
    parser.add_argument(
        "-p",
        "--hp",
        "--hyperparameters",
        "--hyperparameters-file",
        dest="hyperparameters",
        type=str,
        help="File containing the hyperparameters run in json format",
        required=True,
    )

    # Parse arguments
    args = parser.parse_args()

    # Access arguments
    logging.info(f"Hyperparameters file: {args.hyperparameters}")
    logging.info("Loading hyperparameters...")
    with open(args.hyperparameters) as json_file:
        hyperparameters = json.load(json_file)
    logging.info("Hyperparameters loaded")
    logging.info("Hyperparameters: ")
    logging.info(json.dumps(hyperparameters, indent=2))
    logging.info("----------------\n")

    logging.info("Running benchmarks run...")
    import asyncio

    asyncio.run(main(hyperparameters))
    logging.info("Benchmarks run completed")
