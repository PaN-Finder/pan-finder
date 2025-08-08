from typing import Any, Dict, List, Set, Tuple, Union, TypedDict
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sentence_transformers import SentenceTransformer

from ...utils import get_logger

NumberTypes = (int, float, complex)


class SearchResult(TypedDict):
    """
    Type definition for the result returned by SearchQueryBuilder.build_query().
    Matches the structure of the SQL query results.
    """

    doi: str
    overall_score: float
    similarity_score: float
    chunk_similarity_score: float
    full_match_score: float
    partial_match_score: float
    keyword_score: float


class SearchQueryBuilder:
    """
    Builds a complex SQL query for searching documents.
    """

    # --- Constants ---
    # Similarity threshold for finding similar filter names
    _SIMILARITY_THRESHOLD_NAMES: float = 0.5
    # Similarity threshold for document title/summary vs intention
    _SIMILARITY_THRESHOLD_DOCS: float = 0.5
    # Similarity threshold for document chunks vs intention
    _SIMILARITY_THRESHOLD_CHUNKS: float = 0.5
    # Final result limit
    _FINAL_LIMIT: int = 20
    # Default RRF K value (can be used as a common default)
    _DEFAULT_RRF_K: int = 6

    def __init__(
        self,
        embedding_model: SentenceTransformer,
        pool: ConnectionPool,  # PostgreSQL
        rrf_k_similarity: int = _DEFAULT_RRF_K,
        rrf_k_chunk: int = _DEFAULT_RRF_K,
        rrf_k_full_match: int = _DEFAULT_RRF_K,
        rrf_k_partial_match: int = _DEFAULT_RRF_K,
        rrf_k_keyword: int = _DEFAULT_RRF_K,
    ):
        self.embedding_model = embedding_model
        self.pool = pool
        self.rrf_k_similarity = rrf_k_similarity
        self.rrf_k_chunk = rrf_k_chunk
        self.rrf_k_full_match = rrf_k_full_match
        self.rrf_k_partial_match = rrf_k_partial_match
        self.rrf_k_keyword = rrf_k_keyword
        self._logger = get_logger(self.__class__.__name__)

    # --- Attributes ---
    # Similarity names for filters (debugging purposes)
    similar_names = {}

    # --- Public Methods ---
    def build_query(self, data: Dict[str, Any]) -> str:
        """
        Constructs the final SQL search query based on the input data.

        Args:
            data: A dictionary containing search parameters like 'intention',
                  'keywords', and 'filters'.

        Returns:
            A string containing the full SQL query.
        """
        if not isinstance(data, dict):
            raise ValueError("Input 'data' must be a dictionary.")

        # 1. Preprocess: Update filter names with similar ones
        self.similar_names = {}
        processed_data = self._update_filter_names(data)
        self._logger.info(
            f"Processed filter names: {processed_data.get('filters', 'N/A')}"
        )

        # 2. Prepare components
        intention = processed_data.get("intention", "")

        intention_vector = (
            self.embedding_model.encode(intention).tolist() if intention != "" else None
        )
        similarity_subquery_sql = self._build_similarity_query(intention_vector)
        chunk_similarity_subquery_sql = self._build_chunk_similarity_query(
            intention_vector
        )

        keywords_sql = self._prepare_keywords_sql(processed_data.get("keywords", []))
        # Pass the root filter object to _build_filter_logic to initialize counter correctly
        filter_subquery_sql = self._build_filter_subquery(processed_data.get("filters"))

        # 3. Assemble the final query
        final_sql = f"""
        SELECT
            searches.doi,
            sum(
                rrf_score(similarity_rank, {self.rrf_k_similarity}) +
                rrf_score(chunk_similarity_rank, {self.rrf_k_chunk}) +
                rrf_score(full_match_rank, {self.rrf_k_full_match}) +
                rrf_score(partial_match_rank, {self.rrf_k_partial_match}) +
                rrf_score(keyword_rank, {self.rrf_k_keyword})
            ) AS overall_score,
            sum(rrf_score(similarity_rank, {self.rrf_k_similarity})) AS similarity_score,
            sum(rrf_score(chunk_similarity_rank, {self.rrf_k_chunk})) AS chunk_similarity_score,
            sum(rrf_score(full_match_rank, {self.rrf_k_full_match})) AS full_match_score,
            sum(rrf_score(partial_match_rank, {self.rrf_k_partial_match})) AS partial_match_score,
            sum(rrf_score(keyword_rank, {self.rrf_k_keyword})) AS keyword_score
        FROM (
            -- Subquery 1: Document Similarity (title + summary (generated))
            (
                {similarity_subquery_sql}
            )
            UNION ALL
            -- Subquery 2: Chunk Similarity (title + text chunks)
            (
                {chunk_similarity_subquery_sql}
            )
            UNION ALL
            -- Subquery 3: Hard Filter Matches
            (
                {filter_subquery_sql}
            )
            UNION ALL
            -- Subquery 4: Keywords (Full-Text Search)
            (
                SELECT
                    d.doi,
                    0 AS similarity_rank,
                    0 AS chunk_similarity_rank,
                    0 AS full_match_rank,
                    0 AS partial_match_rank,
                    DENSE_RANK() OVER (ORDER BY ts_rank_cd(title_text_search_vector, to_tsquery('english', '{keywords_sql}')) DESC) AS keyword_rank
                FROM document d
                WHERE
                    title_text_search_vector @@ to_tsquery('english', '{keywords_sql}')
                    AND '{keywords_sql}' != '' -- Avoid error if keywords are empty
                -- NO ORDER BY here, as we will use the rank to calculate the score
                -- NO LIMIT as we want all DOIs with at least one keyword match
            )
        ) searches
        WHERE searches.doi IS NOT NULL -- Exclude potential NULL DOIs from empty subqueries
        GROUP BY searches.doi
        ORDER BY
            overall_score DESC,
            full_match_score DESC,
            partial_match_score DESC,
            similarity_score DESC,
            chunk_similarity_score DESC,
            keyword_score DESC
        LIMIT {self._FINAL_LIMIT};
        """

        return final_sql

    def _build_similarity_query(self, intention_vector: List | None) -> str:
        if intention_vector is None:
            return self._get_empty_subquery()

        return f"""SELECT
                    d.doi,
                    DENSE_RANK () OVER (ORDER BY d.title_summary_vector <=> '{intention_vector}'::vector ASC) AS similarity_rank,
                    0 AS chunk_similarity_rank,
                    0 AS full_match_rank,
                    0 AS partial_match_rank,
                    0 AS keyword_rank
                FROM document d
                WHERE
                    d.title_summary_vector <=> '{intention_vector}'::vector < {self._SIMILARITY_THRESHOLD_DOCS}"""

    def _build_chunk_similarity_query(self, intention_vector: List | None) -> str:
        if intention_vector is None:
            return self._get_empty_subquery()

        return f"""WITH RankedChunks AS (
                    SELECT
                        d.doi,
                        c.text_vector <=> '{intention_vector}'::vector AS distance, -- Calculate distance for ordering
                        -- Assign a rank to each chunk within its document based on similarity
                        ROW_NUMBER() OVER(PARTITION BY d.doi ORDER BY c.text_vector <=> '{intention_vector}'::vector ASC) as rn_within_doi,
                        -- Count how many chunks *total* for this DOI met the similarity threshold
                        COUNT(*) OVER (PARTITION BY d.doi) as chunk_count_for_doi
                    FROM
                        chunk c
                    JOIN
                        document d ON c.document_id = d.id
                    WHERE
                        c.text_vector <=> '{intention_vector}'::vector < {self._SIMILARITY_THRESHOLD_CHUNKS} -- Pre-filter chunks by similarity threshold
                )
                SELECT
                    rc.doi,
                    0 AS similarity_rank,
                    DENSE_RANK() OVER (ORDER BY rc.distance ASC, rc.chunk_count_for_doi DESC) AS chunk_similarity_rank,
                    -- Primary Sort: Prioritize DOIs whose *best* chunk is most similar (lowest distance)
                    -- Secondary Sort: For DOIs with the *same* best chunk distance, rank those with more qualifying chunks higher
                    0 AS full_match_rank,
                    0 AS partial_match_rank,
                    0 AS keyword_rank
                FROM RankedChunks rc
                WHERE
                    rc.rn_within_doi = 1        -- Select only the single best chunk for each DOI
                -- NO ORDER BY here, as we will use the rank to calculate the score
                -- NO LIMIT as we want all DOIs with at least one chunk meeting the threshold"""

    # --- Private Helper Methods ---
    def _prepare_keywords_sql(self, keywords: List[str]) -> str:
        """Formats keywords for PostgreSQL full-text search ts_query (OR logic)."""
        if not keywords:
            return ""
        # Basic sanitization: remove non-alphanumeric, keep '|', replace spaces with '|'
        processed = "|".join(keywords)
        processed = processed.replace(" ", "|")
        # Remove characters potentially harmful to ts_query (keep alphanumeric and '|')
        sanitized = "".join(c for c in processed if c.isalnum() or c == "|")
        # Remove leading/trailing/multiple pipes
        sanitized = "|".join(filter(None, sanitized.split("|")))
        return sanitized

    # --- Filter Name Similarity ---
    def _find_similar_names(self, raw_name: str) -> list[str]:
        """Finds similar filter names in the database using vector embeddings."""
        if not raw_name:
            return []

        query_vector = self.embedding_model.encode(raw_name).tolist()
        with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cursor,
        ):
            cursor.execute(
                """WITH top_matches AS (
                    SELECT name, name_vector <=> %s::vector AS distance
                    FROM filter_key
                    WHERE name_vector <=> %s::vector < %s
                    ORDER BY distance
                ),
                fallback_matches AS (
                    SELECT name, name_vector <=> %s::vector AS distance
                    FROM filter_key
                    WHERE name_vector <=> %s::vector >= %s
                    ORDER BY distance
                )
                (
                    (
                        SELECT * FROM top_matches
                        ORDER BY distance
                    )
                    UNION ALL
                    (
                        SELECT * FROM fallback_matches
                        ORDER BY distance
                        LIMIT GREATEST(0, 5 - (SELECT COUNT(*) FROM top_matches))
                    )
                )
                ORDER BY distance;
                """,
                (
                    query_vector,
                    query_vector,
                    self._SIMILARITY_THRESHOLD_NAMES,
                    query_vector,
                    query_vector,
                    self._SIMILARITY_THRESHOLD_NAMES,
                ),
            )
            result = cursor.fetchall()
            self._logger.info(
                f"Finding similar names for '{raw_name}'. Found: {[row['name'] for row in result[:5]]}"
            )

            self.similar_names[raw_name] = result

            if len(result) == 0:
                return [raw_name]

            return [row["name"] for row in result]

    def _update_filter_names_recursive(self, filt: Dict) -> Union[Dict, None]:
        """Recursively finds and replaces 'name' in filter conditions."""
        if "conditions" in filt and "logic" in filt:
            updated_conditions = []
            for i, cond in enumerate(filt.get("conditions", [])):
                if isinstance(cond, dict):
                    updated_cond = self._update_filter_names_recursive(cond)
                    if updated_cond:  # Keep condition only if it's valid after update
                        updated_conditions.append(updated_cond)
                else:
                    self._logger.info(
                        f"Skipping invalid condition at index {i}: {cond}"
                    )
            # Return None if a logic block has no valid conditions left
            filt["conditions"] = updated_conditions
            return filt if updated_conditions else None

        elif "name" in filt and "operator" in filt and "value" in filt:
            raw_name = filt.get("name")
            if isinstance(raw_name, str) and raw_name:
                similar_names = self._find_similar_names(raw_name)
                filt["name"] = (
                    similar_names if similar_names else [raw_name]
                )  # Ensure name is always a list
                return filt
            else:
                self._logger.info(
                    f"Skipping condition with invalid or missing name: {filt}"
                )
                return None  # Invalid condition structure
        else:
            self._logger.info(f"Skipping condition with unexpected structure: {filt}")
            return None  # Invalid condition structure

    def _update_filter_names(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Updates the 'filters' part of the data by replacing names with similar ones."""
        filters_obj = data.get("filters")
        if not isinstance(filters_obj, dict) or not filters_obj.get("conditions"):
            self._logger.info(
                "No valid filters found or filters are not a dict, skipping name update."
            )
            return data  # Return original data if no filters or invalid format

        updated_filters = self._update_filter_names_recursive(
            filters_obj.copy()
        )  # Work on a copy

        # Only update data['filters'] if the recursive update returned a valid structure
        if updated_filters and updated_filters.get("conditions"):
            data["filters"] = updated_filters
        else:
            # If filters become empty/invalid after update, remove the key or set to empty
            self._logger.info("Filters became empty or invalid after name update.")
            data["filters"] = None  # Or {} or remove key data.pop('filters', None)

        return data

    # --- Filter Subquery Construction ---
    def _build_filter_subquery(self, filters_obj: Union[Dict, None]) -> str:
        """Builds the SQL subquery for filtering documents based on the filter object."""
        if not filters_obj or not filters_obj.get("conditions"):
            self._logger.info(
                "No valid filters provided, creating empty filter subquery."
            )
            return self._get_empty_subquery()

        try:
            # 1. Generate flag definitions (MAX(CASE...) AS has_condition_N)
            flag_definitions, condition_count = self._generate_filter_flags(filters_obj)
            if not flag_definitions:
                self._logger.info(
                    "Could not generate any filter flags from the provided structure."
                )
                return self._get_empty_subquery()
            flags_sql = ",\n            ".join(flag_definitions)

            # 2. Collect unique keys
            unique_keys = set()
            self._collect_keys_recursive(filters_obj, unique_keys)
            if not unique_keys:
                self._logger.info("No filter keys found in the provided structure.")
                return self._get_empty_subquery()

            # Sort keys for deterministic SQL generation
            sorted_keys = sorted(list(unique_keys))
            keys_sql = ", ".join(f"'{k}'" for k in sorted_keys)

            # 3. Build the logic expression (e.g., (has_condition_1 > 0 AND has_condition_2 > 0) OR has_condition_3 > 0)
            filter_logic_sql = self._build_filter_logic(filters_obj)
            if not filter_logic_sql or filter_logic_sql == "FALSE":
                self._logger.info(
                    "Filter logic resulted in an empty or FALSE condition."
                )
                return self._get_empty_subquery()

            # 4. Construct the filter subquery using CTEs
            # Generate parts for partial match counting and WHERE clause optimization
            partial_match_sum_sql = " + ".join(
                [f"has_condition_{i+1}" for i in range(condition_count)]
            )

            # Only include documents that have at least one condition met
            where_optimization_sql = " OR ".join(
                [f"has_condition_{i+1} > 0" for i in range(condition_count)]
            )

            return f"""
            WITH FilterFlags AS (
                -- Step 1: Calculate flags for each unique base condition per document
                SELECT
                    f.document_id,
                    {flags_sql}
                FROM filter f
                -- Pre-filter rows based on *all* keys involved in the conditions
                WHERE f.key IN ({keys_sql})
                GROUP BY f.document_id
            ),
            FilterLogic AS (
                -- Step 2: Apply the specific AND/OR logic and count partial matches
                SELECT
                    ff.document_id,
                    CASE
                        WHEN {filter_logic_sql}
                        THEN 1 -- The document satisfies the overall logic (Full Match)
                        ELSE 0 -- The document does not satisfy the overall logic (Partial or No Match)
                    END AS full_match_score,
                    -- Sum of individual flags (scores can be 0, 1, or 2)
                    ({partial_match_sum_sql}) AS partial_match_count
                FROM FilterFlags ff
                -- Optimization: Only process documents that matched at least one flag based on score
                WHERE ({where_optimization_sql})
            )
            -- Step 3: Final SELECT, Ranking, and Join
            SELECT
                d.doi,
                0 AS similarity_rank,
                0 AS chunk_similarity_rank,
                fl.full_match_score AS full_match_rank, -- 1: true, 0: false. rrf_score fn will handle this.
                DENSE_RANK() OVER (ORDER BY fl.partial_match_count DESC) AS partial_match_rank,
                0 AS keyword_rank
            FROM FilterLogic fl
            JOIN document d ON d.id = fl.document_id
            WHERE partial_match_count > 0 -- Ensures only documents that truly matched (score > 0) are returned
            -- NO ORDER BY here, as we will use the rank to calculate the score
            -- NO LIMIT here, we want to get all documents that match the filter
            """
        except Exception as e:
            self._logger.info(f"Unexpected error building filter subquery: {e}")
            raise

    def _get_empty_subquery(self) -> str:
        """Returns an SQL subquery that yields no results, matching the required columns."""
        return """SELECT
                    NULL::text AS doi,
                    0 AS similarity_rank,
                    0 AS chunk_similarity_rank,
                    0 AS full_match_rank,
                    0 AS partial_match_rank,
                    0 AS keyword_rank
                WHERE FALSE -- Ensure this returns no rows
                LIMIT 0"""

    # --- Filter Flags Generation ---

    def _build_flags_recursive(
        self, condition: dict, flag_counter: List[int], all_flags: List[str]
    ) -> None:
        """Recursively builds individual flag CASE statements."""
        if "logic" in condition and "conditions" in condition:
            nested_conditions = condition.get("conditions", [])
            for sub_condition in nested_conditions:
                if isinstance(sub_condition, dict):
                    self._build_flags_recursive(sub_condition, flag_counter, all_flags)
                else:
                    self._logger.info(
                        f"Skipping non-dict item in nested conditions: {sub_condition}"
                    )

        elif "name" in condition and "operator" in condition and "value" in condition:
            flag_counter[0] += 1  # Increment upfront, decrement if flag is skipped
            current_flag_index = flag_counter[0]
            flag_name = f"has_condition_{current_flag_index}"

            name_list = condition["name"]
            operator = str(condition["operator"]).upper()
            value = condition["value"]

            if not isinstance(name_list, list) or not name_list:
                self._logger.info(
                    f"Skipping flag {flag_name} due to invalid 'name': {name_list} in condition: {condition}"
                )
                flag_counter[0] -= 1
                return

            safe_names = ["'{}'".format(str(n).replace("'", "''")) for n in name_list]
            key_in_clause = f"f.key IN ({', '.join(safe_names)})"

            flag_sql_to_add = None
            comparison_clause = ""

            try:
                match operator:
                    case "BETWEEN" | "NOT BETWEEN":
                        if isinstance(value, list) and len(value) == 2:
                            v1, v2 = value[0], value[1]
                            is_v1_num = isinstance(v1, NumberTypes)
                            is_v2_num = isinstance(v2, NumberTypes)
                            if is_v1_num and is_v2_num:
                                if isinstance(v1, complex) or isinstance(v2, complex):
                                    raise ValueError(
                                        "Complex numbers are not supported for BETWEEN."
                                    )
                                if isinstance(v1, float) or isinstance(v2, float):
                                    comparison_clause = f"cast_to_float(f.value) {operator} {float(v1)} AND {float(v2)}"
                                else:
                                    comparison_clause = f"cast_to_int(f.value) {operator} {int(v1)} AND {int(v2)}"
                            else:  # String comparison
                                safe_v1 = str(v1).replace("'", "''")
                                safe_v2 = str(v2).replace("'", "''")
                                comparison_clause = (
                                    f"f.value {operator} '{safe_v1}' AND '{safe_v2}'"
                                )
                        else:
                            self._logger.info(
                                f"Invalid value for {operator} on {flag_name}: {value}. Condition will be FALSE."
                            )
                            comparison_clause = "FALSE"

                    case "IN" | "NOT IN":
                        if isinstance(value, list) and value:
                            if any(isinstance(v, float) for v in value):
                                safe_values = [str(float(v)) for v in value]
                                comparison_clause = f"cast_to_float(f.value) {operator} ({', '.join(safe_values)})"
                            elif all(isinstance(v, int) for v in value):
                                safe_values = [str(int(v)) for v in value]
                                comparison_clause = f"cast_to_int(f.value) {operator} ({', '.join(safe_values)})"
                            else:  # Treat all as strings
                                safe_values = [
                                    "'{}'".format(str(v).replace("'", "''"))
                                    for v in value
                                ]
                                comparison_clause = (
                                    f"f.value {operator} ({', '.join(safe_values)})"
                                )
                        else:
                            self._logger.info(
                                f"Invalid value for {operator} on {flag_name}: {value}. Condition will be FALSE."
                            )
                            comparison_clause = "FALSE"

                    case "IS NOT NULL":
                        comparison_clause = "f.value IS NOT NULL"
                    case "IS NULL":
                        comparison_clause = "f.value IS NULL"

                    case "ILIKE" | "LIKE":  # Prioritized scoring
                        sanitized_core_value = (
                            str(value)
                            .replace("'", "''")
                            .replace("%", "")
                            .replace("_", "\\_")
                        )

                        prefix_match_sql = f"({key_in_clause} AND f.value {operator} '{sanitized_core_value}%' ESCAPE '\\')"
                        contains_match_sql = f"({key_in_clause} AND f.value {operator} '%{sanitized_core_value}%' ESCAPE '\\')"
                        flag_sql_to_add = f"""MAX(CASE
                            WHEN {prefix_match_sql} THEN 2
                            WHEN {contains_match_sql} THEN 1
                            ELSE 0
                        END) AS {flag_name}"""

                    case "NOT ILIKE" | "NOT LIKE":
                        # Input 'value' sanitized to core term. Check if core term is NOT contained.
                        sanitized_core_value = (
                            str(value)
                            .replace("'", "''")
                            .replace("%", "")
                            .replace("_", "\\_")
                        )
                        comparison_clause = (
                            f"f.value {operator} '%{sanitized_core_value}%' ESCAPE '\\'"
                        )

                    case "=" | "!=" | ">" | "<" | ">=" | "<=":
                        if isinstance(value, list):
                            self._logger.info(
                                f"List value for {operator} on {flag_name}: {value}. Condition will be FALSE."
                            )
                            comparison_clause = "FALSE"
                        else:
                            if isinstance(value, bool):
                                comparison_clause = (
                                    f"cast_to_bool(f.value) {operator} {bool(value)}"
                                )
                            elif isinstance(value, int):
                                comparison_clause = (
                                    f"cast_to_int(f.value) {operator} {int(value)}"
                                )
                            elif isinstance(value, float):
                                comparison_clause = (
                                    f"cast_to_float(f.value) {operator} {float(value)}"
                                )
                            else:  # String comparison
                                if operator == "=":
                                    sanitized_value = (
                                        str(value)
                                        .replace("'", "''")
                                        .replace("%", "")
                                        .replace("_", "\\_")
                                    )
                                    prefix_match_sql = f"({key_in_clause} AND f.value ILIKE '{sanitized_value}%' ESCAPE '\\')"
                                    contains_match_sql = f"({key_in_clause} AND f.value ILIKE '%{sanitized_value}%' ESCAPE '\\')"
                                    flag_sql_to_add = f"""MAX(CASE
                                        WHEN {prefix_match_sql} THEN 2
                                        WHEN {contains_match_sql} THEN 1
                                        ELSE 0
                                    END) AS {flag_name}"""
                                else:  # Exact string operators !=, >, <, >=, <=
                                    sanitized_value = str(value).replace("'", "''")
                                    comparison_clause = (
                                        f"f.value {operator} '{sanitized_value}'"
                                    )
                    case _:
                        self._logger.info(
                            f"Unsupported operator '{operator}' for {flag_name}. Condition will be FALSE."
                        )
                        comparison_clause = "FALSE"

                if flag_sql_to_add:
                    # Specific ILIKE sql for prefix/contains match
                    all_flags.append(flag_sql_to_add)
                elif (
                    comparison_clause and comparison_clause != "FALSE"
                ):  # Generic flag for score 1
                    sql_condition = f"({key_in_clause} AND {comparison_clause})"
                    generic_flag_sql = f"MAX(CASE WHEN {sql_condition} THEN 1 ELSE 0 END) AS {flag_name}"
                    all_flags.append(generic_flag_sql)
                else:  # No specific SQL and comparison_clause is FALSE or empty
                    self._logger.info(
                        f"Skipping flag {flag_name} due to FALSE or empty comparison clause."
                    )
                    flag_counter[0] -= 1  # Decrement as no flag was actually added

            except Exception as e:  # Catch errors from type casting or value processing
                self._logger.info(
                    f"Error processing value for condition {flag_name} ({condition}): {e}. Skipping flag."
                )
                # Decrement counter as no flag was actually added due to error
                flag_counter[0] -= 1
        else:
            self._logger.info(
                f"Skipping flag generation for invalid/incomplete condition structure: {condition}"
            )

    def _generate_filter_flags(self, filt: dict) -> Tuple[List[str], int]:
        flag_counter = [0]
        all_flags = []
        try:
            self._build_flags_recursive(filt, flag_counter, all_flags)
        except Exception as e:
            self._logger.info(f"Unexpected error during recursive flag building: {e}")
            return [], 0
        return all_flags, flag_counter[0]

    # --- Filter Logic Combination ---
    def _build_filter_logic(self, filters_obj: Dict) -> str:
        """
        Wrapper to initialize the flag counter for _build_logic_recursive.
        The flag counter here is independent and used to consume flags sequentially.
        """
        logic_flag_counter = [0]  # Counter for referencing has_condition_X flags
        return self._build_logic_recursive(filters_obj, logic_flag_counter)

    def _collect_keys_recursive(self, condition: dict, all_keys: Set[str]) -> None:
        if "logic" in condition and "conditions" in condition:
            for sub_condition in condition.get("conditions", []):
                if isinstance(sub_condition, dict):
                    self._collect_keys_recursive(sub_condition, all_keys)
        elif "name" in condition:
            current_names = condition.get("name")
            if isinstance(current_names, list):
                all_keys.update(
                    key for key in current_names if isinstance(key, str) and key
                )

    def _build_logic_recursive(
        self, condition: dict, flag_idx_counter: List[int]
    ) -> str:
        """
        Recursively builds the SQL logic expression (e.g., (has_condition_1 > 0 AND has_condition_2 > 0)).
        Uses a separate flag_idx_counter to refer to flags sequentially.
        """
        if "logic" in condition and "conditions" in condition:
            nested_conditions = condition.get("conditions", [])
            if not nested_conditions:
                self._logger.info(
                    f"Empty nested conditions for logic '{condition['logic']}'. Returning FALSE."
                )
                return "FALSE"

            logic_parts = []
            for sub_condition in nested_conditions:
                if isinstance(sub_condition, dict):
                    part = self._build_logic_recursive(sub_condition, flag_idx_counter)
                    if part and part != "FALSE":
                        logic_parts.append(part)
                else:
                    self._logger.info(
                        f"Skipping non-dict item in logic conditions: {sub_condition}"
                    )

            if not logic_parts:  # All sub-conditions were invalid or resulted in FALSE
                self._logger.info(
                    f"No valid logic parts for logic '{condition['logic']}'. Returning FALSE."
                )
                return "FALSE"

            if (
                len(logic_parts) == 1
            ):  # Single valid condition, no need for parentheses or AND/OR
                return logic_parts[0]

            sql_logic_operator = f" {condition['logic'].upper()} "
            return f"({sql_logic_operator.join(logic_parts)})"

        elif (
            "name" in condition and "operator" in condition and "value" in condition
        ):  # ഇത് ഒരു അടിസ്ഥാന വ്യവസ്ഥയാണ്
            # This is a base condition, corresponding to a flag generated by _build_flags_recursive.
            # We need to ensure this base condition is valid before consuming a flag index.
            name_list = condition.get("name")
            if not isinstance(name_list, list) or not name_list:
                self._logger.info(
                    f"Skipping logic part for condition with invalid 'name': {condition}. Returning FALSE."
                )
                return "FALSE"  # This effectively makes this branch of logic false

            flag_idx_counter[0] += 1  # Consume the next flag index
            # Check for > 0 as flags can now have scores 0, 1, or 2
            return f"has_condition_{flag_idx_counter[0]} > 0"
        else:
            # This path might be hit if the filter structure is malformed at this level
            self._logger.info(
                f"Invalid condition structure for logic building (not a logic block or base condition): {condition}. Returning FALSE."
            )
            return "FALSE"  # Treat malformed parts as FALSE
