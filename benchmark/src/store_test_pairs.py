"""
Description: This script processes test paira from JSON files and stores them in a PostgreSQL database.

"""

import logging
import json
import os
from pathlib import Path
from paths import benchmark_dir, include_server_modules
import argparse

include_server_modules()
from src.db.connection import (
    get_database_connection,
    register_database,
    DatabaseConfig,
)

logging.basicConfig(level=logging.INFO)


def insert_test_pair(
    cursor,
    tpId,
    userPrompt,
    targetDoi,
    promptId,
    expertName,
    groupId,
    source,
    type,
    targetGroup
):
    cursor.execute(
        """
        INSERT INTO test_pairs (tpId, userPrompt, targetDoi, expectedRank, promptId, expertName, groupId, source, type, targetGroup)
        VALUES (%s, %s, %s, 0, %s, %s, %s, %s, %s, %s)
        """,
        (
            tpId,
            userPrompt,
            targetDoi,
            promptId,
            expertName,
            groupId,
            source,
            type,
            targetGroup,
        ),
    )


def main(
        files: [str]
):
    try:
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

        if files:
            logging.info(f"Importing {len(files)} test pairs files specified")
        else:
            files = []
            for folder in ["expert", "synthetic"]:
                full_path = Path(benchmark_dir()) / "queries" / folder
                logging.info(f"listing files from {full_path}")

                files += [os.path.join(full_path, f) for f in os.listdir(full_path)]

            files = [f for f in files if "20250919" in f and "expanded" not in f]

            files = [
                f
                for f in files
                if os.path.isfile(f) and f.endswith("json") and "expanded" not in f
            ]
            logging.info(f"Found {len(files)} test pairs files")

        total_test_pair = 0

        with get_database_connection("pan-finder-benchmarks") as conn:
            with conn.cursor() as cursor:
                for file in files:
                    with open(file, "r") as fh:
                        data = json.load(fh)

                    if "synthetic" in file:
                        #  ../../../../data/queries/synthetic/out_generated_queries_0c486eb7-2148-4fb1-bf30-eb7f8cf9e911.json
                        groupId = file.split(".")[-2].split("_")[-1]
                        tpSource = "synthetic"
                    else:
                        # data/queries/expert/domain_expert_queries_20250423_1.json
                        groupId = "_".join(file.split(".")[-2].split("_")[3:])
                        tpSource = "expert"

                    # {
                    #    "query_generation_system_prompt_id": "d3184c64-10bb-11f0-adb3-bf299b15d9db",
                    #    "doi": "10.15151/ESRF-ES-1347248794",
                    #    "query": "Look for research proposals related to crystallography and bioSAXS projects scheduled to start on or after October 7, 2023, and focusing on cell signaling proteins or drug discovery."
                    #  },
                    file_test_pair = 0
                    for test_pair in data:
                        logging.info(f"{test_pair}")
                        if not test_pair["query"]:
                            logging.info(f"Skipping test pair. No query")
                            continue

                        tpId = test_pair["id"]
                        doi = test_pair["doi"]
                        tpType = (
                            test_pair["type"] if "type" in test_pair else "positive"
                        )
                        tpGroup = test_pair["group"] if "group" in test_pair else None


                        userPrompt = test_pair["query"]
                        if userPrompt[0] == "{":
                            userPrompt = json.loads(userPrompt)
                            if "query" in userPrompt.keys():
                                userPrompt = userPrompt["query"]
                            else:
                                logging.info(f"Invalid query {doi}")
                                logging.info(f"{userPrompt}")
                                continue

                        insert_test_pair(
                            cursor,
                            tpId,
                            userPrompt,
                            doi,
                            (
                                test_pair["query_generation_system_prompt_id"]
                                if tpType == "synthetic"
                                else None
                            ),
                            test_pair["expert"] if tpType == "expert" else None,
                            groupId,
                            tpSource,
                            tpType,
                            tpGroup
                        )
                        file_test_pair += 1
                        total_test_pair += 1

                    conn.commit()
                    logging.info(f"Ingested {file_test_pair} test pairs from {file}")

        logging.info(f"Ingested {total_test_pair} test pairs in total")

    except Exception as e:
        logging.error("Error during store", exc_info=True)
        raise


if __name__ == "__main__":


    # Create ArgumentParser object
    parser = argparse.ArgumentParser(description="PaN-Finder store test pairs")

    # Define command-line options and arguments
    parser.add_argument(
        "-f",
        "--file",
        dest="files",
        action="append",
        type=str,
        help="Files containing the new test pairs to import",
    )

    # Parse arguments
    args = parser.parse_args()

    main(args.files)
