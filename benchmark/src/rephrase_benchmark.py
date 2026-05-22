from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from paths import benchmark_dir, include_server_modules, root_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare retrieval results for raw user questions with and without "
            "SearchEngine query rephrasing."
        )
    )
    parser.add_argument(
        "--recover-details-json",
        type=Path,
        default=None,
        help=(
            "Existing rephrase_benchmark_details_*.json file to use for rebuilding "
            "the diff CSV without rerunning the benchmark."
        ),
    )
    parser.add_argument(
        "--recover-diff-csv",
        type=Path,
        default=None,
        help=(
            "Target CSV path for --recover-details-json. Defaults to the sibling "
            "rephrase_benchmark_diff_*.csv path."
        ),
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=root_dir() / "report" / "data-1779438710450.csv",
        help="CSV file whose first column contains user questions.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=benchmark_dir() / "results" / "rephrase_benchmark",
        help="Directory for benchmark outputs.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top relevant results to keep per mode for comparison.",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip the first N CSV data rows before benchmarking.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of CSV rows to benchmark.",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Logging level, for example INFO or DEBUG.",
    )
    return parser.parse_args()


def load_queries(
    csv_path: Path, offset: int = 0, limit: int | None = None
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            return rows

        first_column_name = header[0] if header else "query"
        for data_index, row in enumerate(reader):
            csv_row_number = data_index + 2
            if not row:
                continue

            query_text = row[0].strip()
            if not query_text:
                continue

            rows.append(
                {
                    "query_id": len(rows) + 1,
                    "csv_row_number": csv_row_number,
                    "source_column": first_column_name,
                    "query": query_text,
                }
            )

    if offset > 0:
        rows = rows[offset:]
    if limit is not None:
        rows = rows[:limit]

    for index, row in enumerate(rows, start=1):
        row["query_id"] = index

    return rows


def validate_runtime_environment() -> None:
    missing: list[str] = []

    if not os.getenv("DATABASE_URL", "").strip():
        missing.append("DATABASE_URL")

    provider = os.getenv("LLM_PROVIDER", "azure").strip().lower()
    if provider == "azure":
        if not os.getenv("AZURE_OPENAI_ENDPOINT", "").strip():
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not os.getenv("AZURE_OPENAI_API_KEY", "").strip():
            missing.append("AZURE_OPENAI_API_KEY")
    elif provider == "openai":
        if not os.getenv("OPENAI_API_KEY", "").strip():
            missing.append("OPENAI_API_KEY")
    else:
        missing.append("LLM_PROVIDER(valid: azure|openai)")

    if missing:
        raise SystemExit(
            "Missing required environment variables for benchmark execution: "
            + ", ".join(missing)
        )


def build_engine():
    include_server_modules()

    from helper import get_llm_client, get_sentence_transformer

    # ruff: noqa: E402
    from src.config import get_settings
    from src.core.engine.engine import SearchEngine

    settings = get_settings()
    return SearchEngine(
        sentence_transformer=get_sentence_transformer(),
        llm_client=get_llm_client(settings.default_model_name),
    )


def serialize_structured_data(structured_data: Any) -> dict[str, Any]:
    return structured_data.model_dump()


def serialize_result(result: Any, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "doi": result.doi,
        "title": result.title,
        "facility_name": result.facility_name,
        "overall_score": result.overall_score,
        "document_score": result.document_score,
        "chunk_score": result.chunk_score,
        "conditions_full_score": result.conditions_full_score,
        "conditions_partial_score": result.conditions_partial_score,
        "keywords_score": result.keywords_score,
    }


def safe_sql_string(sql_query: Any) -> str | None:
    try:
        return sql_query.as_string()
    except Exception:
        return None


def top_result_score(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    return float(results[0]["overall_score"])


def sum_top_scores(results: list[dict[str, Any]]) -> float:
    return float(sum(float(result["overall_score"]) for result in results))


def count_full_matches(results: list[dict[str, Any]]) -> int:
    return sum(float(result["conditions_full_score"]) > 0 for result in results)


def classify_diff(diff: dict[str, Any]) -> str:
    if not diff["query_changed"]:
        return "unchanged"

    if (
        diff["original_top_dois"] == diff["rephrased_top_dois"]
        and abs(diff["top_score_delta"]) < 1e-9
        and abs(diff["top_n_score_sum_delta"]) < 1e-9
        and diff["full_match_delta"] == 0
    ):
        return "unchanged"

    baseline_signal = (
        diff["original_full_match_count"],
        round(diff["original_top_n_score_sum"], 6),
        round(diff["original_top_score"], 6),
    )
    rephrased_signal = (
        diff["rephrased_full_match_count"],
        round(diff["rephrased_top_n_score_sum"], 6),
        round(diff["rephrased_top_score"], 6),
    )

    if rephrased_signal > baseline_signal:
        return "helped"
    if rephrased_signal < baseline_signal:
        return "hurt"
    return "inconclusive"


def build_diff(
    query_row: dict[str, Any],
    original_run: dict[str, Any],
    rephrased_run: dict[str, Any],
) -> dict[str, Any]:
    original_top = original_run["top_results"]
    rephrased_top = rephrased_run["top_results"]

    original_top_dois = [result["doi"] for result in original_top]
    rephrased_top_dois = [result["doi"] for result in rephrased_top]

    original_set = set(original_top_dois)
    rephrased_set = set(rephrased_top_dois)
    shared_dois = sorted(original_set & rephrased_set)
    union_size = len(original_set | rephrased_set)

    original_top_score = top_result_score(original_top)
    rephrased_top_score = top_result_score(rephrased_top)
    original_top_n_score_sum = sum_top_scores(original_top)
    rephrased_top_n_score_sum = sum_top_scores(rephrased_top)
    original_full_match_count = count_full_matches(original_top)
    rephrased_full_match_count = count_full_matches(rephrased_top)

    diff = {
        "query_id": query_row["query_id"],
        "csv_row_number": query_row["csv_row_number"],
        "original_query": query_row["query"],
        "rephrased_query": rephrased_run["effective_query"],
        "query_changed": rephrased_run["effective_query"] != query_row["query"],
        "original_top_dois": original_top_dois,
        "rephrased_top_dois": rephrased_top_dois,
        "shared_top_dois": shared_dois,
        "shared_top_count": len(shared_dois),
        "top_n_jaccard": (len(shared_dois) / union_size) if union_size else 1.0,
        "top_1_original_doi": original_top_dois[0] if original_top_dois else None,
        "top_1_rephrased_doi": rephrased_top_dois[0] if rephrased_top_dois else None,
        "top_1_changed": original_top_dois[:1] != rephrased_top_dois[:1],
        "original_top_score": original_top_score,
        "rephrased_top_score": rephrased_top_score,
        "top_score_delta": rephrased_top_score - original_top_score,
        "original_top_n_score_sum": original_top_n_score_sum,
        "rephrased_top_n_score_sum": rephrased_top_n_score_sum,
        "top_n_score_sum_delta": rephrased_top_n_score_sum - original_top_n_score_sum,
        "original_full_match_count": original_full_match_count,
        "rephrased_full_match_count": rephrased_full_match_count,
        "full_match_delta": rephrased_full_match_count - original_full_match_count,
        "original_runtime_seconds": original_run["total_runtime_seconds"],
        "rephrased_runtime_seconds": rephrased_run["total_runtime_seconds"],
        "runtime_delta_seconds": (
            rephrased_run["total_runtime_seconds"]
            - original_run["total_runtime_seconds"]
        ),
        "original_total_results": original_run["total_results"],
        "rephrased_total_results": rephrased_run["total_results"],
        "original_relevant_results": original_run["relevant_results_count"],
        "rephrased_relevant_results": rephrased_run["relevant_results_count"],
        "original_error": original_run.get("error"),
        "rephrased_error": rephrased_run.get("error"),
    }
    diff["classification"] = classify_diff(diff)
    return diff


def build_summary(
    *,
    queries: list[dict[str, Any]],
    diffs: list[dict[str, Any]],
    input_csv: Path,
    top_n: int,
    started_at: str,
    finished_at: str,
) -> dict[str, Any]:
    classification_counts = {
        "helped": 0,
        "hurt": 0,
        "unchanged": 0,
        "inconclusive": 0,
    }
    for diff in diffs:
        classification_counts[diff["classification"]] += 1

    total_queries = len(diffs)
    changed_queries = sum(diff["query_changed"] for diff in diffs)
    top_1_changed = sum(diff["top_1_changed"] for diff in diffs)
    queries_with_errors = sum(
        bool(diff["original_error"] or diff["rephrased_error"]) for diff in diffs
    )

    avg_jaccard = (
        sum(diff["top_n_jaccard"] for diff in diffs) / total_queries
        if total_queries
        else 0.0
    )
    avg_top_score_delta = (
        sum(diff["top_score_delta"] for diff in diffs) / total_queries
        if total_queries
        else 0.0
    )
    avg_top_n_score_sum_delta = (
        sum(diff["top_n_score_sum_delta"] for diff in diffs) / total_queries
        if total_queries
        else 0.0
    )
    avg_runtime_delta = (
        sum(diff["runtime_delta_seconds"] for diff in diffs) / total_queries
        if total_queries
        else 0.0
    )

    return {
        "input_csv": str(input_csv),
        "query_count": len(queries),
        "evaluated_queries": total_queries,
        "top_n": top_n,
        "started_at": started_at,
        "finished_at": finished_at,
        "query_changed_count": changed_queries,
        "top_1_changed_count": top_1_changed,
        "queries_with_errors": queries_with_errors,
        "classification_counts": classification_counts,
        "average_top_n_jaccard": avg_jaccard,
        "average_top_score_delta": avg_top_score_delta,
        "average_top_n_score_sum_delta": avg_top_n_score_sum_delta,
        "average_runtime_delta_seconds": avg_runtime_delta,
        "classification_note": (
            "The helped/hurt label is heuristic. It compares the rephrased run "
            "against the original run using top-N full-match count first, then "
            "top-N overall score sum, then top-1 overall score."
        ),
    }


async def run_single_mode(
    engine: Any,
    query_text: str,
    *,
    use_rephrase: bool,
    top_n: int,
) -> dict[str, Any]:
    effective_query = query_text
    rephrase_time = 0.0

    try:
        if use_rephrase:
            rephrase_start = time.time()
            effective_query = await engine.rephrase_query_for_search(query_text)
            rephrase_time = time.time() - rephrase_start

        parse_start = time.time()
        structured_data = await engine.parse_query_to_structured_data(effective_query)
        parse_time = time.time() - parse_start

        search_start = time.time()
        raw_results, sql_query, knee_point_result = await engine.execute_search(
            structured_data
        )
        search_time = time.time() - search_start

        relevant_results = (
            knee_point_result.filtered_results if knee_point_result else raw_results
        )
        top_results = [
            serialize_result(result, rank)
            for rank, result in enumerate(relevant_results[:top_n], start=1)
        ]

        return {
            "effective_query": effective_query,
            "structured_data": serialize_structured_data(structured_data),
            "sql_query": safe_sql_string(sql_query),
            "rephrase_seconds": rephrase_time,
            "parse_seconds": parse_time,
            "search_seconds": search_time,
            "total_runtime_seconds": rephrase_time + parse_time + search_time,
            "total_results": len(raw_results),
            "relevant_results_count": len(relevant_results),
            "weakly_relevant_results_count": max(
                0, len(raw_results) - len(relevant_results)
            ),
            "top_results": top_results,
            "error": None,
        }
    except Exception as exc:
        logging.exception("Benchmark run failed for query: %s", query_text)
        return {
            "effective_query": effective_query,
            "structured_data": {"intention": "", "keywords": [], "filters": {}},
            "sql_query": None,
            "rephrase_seconds": rephrase_time,
            "parse_seconds": 0.0,
            "search_seconds": 0.0,
            "total_runtime_seconds": rephrase_time,
            "total_results": 0,
            "relevant_results_count": 0,
            "weakly_relevant_results_count": 0,
            "top_results": [],
            "error": str(exc),
        }


async def benchmark_query(
    engine: Any,
    query_row: dict[str, Any],
    *,
    top_n: int,
) -> dict[str, Any]:
    original_run = await run_single_mode(
        engine,
        query_row["query"],
        use_rephrase=False,
        top_n=top_n,
    )
    rephrased_run = await run_single_mode(
        engine,
        query_row["query"],
        use_rephrase=True,
        top_n=top_n,
    )
    diff = build_diff(query_row, original_run, rephrased_run)

    return {
        "query_id": query_row["query_id"],
        "csv_row_number": query_row["csv_row_number"],
        "source_column": query_row["source_column"],
        "original_query": query_row["query"],
        "without_rephrase": original_run,
        "with_rephrase": rephrased_run,
        "diff": diff,
    }


def write_query_diff_csv(path: Path, diffs: list[dict[str, Any]]) -> None:
    fieldnames = [
        "query_id",
        "csv_row_number",
        "classification",
        "query_changed",
        "top_1_changed",
        "shared_top_count",
        "top_n_jaccard",
        "original_top_score",
        "rephrased_top_score",
        "top_score_delta",
        "original_top_n_score_sum",
        "rephrased_top_n_score_sum",
        "top_n_score_sum_delta",
        "original_full_match_count",
        "rephrased_full_match_count",
        "full_match_delta",
        "original_runtime_seconds",
        "rephrased_runtime_seconds",
        "runtime_delta_seconds",
        "original_total_results",
        "rephrased_total_results",
        "original_relevant_results",
        "rephrased_relevant_results",
        "top_1_original_doi",
        "top_1_rephrased_doi",
        "original_query",
        "rephrased_query",
        "original_top_dois",
        "rephrased_top_dois",
        "shared_top_dois",
        "original_error",
        "rephrased_error",
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fieldnames, quoting=csv.QUOTE_NONNUMERIC
        )
        writer.writeheader()
        for diff in diffs:
            row = {key: diff.get(key) for key in fieldnames}
            row["original_top_dois"] = json.dumps(diff["original_top_dois"])
            row["rephrased_top_dois"] = json.dumps(diff["rephrased_top_dois"])
            row["shared_top_dois"] = json.dumps(diff["shared_top_dois"])
            writer.writerow(row)


def default_diff_csv_path(details_json_path: Path) -> Path:
    details_name = details_json_path.name
    if details_name.startswith("rephrase_benchmark_details_"):
        diff_name = details_name.replace(
            "rephrase_benchmark_details_", "rephrase_benchmark_diff_", 1
        )
        return details_json_path.with_name(diff_name).with_suffix(".csv")
    return details_json_path.with_suffix(".csv")


def recover_diff_csv_from_details(
    details_json_path: Path, output_csv_path: Path
) -> int:
    payload = json.loads(details_json_path.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    diffs = [
        record["diff"]
        for record in records
        if isinstance(record, dict) and "diff" in record
    ]
    write_query_diff_csv(output_csv_path, diffs)
    return len(diffs)


async def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.recover_details_json is not None:
        output_csv_path = args.recover_diff_csv or default_diff_csv_path(
            args.recover_details_json
        )
        recovered_count = recover_diff_csv_from_details(
            args.recover_details_json, output_csv_path
        )
        logging.info("Recovered %s diff rows to %s", recovered_count, output_csv_path)
        return

    validate_runtime_environment()

    queries = load_queries(args.input_csv, offset=args.offset, limit=args.limit)
    if not queries:
        raise ValueError(f"No benchmark queries found in {args.input_csv}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    started_at = datetime.now().isoformat(timespec="seconds")

    engine = build_engine()

    records: list[dict[str, Any]] = []
    diffs: list[dict[str, Any]] = []

    for index, query_row in enumerate(queries, start=1):
        logging.info(
            "Benchmarking query %s/%s | row %s",
            index,
            len(queries),
            query_row["csv_row_number"],
        )
        record = await benchmark_query(engine, query_row, top_n=args.top_n)
        records.append(record)
        diffs.append(record["diff"])

    finished_at = datetime.now().isoformat(timespec="seconds")
    summary = build_summary(
        queries=queries,
        diffs=diffs,
        input_csv=args.input_csv,
        top_n=args.top_n,
        started_at=started_at,
        finished_at=finished_at,
    )

    details_path = args.output_dir / f"rephrase_benchmark_details_{timestamp}.json"
    summary_path = args.output_dir / f"rephrase_benchmark_summary_{timestamp}.json"
    diff_csv_path = args.output_dir / f"rephrase_benchmark_diff_{timestamp}.csv"

    details_payload = {
        "summary": summary,
        "records": records,
    }

    details_path.write_text(json.dumps(details_payload, indent=2), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_query_diff_csv(diff_csv_path, diffs)

    logging.info("Summary written to %s", summary_path)
    logging.info("Per-query diff written to %s", diff_csv_path)
    logging.info("Detailed records written to %s", details_path)


if __name__ == "__main__":
    asyncio.run(main())
