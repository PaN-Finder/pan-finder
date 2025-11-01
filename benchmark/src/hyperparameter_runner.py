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
from benchmarks_metrics import metrics_at_1k

include_server_modules()
from src.core.search_query_builder import SearchQueryBuilder
from src.db.connection import (
    get_database_pool,
    get_database_connection,
    register_database,
    DatabaseConfig,
)
from src.core.engine.knee_point import KneePoint
from src.db.models.search import EnhancedSearchResult

logging.getLogger("hyperparameter_runner")


async def process_test_pair(
    hyperparameters: dict,
    system_prompt: str,
    user_prompt: str,
    builder: SearchQueryBuilder,
) -> dict:

    logging.info("process_test_pair: begin: extracting user prompt components")
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
    logging.info("process_test_pair: end: extracting user prompt components")

    logging.info("process_test_pair: User Prompt: %s", user_prompt)
    logging.info("process_test_pair: LLM Response: %s", response)
    logging.info("process_test_pair: Formatted Data %s", user_prompt_components)

    logging.info("process_test_pair: begin: query building")
    start_query_building = time.time()
    query = builder.build_query(user_prompt_components)
    end_query_building = time.time()
    logging.info("process_test_pair: end: query building")
    logging.info("SQL Query %s", query.as_string())

    logging.info("process_test_pair: begin: query execution")
    start_query_execution = time.time()
    with get_database_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            query_string = query.as_string(conn)
            #query_string = cursor.mogrify(query).decode("utf-8")
            results = cursor.fetchall()
    end_query_execution = time.time()
    logging.info("process_test_pair: end: query execution")

    logging.info("process_test_pair: begin: computing run times")
    extraction_time = (
        end_query_components_extraction - start_query_components_extraction
    )
    building_time = end_query_building - start_query_building
    query_time = end_query_execution - start_query_execution
    run_time = extraction_time + building_time + query_time
    logging.info("process_test_pair: end: computing run times")
    logging.info(f"process_test_pair: Total Run Time: {run_time:.3f}s")

    dfResults = pd.DataFrame(
        results,
        columns=[
            "DOI",
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

    logging.info("process_test_pair: Results")
    logging.info(dfResults.to_string(index=True))

    return {
        "components": user_prompt_components,
        "extraction_time": extraction_time,
        "building_time": building_time,
        "query_time": query_time,
        "run_time": run_time,
        "query": query_string,
        "results_set": dfResults,
    }


async def process_simple_test_pair(
    hyperparameters: dict,
    system_prompt: str,
    test_pair: dict,
    run_id: str,
    builder: SearchQueryBuilder,
) -> None:
    """
    This function execute simple test pair test such as positive and negative.
    It also computes the related metrics and seve them in the db
    """

    user_prompt = test_pair[1]
    doi = test_pair[2]

    logging.info("process_simple_test_pair: begin: execute search")
    results = await process_test_pair(hyperparameters, system_prompt, user_prompt, builder)
    logging.info("process_simple_test_pair: end: execute search")

    logging.info("process_simple_test_pair: begin: target doi %s", doi)
    results_set = results["results_set"]
    index = next(iter(results_set.index[results_set["DOI"] == doi]), -1)
    results["rank"] = index + 1
    overall_score = results_set.iloc[index, 1] if index != -1 else 0
    logging.info("process_simple_test_pair: end: target doi")
    logging.info(f"process_simple_test_pair: Rank: {results["rank"]} (Index: {index})")
    logging.info(f"process_simple_test_pair: Overall Score: {overall_score}")

    logging.info("process_simple_test_pair: begin: insert test pair test record")
    tp_id = insert_test_pair_test(
        run_id,
        test_pair[0],
        results
    )
    logging.info("process_simple_test_pair: end: insert test pair test record. Id: %s", tp_id)

    # compute all test pair metrics
    logging.info("process_simple_test_pair: begin: compute test pair metrics")
    test_pair_metrics = compute_simple_test_pair_metrics(
        hyperparameters,
        results,
        test_pair,
    )
    logging.info("process_simple_test_pair: end: compute test pair metrics")
    logging.info("process_simple_test_pair: metrics: %s", json.dumps(test_pair_metrics))

    # insert test metrics
    logging.info("process_simple_test_pair: begin: insert test pair metrics")
    insert_test_pair_metrics(
        run_id,
        tp_id,
        test_pair_metrics,
    )
    logging.info("process_simple_test_pair: end: insert test pair metrics")

async def process_comparative_test_pair(
    hyperparameters: dict,
    system_prompt: str,
    test_pair: dict,
    run_id: str,
    builder: SearchQueryBuilder,
) -> None:
    """
    This function execute comparative test pair test.
    It also computes the related metrics and save them in the db
    """

    user_prompt = test_pair[1]
    dois = test_pair[2].split(",")

    logging.info("process_comparative_test_pair: begin: execute search")
    results = await process_test_pair(hyperparameters, system_prompt, user_prompt, builder)
    logging.info("process_comparative_test_pair: end: execute search")

    logging.info("process_comparative_test_pair: begin: target dois %s", ",".join(dois))
    indexes = [next((i for i, r in enumerate(results["results_set"]) if r[0] == doi), -1) for doi in dois]
    results["ranks"] = [index + 1 for index in indexes]
    overall_scores = [results["results_set"][index][1] if index != -1 else 0 for index in indexes]
    logging.info("process_comparative_test_pair: end: target dois")
    logging.info(f"process_comparative_test_pair: Ranks: {results["ranks"]} (Index: {indexes})")
    logging.info(f"process_comparative_test_pair: Overall Score: {overall_scores}")

    logging.info("process_comparative_test_pair: begin: insert test pair test record")
    tp_id = insert_test_pair_test(
        run_id,
        test_pair[0],
        results
    )
    logging.info("process_comparative_test_pair: end: insert test pair test record. Id: %s", tp_id)

    # compute all test pair metrics
    logging.info("process_comparative_test_pair: begin: compute test pair metrics")
    test_pair_metrics = compute_comparative_test_pair_metrics(
        hyperparameters,
        results,
        test_pair,
    )
    logging.info("process_comparative_test_pair: end: compute test pair metrics")
    logging.info("process_comparative_test_pair: metrics: %s", json.dumps(test_pair_metrics))

    # insert test metrics
    logging.info("process_comparative_test_pair: begin: insert test pair metrics")
    insert_test_pair_metrics(
        run_id,
        tp_id,
        test_pair_metrics,
    )
    logging.info("process_comparative_test_pair: end: insert test pair metrics")


async def process_extended_test_pair(
    hyperparameters: dict,
    system_prompt: str,
    test_pair: dict,
    run_id: str,
    builder: SearchQueryBuilder,
    knee_point_instance: KneePoint,
) -> None:
    """
    This function execute extended presence test pair test.
    It also computes the related metrics and saves them in the db
    """

    user_prompt = test_pair[1]
    doi = test_pair[2]

    logging.info("process_extended_test_pair: begin: execute search")
    results = await process_test_pair(hyperparameters, system_prompt, user_prompt, builder)
    logging.info("process_extended_test_pair: end: execute search")

    logging.info("process_extended_test_pair: begin: computing knee point")
    knee_point_input = [
        EnhancedSearchResult(
            doi=r["DOI"],
            title="",
            facility_name="",
            abstract="",
            overall_score=float(r["Overall Score"]),
            similarity_score=0.0,
            chunk_similarity_score=0.0,
            full_match_score=0.0,
            partial_match_score=0.0,
            keyword_score=0.0,
        )
        for i,r
        in results["results_set"].iterrows()
    ]
    results["knee_point_results"] = knee_point_instance.filter_with_stats(knee_point_input)
    logging.info("process_extended_test_pair: end: computing knee point")

    logging.info("process_extended_test_pair: begin: target doi %s", doi)
    hr_dois = [ r.doi for r in results["knee_point_results"]]
    results_set = results["results_set"]
    index = next(iter(results_set.index[results_set["DOI"] == doi]), -1)
    results["rank"] = index + 1
    overall_score = results_set.iloc[index, 1] if index != -1 else 0
    results["actual_group"] = "HR" if doi in hr_dois else "LR" if index >= 0 else "NP"
    logging.info("process_extended_test_pair: end: target doi")
    logging.info(f"process_extended_test_pair: Rank: {results["rank"]} (Index: {index})")
    logging.info(f"process_extended_test_pair: Overall Score: {overall_score}")
    logging.info(f"process_extended_test_pair: Actual group: {results["actual_group"]}")

    logging.info("process_extended_test_pair: begin: insert test pair test record")
    tp_id = insert_test_pair_test(
        run_id,
        test_pair[0],
        results
    )
    logging.info("process_extended_test_pair: end: insert test pair test record. Id: %s", tp_id)

    # compute all test pair metrics
    logging.info("process_extended_test_pair: begin: compute test pair metrics")
    test_pair_metrics = compute_extended_test_pair_metrics(
        hyperparameters,
        results,
        test_pair,
    )
    logging.info("process_extended_test_pair: end: compute test pair metrics")
    logging.info("process_extended_test_pair: metrics: %s", json.dumps(test_pair_metrics))

    # insert test metrics
    logging.info("process_extended_test_pair: begin: insert test pair metrics")
    insert_test_pair_metrics(
        run_id,
        tp_id,
        test_pair_metrics,
    )
    logging.info("process_extended_test_pair: end: insert test pair metrics")


def compute_simple_test_pair_metrics(
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
        for name, metric in hyperparameters["metrics"]["test_pair_metrics"][test_pair[8]].items()
    }
    return metrics_values

def compute_extended_test_pair_metrics(
    hyperparameters: dict,
    processed_data: dict,
    test_pair,
) -> dict:
    metrics_values = {
        name: metrics_at_1k[metric["function"]](
            ag=processed_data["actual_group"][0],
            eg=test_pair[9],
            wm=metric["weights"],
        )
        for name, metric in hyperparameters["metrics"]["test_pair_metrics"][test_pair[8]].items()
    }
    return metrics_values

def compute_comparative_test_pair_metrics(
    hyperparameters: dict,
    processed_data: dict,
    test_pair,
) -> dict:
    metrics_values = {
        name: metrics_at_1k[metric](
            r=processed_data["ranks"],
            k=hyperparameters["results_set"]["results_set_size"],
        )
        for name, metric in hyperparameters["metrics"]["test_pair_metrics"][test_pair[8]].items()
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
    results
) -> str:
    test_id = str(uuid.uuid4())
    rank = results["rank"] if "rank" in results else results["ranks"][0] if "ranks" in results else -1
    ranks = results["ranks"] if "ranks" in results else [results["rank"]] if "rank" in results else []
    actual_groups = results["actual_groups"] if "actual_groups" in results else [results["actual_group"]] if "actual_group" in results else []
    knee_point_results = json.dumps(
        results["knee_point_results"]
        if "knee_point_results" in results
        else {})

    params = (
        test_id,
        run_id,
        tp_id,
        results["components"]["intention"],
        results["components"]["keywords"],
        json.dumps(results["components"]["filters"]),
        rank,
        results["run_time"],
        results["extraction_time"],
        results["building_time"],
        results["query_time"],
        results["query"],
        results["results_set"].to_json(),
        ranks,
        actual_groups,
        knee_point_results
    )
    #print([type(x) for x in params])
    #print([repr(x) for x in params])

    with get_database_connection("pan-finder-benchmarks") as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO benchmarks_run_test 
                (
                    testId, 
                    runId, 
                    tpId,  
                    intention, 
                    keywords, 
                    filters, 
                    rank, 
                    runTime, 
                    extractionTime, 
                    buildingTime, 
                    queryTime, 
                    sqlQuery, 
                    resultsSet,
                    ranks,
                    actualGroups,
                    kneePointResults
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                params
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
        results_set_size=hyperparameters["results_set"].get("results_set_size", 20),
    )

    knee_point = KneePoint()

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
                "test_pairs_set", "comprehensive"
            )
            test_pairs_type = hyperparameters["test_pairs"].get(
                "test_pairs_type", "all"
            )

            query = """
                SELECT 
                    tpId, 
                    userPrompt, 
                    targetDoi, 
                    expectedRank, 
                    promptId, 
                    expertName, 
                    groupId, 
                    source, 
                    type, 
                    targetGroup
                FROM test_pairs
            """
            conditions = []
            params = []
            if test_pairs_set in ["synthetic", "expert"]:
                conditions.append(f"source = %s")
                params.append(test_pairs_set)
            if test_pairs_type != "all":
                conditions.append(f"type = %s")
                params.append(test_pairs_type)

            if params:
                query += " WHERE " + " AND ".join(conditions)

            tp_cursor.execute(query, params)

            # loop on all the tests
            test_pair_counter = 1
            for test_pair in tp_cursor:
                test_pair_id = str(test_pair[0])
                logging.info(
                    f"--- Running Test Pair {test_pair_counter}: {test_pair_id} ---"
                )

                if test_pair[8] == "positive" or test_pair[8] == "negative":
                    await process_simple_test_pair(
                        hyperparameters,
                        system_prompt,
                        test_pair,
                        run_id,
                        builder
                    )

                elif test_pair[8] == "extended presence":
                    await process_extended_test_pair(
                        hyperparameters,
                        system_prompt,
                        test_pair,
                        run_id,
                        builder,
                        knee_point
                    )

                elif test_pair[8] == "comparative":
                    await process_comparative_test_pair(
                        hyperparameters,
                        system_prompt,
                        test_pair,
                        run_id,
                        builder
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
