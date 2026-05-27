"""Compare benchmark score files and cached LLM extraction responses.

New cache entries are resolved through metadata written by LLMClient:
metadata.request.user_input, metadata.request.model, metadata.request.temperature,
metadata.request.max_tokens, metadata.request.response_format, plus benchmark-specific
metadata.system_prompt_version.
"""

from __future__ import annotations

import argparse
import contextlib
import difflib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paths import benchmark_dir

DEFAULT_RESPONSE_FORMAT = {"type": "json_object"}
CacheLookupKey = tuple[str, str, str, str, str, str]


@dataclass(frozen=True)
class QueryRecord:
    index: int
    dataset: str
    document_index: int
    query_index: int
    doi: str
    query: str
    min_position: int


@dataclass(frozen=True)
class CacheResolver:
    model: str
    prompt_version: str
    cache_index: dict[CacheLookupKey, list[dict[str, Any]]]
    hits: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare two raw_scores_by_test_config files and show cached LLM "
            "response differences for the underlying benchmark questions."
        )
    )
    parser.add_argument("old_scores", type=Path)
    parser.add_argument("new_scores", type=Path)
    parser.add_argument(
        "--cache",
        type=Path,
        default=benchmark_dir() / "cache" / "llm_cache.json",
        help="Path to llm_cache.json",
    )
    parser.add_argument(
        "--old-model",
        default="gpt-4.1-mini",
        help="Model name used for the earlier score file",
    )
    parser.add_argument(
        "--new-model",
        default="gpt-5.4-mini",
        help="Model name used for the newer score file",
    )
    parser.add_argument(
        "--old-prompt-version",
        default=None,
        help="Prompt version for the earlier run; inferred only when unambiguous",
    )
    parser.add_argument(
        "--new-prompt-version",
        default=None,
        help="Prompt version for the newer run; inferred only when unambiguous",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="LLM temperature used for both benchmark runs",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=500,
        help="LLM max token setting used for both benchmark runs",
    )
    parser.add_argument(
        "--configs",
        nargs="*",
        default=None,
        help="Optional subset of shared score config names to compare",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of differing query rows to print",
    )
    parser.add_argument(
        "--show-all-differences",
        action="store_true",
        help="Include score improvements as well as regressions",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write the comparison report",
    )
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def flatten_queries() -> list[QueryRecord]:
    base_dir = benchmark_dir() / "queries" / "synthetic"
    records: list[QueryRecord] = []
    index = 0

    for dataset_path in sorted(base_dir.glob("*.json")):
        dataset = json.loads(dataset_path.read_text())
        for document_index, document in enumerate(dataset):
            doi = document.get("doi", "N/A")
            for query_index, query_obj in enumerate(document.get("queries", [])):
                query_text = query_obj.get("query", "").strip()
                records.append(
                    QueryRecord(
                        index=index,
                        dataset=dataset_path.name,
                        document_index=document_index,
                        query_index=query_index,
                        doi=doi,
                        query=query_text,
                        min_position=int(query_obj.get("min_position", 0)),
                    )
                )
                index += 1

    return records


def normalize_cache_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return json.dumps(value, sort_keys=True, ensure_ascii=True)


def make_cache_lookup_key(
    *,
    model: str,
    prompt_version: str,
    user_input: str,
    temperature: Any,
    max_tokens: Any,
    response_format: Any,
) -> CacheLookupKey:
    return (
        model,
        prompt_version,
        user_input,
        normalize_cache_value(temperature),
        normalize_cache_value(max_tokens),
        normalize_cache_value(response_format),
    )


def metadata_request(entry: dict[str, Any]) -> dict[str, Any]:
    metadata = entry.get("metadata", {})
    request = metadata.get("request", {})
    return request if isinstance(request, dict) else {}


def entry_user_input(entry: dict[str, Any]) -> str | None:
    request = metadata_request(entry)
    user_input = request.get("user_input")
    if isinstance(user_input, str) and user_input:
        return user_input
    return None


def entry_lookup_key(entry: dict[str, Any]) -> CacheLookupKey | None:
    metadata = entry.get("metadata", {})
    request = metadata_request(entry)

    model = request.get("model") or metadata.get("llm_model")
    prompt_version = metadata.get("system_prompt_version")
    user_input = entry_user_input(entry)
    temperature = request.get("temperature", metadata.get("temperature"))
    max_tokens = request.get("max_tokens", metadata.get("max_tokens"))
    response_format = request.get(
        "response_format", metadata.get("response_format", DEFAULT_RESPONSE_FORMAT)
    )

    if not isinstance(model, str) or not isinstance(prompt_version, str):
        return None
    if user_input is None or temperature is None or max_tokens is None:
        return None

    return make_cache_lookup_key(
        model=model,
        prompt_version=prompt_version,
        user_input=user_input,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )


def build_cache_index(
    cache_entries: dict[str, Any],
) -> dict[CacheLookupKey, list[dict[str, Any]]]:
    cache_index: dict[CacheLookupKey, list[dict[str, Any]]] = {}
    for entry in cache_entries.values():
        if not isinstance(entry, dict):
            continue
        lookup_key = entry_lookup_key(entry)
        if lookup_key is None:
            continue
        cache_index.setdefault(lookup_key, []).append(entry)
    return cache_index


def detect_prompt_version(*, model: str, cache_entries: dict[str, Any]) -> str:
    versions = sorted(
        {
            entry.get("metadata", {}).get("system_prompt_version")
            for entry in cache_entries.values()
            if (
                metadata_request(entry).get("model")
                or entry.get("metadata", {}).get("llm_model")
            )
            == model
            and isinstance(entry.get("metadata", {}).get("system_prompt_version"), str)
        }
    )
    if len(versions) == 1:
        return versions[0]
    if not versions:
        raise RuntimeError(
            f"Could not infer a prompt version for model '{model}' from cache metadata."
        )
    raise RuntimeError(
        f"Multiple prompt versions found for model '{model}': {', '.join(versions)}. "
        "Pass --old-prompt-version and --new-prompt-version."
    )


def parse_cache_payload(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    if entry is None:
        return None

    response_blob = entry.get("response")
    if response_blob is None:
        return None

    response_data = json.loads(response_blob)
    content = response_data.get("content")
    if not isinstance(content, str):
        return None

    try:
        extracted = json.loads(content)
    except json.JSONDecodeError:
        extracted = {"_raw_content": content}

    return {
        "extracted": extracted,
        "response": response_data,
        "metadata": entry.get("metadata", {}),
    }


def pretty_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)


def build_json_diff(old_value: Any, new_value: Any) -> str:
    old_lines = pretty_json(old_value).splitlines()
    new_lines = pretty_json(new_value).splitlines()
    return "\n".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="old_extracted.json",
            tofile="new_extracted.json",
            lineterm="",
        )
    )


def build_cache_resolver(
    *,
    cache_index: dict[CacheLookupKey, list[dict[str, Any]]],
    model: str,
    prompt_version: str,
    query_records: list[QueryRecord],
    temperature: float,
    max_tokens: int,
) -> CacheResolver:
    resolver = CacheResolver(
        model=model,
        prompt_version=prompt_version,
        cache_index=cache_index,
        hits=0,
    )
    hits = sum(
        1
        for record in query_records
        if resolve_entry_with_resolver(
            resolver,
            record,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        is not None
    )
    return CacheResolver(
        model=model,
        prompt_version=prompt_version,
        cache_index=cache_index,
        hits=hits,
    )


def resolve_entry_with_resolver(
    resolver: CacheResolver,
    record: QueryRecord,
    *,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any] | None:
    lookup_key = make_cache_lookup_key(
        model=resolver.model,
        prompt_version=resolver.prompt_version,
        user_input=record.query,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=DEFAULT_RESPONSE_FORMAT,
    )
    entries = resolver.cache_index.get(lookup_key)
    if not entries:
        return None
    return entries[-1]


def validate_score_shapes(
    *,
    old_scores: dict[str, list[float]],
    new_scores: dict[str, list[float]],
    query_records: list[QueryRecord],
    configs: list[str],
) -> None:
    expected_rows = len(query_records)
    for config in configs:
        old_len = len(old_scores[config])
        new_len = len(new_scores[config])
        if old_len != new_len:
            raise ValueError(
                f"Config '{config}' has different row counts: old={old_len}, new={new_len}"
            )
        if old_len != expected_rows:
            raise ValueError(
                f"Config '{config}' has {old_len} rows, but synthetic query order has {expected_rows}"
            )


def payloads_differ(
    old_payload: dict[str, Any] | None, new_payload: dict[str, Any] | None
) -> bool:
    if old_payload is None or new_payload is None:
        return False
    return old_payload["extracted"] != new_payload["extracted"]


def summarize_differences(
    *,
    old_scores: dict[str, list[float]],
    new_scores: dict[str, list[float]],
    configs: list[str],
    query_records: list[QueryRecord],
    old_resolver: CacheResolver,
    new_resolver: CacheResolver,
    temperature: float,
    max_tokens: int,
) -> list[dict[str, Any]]:
    differing_rows: list[dict[str, Any]] = []

    for record in query_records:
        per_config: dict[str, dict[str, float]] = {}
        deltas: list[float] = []
        for config in configs:
            old_value = old_scores[config][record.index]
            new_value = new_scores[config][record.index]
            if abs(old_value - new_value) < 1e-12:
                continue
            delta = new_value - old_value
            per_config[config] = {"old": old_value, "new": new_value, "delta": delta}
            deltas.append(delta)

        old_entry = resolve_entry_with_resolver(
            old_resolver,
            record,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        new_entry = resolve_entry_with_resolver(
            new_resolver,
            record,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        response_changed = payloads_differ(
            parse_cache_payload(old_entry), parse_cache_payload(new_entry)
        )

        if per_config or response_changed:
            average_delta = sum(deltas) / len(deltas) if deltas else 0.0
            differing_rows.append(
                {
                    "index": record.index,
                    "config_scores": per_config,
                    "average_delta": average_delta,
                    "worst_delta": min(deltas) if deltas else 0.0,
                    "best_delta": max(deltas) if deltas else 0.0,
                    "score_changed": bool(per_config),
                    "response_changed": response_changed,
                }
            )

    differing_rows.sort(key=lambda row: (row["average_delta"], row["index"]))
    return differing_rows


def filter_rows(
    rows: list[dict[str, Any]], show_all_differences: bool
) -> list[dict[str, Any]]:
    if show_all_differences:
        return rows
    return [row for row in rows if row["response_changed"] or row["average_delta"] < 0]


def payload_question(payload: dict[str, Any] | None) -> str | None:
    if payload is None:
        return None
    metadata = payload.get("metadata", {})
    request = metadata.get("request", {})
    if isinstance(request, dict):
        user_input = request.get("user_input")
        if isinstance(user_input, str):
            return user_input
    return None


def score_direction(row: dict[str, Any]) -> str:
    if not row["score_changed"]:
        return "unchanged"
    if row["average_delta"] > 1e-12:
        return "better"
    if row["average_delta"] < -1e-12:
        return "worse"
    if row["worst_delta"] < 0 and row["best_delta"] > 0:
        return "mixed"
    return "unchanged"


def print_header(
    args: argparse.Namespace,
    old_resolver: CacheResolver,
    new_resolver: CacheResolver,
    configs: list[str],
    total_queries: int,
) -> None:
    print(f"Old scores: {args.old_scores}")
    print(f"New scores: {args.new_scores}")
    print(f"Cache:      {args.cache}")
    print(f"Old model:  {args.old_model} ({old_resolver.prompt_version})")
    print(f"New model:  {args.new_model} ({new_resolver.prompt_version})")
    print(f"Settings:   temperature={args.temperature}, max_tokens={args.max_tokens}")
    print(f"Configs:    {', '.join(configs)}")
    print(
        "Cache hits: "
        f"old={old_resolver.hits}/{total_queries}, "
        f"new={new_resolver.hits}/{total_queries}"
    )
    print()


def print_row_report(
    *,
    row: dict[str, Any],
    record: QueryRecord,
    old_payload: dict[str, Any] | None,
    new_payload: dict[str, Any] | None,
) -> None:
    print("=" * 100)
    print(
        f"Query index {record.index} | score_changed={row['score_changed']} | "
        f"score={score_direction(row)} | response_changed={row['response_changed']} | "
        f"avg delta {row['average_delta']:+.3f} | "
        f"worst {row['worst_delta']:+.3f} | best {row['best_delta']:+.3f}"
    )
    print(f"Dataset: {record.dataset}")
    print(
        f"Document index: {record.document_index} | Query index in document: {record.query_index}"
    )
    print(f"DOI: {record.doi}")
    print(f"Min position: {record.min_position}")
    print(f"Query: {record.query}")
    print(
        f"Old cached question: {payload_question(old_payload) or '<cache entry not found>'}"
    )
    print(
        f"New cached question: {payload_question(new_payload) or '<cache entry not found>'}"
    )
    print("Per-config score differences:")
    if row["config_scores"]:
        for config, values in row["config_scores"].items():
            print(
                f"  - {config}: old={values['old']:.3f}, new={values['new']:.3f}, delta={values['delta']:+.3f}"
            )
    else:
        print("  <no score differences>")

    if old_payload is not None:
        print("Old extracted JSON:")
        print(pretty_json(old_payload["extracted"]))
    else:
        print("Old extracted JSON: <cache entry not found>")

    if new_payload is not None:
        print("New extracted JSON:")
        print(pretty_json(new_payload["extracted"]))
    else:
        print("New extracted JSON: <cache entry not found>")

    if old_payload is not None and new_payload is not None:
        diff_text = build_json_diff(old_payload["extracted"], new_payload["extracted"])
        print("Extracted JSON diff:")
        if diff_text:
            print(diff_text)
        else:
            print("<no JSON diff>")


def run_report(args: argparse.Namespace) -> None:
    old_scores = load_json(args.old_scores)
    new_scores = load_json(args.new_scores)
    cache_data = load_json(args.cache)
    cache_entries = cache_data.get("entries", {})
    cache_index = build_cache_index(cache_entries)

    query_records = flatten_queries()

    shared_configs = sorted(set(old_scores) & set(new_scores))
    if args.configs:
        configs = [config for config in args.configs if config in shared_configs]
        missing = sorted(set(args.configs) - set(configs))
        if missing:
            raise ValueError(
                f"Requested configs not found in both files: {', '.join(missing)}"
            )
    else:
        configs = shared_configs

    if not configs:
        raise ValueError("No shared configs to compare")

    validate_score_shapes(
        old_scores=old_scores,
        new_scores=new_scores,
        query_records=query_records,
        configs=configs,
    )

    old_prompt_version = args.old_prompt_version or detect_prompt_version(
        model=args.old_model,
        cache_entries=cache_entries,
    )
    new_prompt_version = args.new_prompt_version or detect_prompt_version(
        model=args.new_model,
        cache_entries=cache_entries,
    )

    old_resolver = build_cache_resolver(
        cache_index=cache_index,
        model=args.old_model,
        prompt_version=old_prompt_version,
        query_records=query_records,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    new_resolver = build_cache_resolver(
        cache_index=cache_index,
        model=args.new_model,
        prompt_version=new_prompt_version,
        query_records=query_records,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    print_header(
        args,
        old_resolver,
        new_resolver,
        configs,
        len(query_records),
    )

    differing_rows = summarize_differences(
        old_scores=old_scores,
        new_scores=new_scores,
        configs=configs,
        query_records=query_records,
        old_resolver=old_resolver,
        new_resolver=new_resolver,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )
    differing_rows = filter_rows(differing_rows, args.show_all_differences)

    print(f"Found {len(differing_rows)} differing query rows after filtering.")
    print()

    for row in differing_rows[: args.limit]:
        record = query_records[row["index"]]
        old_entry = resolve_entry_with_resolver(
            old_resolver,
            record,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        new_entry = resolve_entry_with_resolver(
            new_resolver,
            record,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        print_row_report(
            row=row,
            record=record,
            old_payload=parse_cache_payload(old_entry),
            new_payload=parse_cache_payload(new_entry),
        )

    if len(differing_rows) > args.limit:
        remaining = len(differing_rows) - args.limit
        print("=" * 100)
        print(
            f"Truncated output. {remaining} additional differing rows were not printed."
        )


def main() -> None:
    args = parse_args()
    if args.output is None:
        run_report(args)
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with (
        args.output.open("w", encoding="utf-8") as output_file,
        contextlib.redirect_stdout(output_file),
    ):
        run_report(args)
    print(f"Wrote comparison report to {args.output}")


if __name__ == "__main__":
    main()
