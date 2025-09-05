import json
import logging
import time
import sys
from pathlib import Path
from datetime import datetime
from openai import AzureOpenAI
import csv
import pandas as pd
from sentence_transformers import SentenceTransformer
from plotting import (
    plot_avarage_scores_per_dataset,
    plot_overall_changes,
    plot_score_distribution_boxplot,
)

# Make server code importable without modifying server files
server_dir = Path(__file__).parent.parent.parent / "server"
server_src = server_dir / "src"
# Add the 'server' directory so we can import packages as 'src.*'
sys.path.insert(0, str(server_dir))
# Add the 'core' subpackage root to import search_query_builder directly (avoid core.__init__)
sys.path.insert(0, str(server_src / "core"))

from search_query_builder import SearchQueryBuilder
from src.db.connection import get_connection_pool, get_db_connection
from src.config import get_settings

logging.setLoggerClass(logging.Logger)
# Global cache for LLM responses (loaded from file)
llm_response_cache = {}


def root_dir() -> Path:
    """Returns the project root directory."""
    return Path(__file__).parent.parent.parent


# Define cache file path
CACHE_FILE_PATH = root_dir() / "benchmark" / "cache" / "llm_cache.json"
settings = get_settings()


def openai_client(self) -> AzureOpenAI:
    """Lazy-loaded OpenAI client."""
    if self._openai_client is None:
        self._openai_client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
        )
    return self._openai_client


def load_system_prompt(model: str, version: str) -> str:
    filepath = Path(root_dir()) / "benchmark" / "prompts" / model / version
    prompt = filepath.read_text()
    return prompt


# Load prompt globally
llm_model = "gpt-4.1-mini"
system_prompt_version = "1_0_7.md"
extract_prompt = load_system_prompt(llm_model, system_prompt_version)


def load_llm_cache():
    """Loads the LLM response cache from a file."""
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


def save_llm_cache():
    """Saves the LLM response cache to a file."""
    try:
        # Ensure parent directory exists
        CACHE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE_PATH, "w") as f:
            json.dump(llm_response_cache, f, indent=2)
    except IOError as e:
        logging.info("Error saving LLM cache: %s", e)


def load_rrf_score_k_values() -> list:
    filepath = Path(root_dir()) / "benchmark" / "rrf_score_k_values_matrix.json"
    rrf_score_k_values = json.loads(filepath.read_text())
    return rrf_score_k_values


def load_datasets():
    base_dir = Path(root_dir()) / "benchmark" / "queries"
    datasets = {}
    for filepath in base_dir.glob("*.json"):
        datasets[filepath.name] = filepath.read_text()
    return datasets


def extract_json_from_response(text: str) -> str:
    # extract json string from response
    # scenario: ```{...}``` -> {...}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Response does not contain a valid JSON object")
    return text[start : end + 1]


query_ix = 0


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
    """Gets response from OpenAI API, using file-backed cache if available."""

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
    answer = response.choices[0].message.content

    if answer is not None:
        llm_response_cache[cache_key] = answer
        save_llm_cache()  # Save cache after adding a new entry
    return answer


def process_query(query_obj: dict, doi: str, builder: SearchQueryBuilder) -> tuple:
    global query_ix
    query_text = query_obj.get("query", "")
    if query_text == "":
        raise ValueError("Query text is empty")

    min_position = query_obj.get("min_position", 0)

    response = get_llm_response(
        extract_prompt, query_text, temperature=0, max_tokens=500
    )

    if response is None:
        raise ValueError("LLM response is None")

    logging.info("DOI: %s", doi)
    logging.info("Query Index: %s", query_ix)
    query_ix += 1
    logging.info("Query: %s", query_text)
    logging.info("LLM Response: %s", response)

    formatted_data = extract_json_from_response(response)
    data = json.loads(formatted_data)
    logging.info("Formatted Data: %s", data)

    query = builder.build_query(data)
    try:
        logging.info("SQL Query: %s", query.as_string())
    except Exception:
        # Fallback in case as_string() requires a connection in this psycopg setup
        logging.info("SQL Query constructed (use DB to render string safely)")

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
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

    logging.info("Results")
    logging.info("%s", df.to_string(index=True))

    position = next((i for i, result in enumerate(results) if result[0] == doi), -1)
    score = (
        0
        if position < 0
        else (1 if position <= min_position else 1 - (position - min_position) / 20)
    )
    if position != -1:
        overall = results[position][1]
        sim_score = results[position][2]
        chunk_score = results[position][3]
        full_match_score = results[position][4]
        partial_match_score = results[position][5]
        keyword_score = results[position][6]
    else:
        overall = sim_score = chunk_score = full_match_score = partial_match_score = (
            keyword_score
        ) = 0

    print(
        f"Score: {score} | Position: {position} | Min Position: {min_position} | Query Runtime: {elapsed_time:.3f}s\n\n"
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


def process_document(doc: dict, builder: SearchQueryBuilder) -> tuple:
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
    dataset_name: str, dataset: str, builder: SearchQueryBuilder
) -> tuple:
    logging.info("Dataset: %s", dataset_name)
    dataset_scores = []
    dataset_runtimes = []
    dataset_breakdowns = []
    data = json.loads(dataset)
    for doc in data:
        scores, runtimes, breakdowns = process_document(doc, builder)
        dataset_scores.extend(scores)
        dataset_runtimes.extend(runtimes)
        dataset_breakdowns.extend(breakdowns)
    return dataset_scores, dataset_runtimes, dataset_breakdowns


def get_sentence_transformer(model: str = "all-MiniLM-L12-v2"):
    model_path = root_dir() / "models" / model
    return SentenceTransformer(str(model_path), device="cpu")


def main():
    # Load cache at the beginning
    load_llm_cache()

    rrf_score_k_values = load_rrf_score_k_values()
    datasets = load_datasets()
    sentence_transformer = get_sentence_transformer()

    all_test_results = []  # Initialize list to store results for CSV
    overall_test_metrics = {}  # Store overall avg score and runtime per test
    all_scores_by_test_config = {}  # To store raw scores for each test config

    # --- Loop through each RRF K configuration ---
    for rrf_config in rrf_score_k_values:
        test_name = rrf_config.get("test_name", "unknown_test")
        logging.info(f"--- Running Test: {test_name} ---")
        logging.info("RRF Score K Values: %s", rrf_config)

        # Instantiate builder with the current configuration
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

        # Reset results for each test configuration
        scores_by_dataset = {}
        runtimes_by_dataset = {}
        breakdowns_by_dataset = {}
        test_all_scores = []  # Scores for the current test config
        test_all_runtimes = []  # Runtimes for the current test config
        test_total_queries = 0  # Query count for the current test config

        # --- Process datasets for the current configuration ---
        for dataset_name, dataset in datasets.items():
            ds_scores, ds_runtimes, ds_breakdowns = process_dataset(
                dataset_name, dataset, builder
            )
            scores_by_dataset[dataset_name] = ds_scores
            runtimes_by_dataset[dataset_name] = ds_runtimes
            breakdowns_by_dataset[dataset_name] = ds_breakdowns

            # Calculate dataset-specific average score
            ds_total_queries = len(ds_scores)
            ds_score_sum = sum(ds_scores)
            ds_avg_score = ds_score_sum / ds_total_queries if ds_total_queries else 0
            ds_avg_score_percent = ds_avg_score * 100

            # Append dataset result to the main list
            all_test_results.append(
                {
                    "test_name": test_name,
                    "dataset_name": dataset_name.replace(
                        ".json", ""
                    ),  # Clean dataset name
                    "avg_score": round(ds_avg_score, 4),
                    "avg_score_percent": round(ds_avg_score_percent, 2),
                }
            )

            # Accumulate for overall test average
            test_total_queries += ds_total_queries
            test_all_scores.extend(ds_scores)
            test_all_runtimes.extend(ds_runtimes)

        # --- Calculate and log overall results for the current test configuration ---
        overall_score_sum = sum(test_all_scores)
        avg_score = overall_score_sum / test_total_queries if test_total_queries else 0
        avg_runtime = (
            sum(test_all_runtimes) / test_total_queries if test_total_queries else 0
        )
        logging.info(f"--- Overall Results for Test: {test_name} ---")
        logging.info("Average Score: %s", avg_score)
        logging.info("Average Query Runtime: %s", avg_runtime)

        # Store overall metrics for this test
        overall_test_metrics[test_name] = {
            "avg_score": avg_score * 100,  # Store as percentage
            "avg_runtime": avg_runtime,
        }

        if test_all_scores:
            all_scores_by_test_config[test_name] = test_all_scores

    results_dir = Path(root_dir()) / "benchmark" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists

    # --- Save all aggregated results to CSV and plots after all tests are done ---
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

    # Use pandas to easily write to CSV
    results_df = pd.DataFrame(all_test_results)
    plot_avarage_scores_per_dataset(
        results_df,
        overall_test_metrics,
        results_dir / f"average_scores_per_dataset_{timestamp}.png",
    )
    results_df.to_csv(
        results_dir / f"results_{timestamp}.csv",
        index=False,
        quoting=csv.QUOTE_NONNUMERIC,
    )

    plot_overall_changes(
        results_dir,
        results_dir / "overall_changes.png",
    )


if __name__ == "__main__":
    main()
