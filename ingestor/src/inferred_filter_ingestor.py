"""Populate `filter` with LLM-inferred key/value pairs.

This ingestor:
- reads selected non-inferred source filters per document,
- compacts and clusters noisy metadata before each LLM call,
- asks the configured LLM to infer extra searchable filters,
- resolves proposed keys against existing canonical keys with a strict similarity check,
- inserts inferred rows with SQL-side deduplication against existing non-inferred filters, and
- creates `filter_description` rows only for genuinely new keys.
"""

import json
import logging
import re
from collections import defaultdict
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from base_filter_ingestor import BaseFilterIngestor
from openai import AzureOpenAI, OpenAI


class InferredFilterIngestor(BaseFilterIngestor):
    logger = logging.getLogger("InferredFilterIngestor")

    DEFAULT_SOURCE_KEYS: tuple[str, ...] = (
        "abstract",
        "attributes.descriptions.description",
        "attributes.titles.title",
        "descriptions.description",
        "description",
        "investigation.summary",
        "investigation.title",
        "parameters.comments",
        "parameters.Sample_description",
        "parameters.SamplePatient_info",
        "samples.parameters.Sample_description",
        "samples.parameters.SamplePatient_info",
        "summary",
        "title",
        "titles.title",
        "scientificMetadata.title",
        "scientificMetadata.measurement.proposalTitle",
        "parameters.SamplePatient_organ_description",
    )

    _INFERENCE_BATCH_SIZE: int = 25
    _MAX_INFERRED_FILTERS_PER_DOCUMENT: int = 12
    _MAX_SOURCE_ROWS_PER_CLUSTER: int = 20
    _STRICT_SIMILARITY_THRESHOLD: float = 0.2
    _MIN_DISTANCE_GAP: float = 0.04

    def __init__(
        self,
        db_conn_factory: Callable[[], AbstractContextManager[Any]],
        settings,
        document_ids: list[int] | None = None,
        dry_run: bool = False,
        model_name: str | None = None,
    ) -> None:
        super().__init__(db_conn_factory, settings)
        self.source_keys = self.DEFAULT_SOURCE_KEYS
        self.document_ids = document_ids or []
        self.dry_run = dry_run
        self.model_name = model_name or self.settings.default_model_name
        if settings.llm_provider == "openai":
            self.llm = OpenAI(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
            )
        else:
            self.llm = AzureOpenAI(
                api_key=settings.azure_openai_api_key,
                azure_endpoint=settings.azure_openai_endpoint,
                api_version=settings.azure_openai_api_version,
            )
        self._normalized_key_index: dict[str, list[str]] = {}
        self._normalized_description_index: dict[str, list[str]] = {}
        self._resolution_cache: dict[str, tuple[str, bool]] = {}

    @staticmethod
    def _collapse_spaces(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _normalize_description_text(self, value: str) -> str:
        return self._collapse_spaces(value).lower()

    def _normalize_new_key_name(self, value: str) -> str:
        return self._collapse_spaces(value).lower()

    def _load_existing_indexes(self, cursor) -> None:
        cursor.execute("SELECT name FROM filter_key")
        key_rows = cursor.fetchall()
        normalized_key_index: dict[str, list[str]] = defaultdict(list)
        for row in key_rows:
            key_name = row[0]
            normalized_key_index[self.normalize_filter_key(key_name)].append(key_name)

        cursor.execute("SELECT filter_key_name, description FROM filter_description")
        description_rows = cursor.fetchall()
        normalized_description_index: dict[str, list[str]] = defaultdict(list)
        for row in description_rows:
            key_name, description = row
            normalized_description_index[
                self._normalize_description_text(description)
            ].append(key_name)

        self._normalized_key_index = dict(normalized_key_index)
        self._normalized_description_index = dict(normalized_description_index)

    def _fetch_source_rows(self, cursor) -> list[tuple[int, str, str]]:
        query = """
            SELECT document_id, key, value
            FROM filter
            WHERE key = ANY(%s)
              AND type IS DISTINCT FROM 'INFERRED'::filter_type
              AND value IS NOT NULL
              AND btrim(value) <> ''
        """
        params: list[Any] = [list(self.source_keys)]

        if self.document_ids:
            query += "\n              AND document_id = ANY(%s)"
            params.append(self.document_ids)

        query += "\n            ORDER BY document_id, key, value"
        cursor.execute(
            query,
            tuple(params),
        )
        return cursor.fetchall()

    def _group_source_rows(
        self, source_rows: list[tuple[int, str, str]]
    ) -> list[tuple[int, list[dict[str, str]]]]:
        grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
        seen_rows: set[tuple[int, str, str]] = set()
        for document_id, key, value in source_rows:
            row_id = (document_id, key, value)
            if row_id in seen_rows:
                continue
            seen_rows.add(row_id)
            grouped[document_id].append({"key": key, "value": value})
        return [(document_id, grouped[document_id]) for document_id in sorted(grouped)]

    def _build_inference_prompt(self, source_rows: list[dict[str, str]]) -> str:
        payload = {
            "source_filters": [
                {
                    "index": index,
                    "key": row["key"],
                    "value": row["value"],
                }
                for index, row in enumerate(source_rows)
            ],
            "max_filters": self._MAX_INFERRED_FILTERS_PER_DOCUMENT,
        }
        return json.dumps(payload, ensure_ascii=True)

    def _cluster_source_rows(
        self, source_rows: list[dict[str, str]]
    ) -> list[list[dict[str, str]]]:
        if len(source_rows) <= self._MAX_SOURCE_ROWS_PER_CLUSTER:
            return [source_rows]

        cluster_row_budget = self._MAX_SOURCE_ROWS_PER_CLUSTER
        rows_by_key: dict[str, list[dict[str, str]]] = defaultdict(list)
        key_order: list[str] = []
        for row in source_rows:
            key = row["key"]
            if key not in rows_by_key:
                key_order.append(key)
            rows_by_key[key].append(row)

        clusters: list[list[dict[str, str]]] = []
        current_cluster_rows: list[dict[str, str]] = []
        for key in key_order:
            key_rows = rows_by_key[key]
            if len(key_rows) > cluster_row_budget:
                if current_cluster_rows:
                    clusters.append(current_cluster_rows)
                    current_cluster_rows = []
                for start in range(0, len(key_rows), cluster_row_budget):
                    clusters.append(key_rows[start : start + cluster_row_budget])
                continue

            if len(current_cluster_rows) + len(key_rows) > cluster_row_budget:
                clusters.append(current_cluster_rows)
                current_cluster_rows = []

            current_cluster_rows.extend(key_rows)

        if current_cluster_rows:
            clusters.append(current_cluster_rows)

        return clusters or [source_rows]

    @staticmethod
    def _system_prompt() -> str:
        return """You infer extra searchable metadata filters from existing document metadata.

Return JSON with this exact shape:
{
  "filters": [
    {
      "name": "short proposed key name",
      "description": "short semantic description of the key",
      "value": "string or number or boolean value",
            "unit": "optional unit",
            "evidence_indices": [0, 2]
    }
  ]
}

Rules:
- Infer only filters that help users find documents more easily.
- Use concise, reusable key names.
- Do not return filters already explicitly present in the source list unless the inferred value is meaningfully more discoverable.
- Skip weak guesses.
- Do not emit empty names, descriptions, or values.
- The description explains the meaning of the key, not the current value.
- evidence_indices must contain source_filters.index values that directly support the inferred value.
- Cite only rows that are real evidence for the inferred value.
- Return at most the requested max_filters.
- Output valid JSON only.
"""

    def _infer_filters(self, source_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
        response = self.llm.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._build_inference_prompt(source_rows)},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=1200,
        )
        content = (
            response.choices[0].message.content
            if response and response.choices
            else None
        )
        return self._parse_llm_response(content)

    def _parse_llm_response(self, content: str | None) -> list[dict[str, Any]]:
        if not content:
            return []

        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            self.logger.warning(
                "Skipping malformed inferred-filter response: %s", content
            )
            return []

        raw_filters = payload.get("filters", []) if isinstance(payload, dict) else []
        if not isinstance(raw_filters, list):
            return []

        parsed_filters: list[dict[str, Any]] = []
        for raw_filter in raw_filters:
            if not isinstance(raw_filter, dict):
                continue

            name = self._collapse_spaces(str(raw_filter.get("name") or ""))
            description = self._collapse_spaces(
                str(raw_filter.get("description") or "")
            )
            unit_value = raw_filter.get("unit")
            unit = (
                self._collapse_spaces(str(unit_value))
                if unit_value not in (None, "")
                else None
            )
            value = raw_filter.get("value")
            evidence_indices_value = raw_filter.get("evidence_indices")

            if not name or not description or value in (None, ""):
                continue

            if isinstance(value, (dict, list)):
                continue

            evidence_indices: list[int] = []
            if isinstance(evidence_indices_value, list):
                seen_indices: set[int] = set()
                for raw_index in evidence_indices_value:
                    if isinstance(raw_index, int):
                        parsed_index = raw_index
                    elif isinstance(raw_index, str) and raw_index.isdigit():
                        parsed_index = int(raw_index)
                    else:
                        continue

                    if parsed_index < 0 or parsed_index in seen_indices:
                        continue

                    seen_indices.add(parsed_index)
                    evidence_indices.append(parsed_index)

            parsed_filters.append(
                {
                    "name": name,
                    "description": description,
                    "value": str(value).strip(),
                    "unit": unit,
                    "evidence_indices": evidence_indices,
                }
            )

        return parsed_filters[: self._MAX_INFERRED_FILTERS_PER_DOCUMENT]

    def _resolve_evidence_rows(
        self, source_rows: list[dict[str, str]], evidence_indices: list[int]
    ) -> set[tuple[str, str]]:
        evidence_rows: set[tuple[str, str]] = set()
        for evidence_index in evidence_indices:
            if evidence_index < 0 or evidence_index >= len(source_rows):
                continue
            evidence_row = source_rows[evidence_index]
            evidence_rows.add((evidence_row["key"], evidence_row["value"]))

        return evidence_rows

    def _build_candidates_for_source_cluster(
        self, cursor, document_id: int, source_rows: list[dict[str, str]]
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen_rows: set[tuple[int, str, str, str | None, str]] = set()

        for inferred_filter in self._infer_filters(source_rows):
            resolved = self._resolve_key(cursor, inferred_filter["name"])
            if resolved is None:
                continue

            resolved_key, is_new_key = resolved
            row = (
                document_id,
                resolved_key,
                inferred_filter["value"],
                inferred_filter["unit"],
                "INFERRED",
            )
            if row in seen_rows:
                continue

            seen_rows.add(row)
            candidates.append(
                {
                    "row": row,
                    "key_name": resolved_key,
                    "description_row": (
                        (resolved_key, inferred_filter["description"])
                        if is_new_key
                        else None
                    ),
                    "evidence_rows": self._resolve_evidence_rows(
                        source_rows,
                        inferred_filter.get("evidence_indices", []),
                    ),
                }
            )

        return candidates

    def _resolve_exact_key_match(self, proposed_name: str) -> tuple[str, bool] | None:
        normalized_name = self.normalize_filter_key(proposed_name)
        exact_key_matches = self._normalized_key_index.get(normalized_name, [])
        if len(exact_key_matches) == 1:
            return exact_key_matches[0], False
        if len(exact_key_matches) > 1:
            return None

        exact_description_matches = self._normalized_description_index.get(
            self._normalize_description_text(proposed_name), []
        )
        if len(exact_description_matches) == 1:
            return exact_description_matches[0], False
        if len(exact_description_matches) > 1:
            return None

        return None

    def _resolve_similarity_match(
        self, cursor, proposed_name: str
    ) -> tuple[str, bool] | None:
        query_text = self.normalize_filter_key(proposed_name)
        query_vector = self.encoder.encode(query_text).tolist()
        cursor.execute(
            """
            WITH key_matches AS (
                SELECT name AS filter_key_name, name_vector <=> %s::vector AS distance
                FROM filter_key
            ),
            description_matches AS (
                SELECT filter_key_name, description_vector <=> %s::vector AS distance
                FROM filter_description
                WHERE description_vector IS NOT NULL
            ),
            combined AS (
                SELECT filter_key_name, MIN(distance) AS distance
                FROM (
                    SELECT filter_key_name, distance FROM key_matches
                    UNION ALL
                    SELECT filter_key_name, distance FROM description_matches
                ) matches
                GROUP BY filter_key_name
            )
            SELECT filter_key_name, distance
            FROM combined
            ORDER BY distance ASC
            LIMIT 2
            """,
            (query_vector, query_vector),
        )
        matches = cursor.fetchall()
        if not matches:
            return None

        best_name, best_distance = matches[0]
        if best_distance > self._STRICT_SIMILARITY_THRESHOLD:
            return None

        if len(matches) > 1:
            _, second_distance = matches[1]
            if second_distance - best_distance < self._MIN_DISTANCE_GAP:
                self.logger.info(
                    "Skipping ambiguous inferred key '%s' (best=%s second=%s)",
                    proposed_name,
                    best_distance,
                    second_distance,
                )
                return None

        return best_name, False

    def _resolve_key(self, cursor, proposed_name: str) -> tuple[str, bool] | None:
        cached = self._resolution_cache.get(proposed_name)
        if cached is not None:
            return cached

        exact_match = self._resolve_exact_key_match(proposed_name)
        if exact_match is not None:
            self._resolution_cache[proposed_name] = exact_match
            return exact_match

        similarity_match = self._resolve_similarity_match(cursor, proposed_name)
        if similarity_match is not None:
            self._resolution_cache[proposed_name] = similarity_match
            return similarity_match

        new_key = self._normalize_new_key_name(proposed_name)
        if not new_key:
            return None

        resolved = (new_key, True)
        self._resolution_cache[proposed_name] = resolved
        self._normalized_key_index.setdefault(
            self.normalize_filter_key(new_key), []
        ).append(new_key)
        return resolved

    def _delete_existing_inferred_rows(self, cursor, document_ids: list[int]) -> None:
        if not document_ids:
            return
        cursor.execute(
            """
            DELETE FROM filter
            WHERE type = 'INFERRED'::filter_type
              AND document_id = ANY(%s)
            """,
            (document_ids,),
        )

    def _insert_filter_rows(
        self, cursor, filter_rows: list[tuple[int, str, str, str | None, str]]
    ) -> None:
        if not filter_rows:
            return

        document_ids = [document_id for document_id, _, _, _, _ in filter_rows]
        keys = [key for _, key, _, _, _ in filter_rows]
        values = [value for _, _, value, _, _ in filter_rows]
        units = [unit for _, _, _, unit, _ in filter_rows]

        cursor.execute(
            """
            WITH candidate_rows AS (
                SELECT DISTINCT
                    candidate.document_id,
                    candidate.key,
                    candidate.value,
                    candidate.unit
                FROM unnest(
                    %s::int[],
                    %s::text[],
                    %s::text[],
                    %s::text[]
                ) AS candidate(document_id, key, value, unit)
            )
            INSERT INTO filter (document_id, key, value, unit, type)
            SELECT
                candidate.document_id,
                candidate.key,
                candidate.value,
                candidate.unit,
                'INFERRED'::filter_type
            FROM candidate_rows candidate
            WHERE NOT EXISTS (
                SELECT 1
                FROM filter existing
                WHERE existing.document_id = candidate.document_id
                  AND existing.key = candidate.key
                  AND existing.value = candidate.value
                  AND existing.unit IS NOT DISTINCT FROM candidate.unit
                  AND existing.type IS DISTINCT FROM 'INFERRED'::filter_type
            )
            """,
            (document_ids, keys, values, units),
        )

    def _insert_key_descriptions(
        self, cursor, description_rows: list[tuple[str, str]]
    ) -> None:
        unique_rows = list(dict.fromkeys(description_rows))
        if not unique_rows:
            return

        descriptions = [description for _, description in unique_rows]
        vectors = self.encoder.encode(descriptions)
        if hasattr(vectors, "tolist"):
            vectors = vectors.tolist()

        cursor.executemany(
            """
            INSERT INTO filter_description (filter_key_name, description, description_vector)
            VALUES (%s, %s, %s)
            ON CONFLICT (filter_key_name, description) DO NOTHING
            """,
            [
                (filter_key_name, description, vector)
                for (filter_key_name, description), vector in zip(
                    unique_rows, vectors, strict=True
                )
            ],
        )

        for filter_key_name, description in unique_rows:
            normalized_description = self._normalize_description_text(description)
            existing = self._normalized_description_index.setdefault(
                normalized_description, []
            )
            if filter_key_name not in existing:
                existing.append(filter_key_name)

    def _log_dry_run_results(
        self,
        document_id: int,
        cluster_index: int,
        cluster_count: int,
        source_rows: list[dict[str, str]],
        filter_rows: list[tuple[int, str, str, str | None, str]],
        description_rows: list[tuple[str, str]],
    ) -> None:
        payload = {
            "document_id": document_id,
            "cluster_index": cluster_index,
            "cluster_count": cluster_count,
            "source_filters": source_rows,
            "filters": [
                {
                    "key": key,
                    "value": value,
                    "unit": unit,
                    "type": row_type,
                }
                for _, key, value, unit, row_type in filter_rows
            ],
            "new_key_descriptions": [
                {"key": filter_key_name, "description": description}
                for filter_key_name, description in description_rows
            ],
        }
        self.logger.info(
            "Dry run inferred filters: %s", json.dumps(payload, ensure_ascii=True)
        )

    def _build_rows_for_source_cluster(
        self, cursor, document_id: int, source_rows: list[dict[str, str]]
    ) -> tuple[
        list[tuple[int, str, str, str | None, str]],
        list[str],
        list[tuple[str, str]],
    ]:
        candidates = self._build_candidates_for_source_cluster(
            cursor,
            document_id,
            source_rows,
        )
        return (
            [candidate["row"] for candidate in candidates],
            [candidate["key_name"] for candidate in candidates],
            [
                candidate["description_row"]
                for candidate in candidates
                if candidate["description_row"] is not None
            ],
        )

    def _infer_document_clusters(
        self, cursor, document_id: int, source_rows: list[dict[str, str]]
    ) -> list[
        tuple[
            int,
            list[dict[str, str]],
            list[tuple[int, str, str, str | None, str]],
            list[str],
            list[tuple[str, str]],
            list[dict[str, Any]],
        ]
    ]:
        cluster_results: list[
            tuple[
                int,
                list[dict[str, str]],
                list[tuple[int, str, str, str | None, str]],
                list[str],
                list[tuple[str, str]],
                list[dict[str, Any]],
            ]
        ] = []
        for cluster_index, source_cluster in enumerate(
            self._cluster_source_rows(source_rows), start=1
        ):
            cluster_candidates = self._build_candidates_for_source_cluster(
                cursor,
                document_id,
                source_cluster,
            )
            cluster_results.append(
                (
                    cluster_index,
                    source_cluster,
                    [candidate["row"] for candidate in cluster_candidates],
                    [candidate["key_name"] for candidate in cluster_candidates],
                    [
                        candidate["description_row"]
                        for candidate in cluster_candidates
                        if candidate["description_row"] is not None
                    ],
                    cluster_candidates,
                )
            )

        return cluster_results

    def _select_supported_document_candidates(
        self,
        document_id: int,
        cluster_candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        aggregated_candidates: dict[
            tuple[int, str, str, str | None, str],
            dict[str, Any],
        ] = {}

        for candidate in cluster_candidates:
            row = candidate["row"]
            existing = aggregated_candidates.get(row)
            if existing is None:
                aggregated_candidates[row] = {
                    "row": row,
                    "key_name": candidate["key_name"],
                    "description_row": candidate["description_row"],
                    "evidence_rows": set(candidate["evidence_rows"]),
                    "cluster_count": 1,
                }
                continue

            existing["evidence_rows"].update(candidate["evidence_rows"])
            existing["cluster_count"] += 1
            if (
                existing["description_row"] is None
                and candidate["description_row"] is not None
            ):
                existing["description_row"] = candidate["description_row"]

        candidates_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in aggregated_candidates.values():
            candidates_by_key[candidate["key_name"]].append(candidate)

        selected_candidates: list[dict[str, Any]] = []
        for key_name, candidates_for_key in candidates_by_key.items():
            if len(candidates_for_key) == 1:
                selected_candidates.append(candidates_for_key[0])
                continue

            ranked_candidates = sorted(
                candidates_for_key,
                key=lambda candidate: (
                    len(candidate["evidence_rows"]),
                    candidate["cluster_count"],
                ),
                reverse=True,
            )

            best_candidate = ranked_candidates[0]
            second_candidate = ranked_candidates[1]
            best_score = (
                len(best_candidate["evidence_rows"]),
                best_candidate["cluster_count"],
            )
            second_score = (
                len(second_candidate["evidence_rows"]),
                second_candidate["cluster_count"],
            )

            if best_score > second_score:
                selected_candidates.append(best_candidate)
                continue

            self.logger.info(
                "Skipping ambiguous inferred values for key '%s' on document %s",
                key_name,
                document_id,
            )

        return selected_candidates

    def _build_rows_for_document(
        self, cursor, document_id: int, source_rows: list[dict[str, str]]
    ) -> tuple[
        list[tuple[int, str, str, str | None, str]], list[str], list[tuple[str, str]]
    ]:
        aggregated_cluster_candidates: list[dict[str, Any]] = []

        for (
            _,
            _,
            _,
            _,
            _,
            cluster_candidates,
        ) in self._infer_document_clusters(cursor, document_id, source_rows):
            aggregated_cluster_candidates.extend(cluster_candidates)

        selected_candidates = self._select_supported_document_candidates(
            document_id,
            aggregated_cluster_candidates,
        )

        return (
            [candidate["row"] for candidate in selected_candidates],
            [candidate["key_name"] for candidate in selected_candidates],
            [
                candidate["description_row"]
                for candidate in selected_candidates
                if candidate["description_row"] is not None
            ],
        )

    def run(self) -> None:
        self.logger.info("Starting inferred filter ingestion...")
        try:
            with self.db_conn_factory() as conn, conn.cursor() as cursor:
                self._load_existing_indexes(cursor)
                source_rows = self._fetch_source_rows(cursor)

            grouped_rows = self._group_source_rows(source_rows)
            if not grouped_rows:
                self.logger.info("No source filter rows found for inferred ingestion")
                return

            for start in range(0, len(grouped_rows), self._INFERENCE_BATCH_SIZE):
                batch = grouped_rows[start : start + self._INFERENCE_BATCH_SIZE]
                document_ids = [document_id for document_id, _ in batch]

                if self.dry_run:
                    with self.db_conn_factory() as conn, conn.cursor() as cursor:
                        for document_id, document_source_rows in batch:
                            cluster_results = self._infer_document_clusters(
                                cursor,
                                document_id,
                                document_source_rows,
                            )
                            cluster_count = len(cluster_results)
                            for (
                                cluster_index,
                                source_cluster,
                                filter_rows,
                                _,
                                description_rows,
                                _,
                            ) in cluster_results:
                                self._log_dry_run_results(
                                    document_id,
                                    cluster_index,
                                    cluster_count,
                                    source_cluster,
                                    filter_rows,
                                    description_rows,
                                )

                    self.logger.info(
                        "Dry run processed inferred filters for documents %d-%d",
                        start + 1,
                        start + len(batch),
                    )
                    continue

                with self.db_conn_factory() as conn, conn.cursor() as cursor:
                    self._delete_existing_inferred_rows(cursor, document_ids)

                    batch_filter_rows: list[tuple[int, str, str, str | None, str]] = []
                    batch_key_names: list[str] = []
                    batch_description_rows: list[tuple[str, str]] = []

                    for document_id, document_source_rows in batch:
                        filter_rows, key_names, description_rows = (
                            self._build_rows_for_document(
                                cursor, document_id, document_source_rows
                            )
                        )
                        batch_filter_rows.extend(filter_rows)
                        batch_key_names.extend(key_names)
                        batch_description_rows.extend(description_rows)

                    self.insert_filter_keys_with_embeddings(cursor, batch_key_names)
                    self._insert_key_descriptions(cursor, batch_description_rows)
                    self._insert_filter_rows(cursor, batch_filter_rows)
                    conn.commit()

                self.logger.info(
                    "Processed inferred filters for documents %d-%d",
                    start + 1,
                    start + len(batch),
                )

        except Exception:
            self.logger.exception("Error during inferred filter ingestion")
            raise

        self.logger.info("Inferred filter ingestion completed.")
