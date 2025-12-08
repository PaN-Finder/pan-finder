from typing import Any, Dict, List, LiteralString, Union, TypedDict, Tuple, Set, cast
from datetime import datetime
from psycopg.sql import SQL, Composed, Identifier, Literal, Composable
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sentence_transformers import SentenceTransformer
from logging import Logger, getLogger

NUMBER_TYPES = (int, float)


class SearchResult(TypedDict):
    """
    Type definition for each row returned when executing the SQL built by
    SearchQueryBuilder.build_query(). Matches the columns selected in the
    final SQL.
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
    Builds a complex SQL query for searching documents based on user input.

    This class combines multiple search strategies:
    - Vector similarity search for user's 'intention' against document titles/summaries and text chunks.
    - Full-text search for 'keywords'.
    - Structured metadata filtering based on 'filters' with complex AND/OR logic.
    - Finds similar filter names to correct for user typos or variations.

    The final query uses a Reciprocal Rank Fusion (RRF) approach to combine scores
    from each strategy into a single, relevant 'overall_score' for ranking.
    """

    # --- Constants ---
    # Similarity threshold for finding similar filter names
    _SIMILARITY_THRESHOLD_NAMES: float = 0.5
    # Minimum number of results to return when finding similar names
    _SIMILARITY_MINIMUM_RESULTS: int = 4
    # Similarity threshold for document title/summary vs intention
    _SIMILARITY_THRESHOLD_DOCS: float = 0.5
    # Similarity threshold for document chunks vs intention
    _SIMILARITY_THRESHOLD_CHUNKS: float = 0.5
    # Final result limit
    _RESULTS_SET_SIZE: int = 20
    # Default RRF K value (can be used as a common default)
    _DEFAULT_RRF_K: int = 6

    def __init__(
        self,
        sentence_transformer: SentenceTransformer,
        pool: ConnectionPool,
        rrf_k_similarity: int = _DEFAULT_RRF_K,
        rrf_k_chunk: int = _DEFAULT_RRF_K,
        rrf_k_full_match: int = _DEFAULT_RRF_K,
        rrf_k_partial_match: int = _DEFAULT_RRF_K,
        rrf_k_keyword: int = _DEFAULT_RRF_K,
        results_set_size: int = _RESULTS_SET_SIZE,
        logger: Logger | None = None,
        capture_similar_names: bool = False,
    ):
        self.sentence_transformer = sentence_transformer
        self.pool = pool
        self.rrf_k_similarity = rrf_k_similarity
        self.rrf_k_chunk = rrf_k_chunk
        self.rrf_k_full_match = rrf_k_full_match
        self.rrf_k_partial_match = rrf_k_partial_match
        self.rrf_k_keyword = rrf_k_keyword
        self.results_set_size = results_set_size
        self._logger = logger or getLogger(__name__)
        self._capture_similar_names = capture_similar_names
        self._similar_names = (
            {}
        )  # For debugging purposes, stores similar names found during query building

    @property
    def similar_names(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Returns the dictionary of similar names found during query building.
        Only populated if capture_similar_names was set to True in the constructor.
        """
        return self._similar_names

    # --- Public Methods ---
    def build_query(self, params: Dict[str, Any]) -> Composed:
        """
        Constructs the final SQL search query based on the input data.

        Args:
            data: A dictionary containing search parameters like 'intention',
                  'keywords', and 'filters'.

        Returns:
            A psycopg Composed object representing the full SQL query.
        """
        if not isinstance(params, dict):
            raise ValueError("Input 'params' must be a dictionary.")

        if self._capture_similar_names:
            self._similar_names.clear()  # Clear previous similar names if capturing

        self._logger.info(f"Building query with params: {params}")
        # 1. Preprocess: Update filter names with similar ones
        normalized_params = self._update_filter_names(params)
        self._logger.info(
            f"Processed filter names: {normalized_params.get('filters', 'N/A')}"
        )

        # 2. Prepare components
        intent_text = normalized_params.get("intention", "")
        intent_embedding = (
            self.sentence_transformer.encode(intent_text).tolist()
            if intent_text != ""
            else None
        )

        doc_similarity_subquery = self._build_similarity_query(intent_embedding)
        chunk_similarity_subquery = self._build_chunk_similarity_query(intent_embedding)
        keywords_tsquery_text = self._build_keywords_tsquery_text(
            normalized_params.get("keywords", [])
        )
        filter_subquery = self._build_filter_subquery(normalized_params.get("filters"))

        # 3. Assemble the final query with composables and sanitized values
        search_sql = SQL(
            """
        SELECT
            searches.doi,
            sum(
                rrf_score(similarity_rank, {rrf_k_similarity}) +
                rrf_score(chunk_similarity_rank, {rrf_k_chunk}) +
                rrf_score(full_match_rank, {rrf_k_full_match}) +
                rrf_score(partial_match_rank, {rrf_k_partial_match}) +
                rrf_score(keyword_rank, {rrf_k_keyword})
            ) AS overall_score,
            sum(rrf_score(similarity_rank, {rrf_k_similarity})) AS similarity_score,
            sum(rrf_score(chunk_similarity_rank, {rrf_k_chunk})) AS chunk_similarity_score,
            sum(rrf_score(full_match_rank, {rrf_k_full_match})) AS full_match_score,
            sum(rrf_score(partial_match_rank, {rrf_k_partial_match})) AS partial_match_score,
            sum(rrf_score(keyword_rank, {rrf_k_keyword})) AS keyword_score
        FROM (
            -- Subquery 1: Document Similarity (title + summary (generated))
            (
                {doc_similarity_subquery}
            )
            UNION ALL
            -- Subquery 2: Chunk Similarity (title + text chunks)
            (
                {chunk_similarity_subquery}
            )
            UNION ALL
            -- Subquery 3: Hard Filter Matches
            (
                {filter_subquery}
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
                    DENSE_RANK() OVER (ORDER BY ts_rank_cd(title_text_search_vector, to_tsquery('english', {keywords_tsquery_text})) DESC) AS keyword_rank
                FROM document d
                WHERE
                    {keywords_tsquery_text} != '' -- Avoid error if keywords are empty
                    AND title_text_search_vector @@ to_tsquery('english', {keywords_tsquery_text})                    
                -- NO ORDER BY here, as we will use the rank to calculate the score
                -- NO LIMIT here: we want all DOIs with at least one keyword match
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
        LIMIT {results_set_size};
        """
        ).format(
            rrf_k_similarity=self.rrf_k_similarity,
            rrf_k_chunk=self.rrf_k_chunk,
            rrf_k_full_match=self.rrf_k_full_match,
            rrf_k_partial_match=self.rrf_k_partial_match,
            rrf_k_keyword=self.rrf_k_keyword,
            doc_similarity_subquery=doc_similarity_subquery,
            chunk_similarity_subquery=chunk_similarity_subquery,
            filter_subquery=filter_subquery,
            keywords_tsquery_text=keywords_tsquery_text,
            results_set_size=self.results_set_size,
        )

        return search_sql

    def _build_similarity_query(self, intention_vector: List | None) -> Composed | SQL:
        """
        Builds the subquery for document similarity search.

        This subquery finds documents where the combined title and summary vector
        is similar to the user's intention vector.

        Args:
            intention_vector: The embedding vector of the user's search intention.

        Returns:
            A Composed or SQL object for the subquery, or an empty subquery if
            no intention vector is provided.
        """
        if intention_vector is None:
            return self._get_empty_subquery()

        return SQL(
            """SELECT
                    d.doi,
                    DENSE_RANK () OVER (ORDER BY d.title_summary_vector <=> {intention_vector}::vector ASC) AS similarity_rank,
                    0 AS chunk_similarity_rank,
                    0 AS full_match_rank,
                    0 AS partial_match_rank,
                    0 AS keyword_rank
                FROM document d
                WHERE
                    d.title_summary_vector <=> {intention_vector}::vector < {_SIMILARITY_THRESHOLD_DOCS}"""
        ).format(
            intention_vector=intention_vector,
            _SIMILARITY_THRESHOLD_DOCS=self._SIMILARITY_THRESHOLD_DOCS,
        )

    def _build_chunk_similarity_query(
        self, intention_vector: List | None
    ) -> Composed | SQL:
        """
        Builds the subquery for chunk-based similarity search.

        This subquery identifies the most relevant text chunk for each document
        based on similarity to the user's intention vector. It ranks documents
        based on the similarity of their best chunk.

        Args:
            intention_vector: The embedding vector of the user's search intention.

        Returns:
            A Composed or SQL object for the subquery, or an empty subquery if
            no intention vector is provided.
        """
        if intention_vector is None:
            return self._get_empty_subquery()

        return SQL(
            """WITH RankedChunks AS (
                    SELECT
                        d.doi,
                        c.text_vector <=> {intention_vector}::vector AS distance, -- Distance used for ordering (lower is better)
                        -- Rank each chunk within its DOI by similarity
                        ROW_NUMBER() OVER(PARTITION BY d.doi ORDER BY c.text_vector <=> {intention_vector}::vector ASC) as rn_within_doi,
                        -- Count how many chunks for this DOI meet the similarity threshold
                        COUNT(*) OVER (PARTITION BY d.doi) as chunk_count_for_doi
                    FROM
                        chunk c
                    JOIN
                        document d ON c.document_id = d.id
                    WHERE
                        c.text_vector <=> {intention_vector}::vector < {_SIMILARITY_THRESHOLD_CHUNKS}
                )
                SELECT
                    rc.doi,
                    0 AS similarity_rank,
                    DENSE_RANK() OVER (ORDER BY rc.distance ASC, rc.chunk_count_for_doi DESC) AS chunk_similarity_rank,
                    -- Primary: prioritize DOIs with a more similar best chunk (lower distance)
                    -- Secondary: break ties by number of qualifying chunks (more is better)
                    0 AS full_match_rank,
                    0 AS partial_match_rank,
                    0 AS keyword_rank
                FROM RankedChunks rc
                WHERE
                    rc.rn_within_doi = 1        -- Keep only the single best chunk per DOI
                -- NO ORDER BY here, as we will use the rank to calculate the score
                -- NO LIMIT as we want all DOIs with at least one chunk meeting the threshold"""
        ).format(
            intention_vector=intention_vector,
            _SIMILARITY_THRESHOLD_CHUNKS=self._SIMILARITY_THRESHOLD_CHUNKS,
        )

    # --- Private Helper Methods ---
    def _parse_datetime_strict(self, value: Any) -> datetime | None:
        """Attempts to parse a datetime strictly.
        Date: YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
        DateTime: YYYY-MM-DD hh:mm:ss, YYYY/MM/DD hh:mm:ss, YYYY.MM.DD hh:mm:ss
        """
        # Accept only exact formats listed above. Any deviation returns None.
        if not isinstance(value, str):
            return None

        s = value.strip()
        if not s:
            return None

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y.%m.%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y.%m.%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue

        return None

    def _build_keywords_tsquery_text(self, keywords: List[str]) -> str:
        """
        Formats keywords for PostgreSQL full-text search ts_query (OR logic).

        Args:
            keywords: A list of keyword strings.

        Returns:
            A single string formatted for to_tsquery, with keywords joined by '|'.
        """
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
        """
        Finds similar filter names in the database using vector embeddings.

        This searches both filter_key.name_vector and filter_description.description_vector
        to help correct for typos or variations in user-provided filter names.

        Args:
            raw_name: The user-provided filter name.

        Returns:
            A list of similar names found in the database, ordered by similarity.
        """
        if not raw_name:
            return []

        query_vector = self.sentence_transformer.encode(raw_name).tolist()
        with (
            self.pool.connection() as conn,
            conn.cursor(row_factory=dict_row) as cursor,
        ):
            cursor.execute(
                """WITH top_matches AS (
                    SELECT DISTINCT name, name_vector <=> %s::vector AS distance
                    FROM filter_key
                    WHERE name_vector <=> %s::vector < %s
                ),
                description_matches AS (
                    SELECT DISTINCT filter_key_name as name, description_vector <=> %s::vector AS distance
                    FROM filter_description
                    WHERE description_vector <=> %s::vector < %s
                ),
                combined_matches AS (
                    SELECT name, distance FROM top_matches
                    UNION
                    SELECT name, distance FROM description_matches
                ),
                fallback_matches AS (
                    SELECT DISTINCT fk.name, fk.name_vector <=> %s::vector AS distance
                    FROM filter_key fk
                    WHERE fk.name_vector <=> %s::vector >= %s
                    AND NOT EXISTS (SELECT 1 FROM combined_matches cm WHERE cm.name = fk.name)
                )
                (
                    (
                        SELECT * FROM combined_matches
                        ORDER BY distance
                    )
                    UNION ALL
                    (
                        SELECT * FROM fallback_matches
                        ORDER BY distance
                        LIMIT GREATEST(0, %s - (SELECT COUNT(*) FROM combined_matches))
                    )
                )
                ORDER BY distance;
                """,
                (
                    query_vector,  # top_matches comparison
                    query_vector,  # top_matches WHERE
                    self._SIMILARITY_THRESHOLD_NAMES,  # top_matches threshold
                    query_vector,  # description_matches comparison
                    query_vector,  # description_matches WHERE
                    self._SIMILARITY_THRESHOLD_NAMES,  # description_matches threshold
                    query_vector,  # fallback_matches comparison
                    query_vector,  # fallback_matches WHERE
                    self._SIMILARITY_THRESHOLD_NAMES,  # fallback_matches threshold
                    self._SIMILARITY_MINIMUM_RESULTS,  # Ensure we always return at least this many results
                ),
            )
            result = cursor.fetchall()
            self._logger.info(
                f"Finding similar names for '{raw_name}'. Found: {[row['name'] for row in result[:5]]}"
            )
            if self._capture_similar_names:
                self._similar_names[raw_name] = result

            if len(result) == 0:
                return [raw_name]

            return [row["name"] for row in result]

    def _update_filter_names_recursive(self, filter_node: Dict) -> Union[Dict, None]:
        """
        Recursively finds and replaces 'name' in filter conditions with similar names.

        Args:
            filter_node: The current node in the filter structure.

        Returns:
            The updated filter node, or None if the node becomes invalid.
        """
        if "conditions" in filter_node and "logic" in filter_node:
            updated_conditions = []
            for i, cond in enumerate(filter_node.get("conditions", [])):
                if isinstance(cond, dict):
                    updated_cond = self._update_filter_names_recursive(cond)
                    if updated_cond:  # Keep condition only if it's valid after update
                        updated_conditions.append(updated_cond)
                else:
                    self._logger.info(
                        f"Skipping invalid condition at index {i}: {cond}"
                    )
            # Return None if a logic block has no valid conditions left
            filter_node["conditions"] = updated_conditions
            return filter_node if updated_conditions else None

        elif (
            "name" in filter_node
            and "operator" in filter_node
            and "value" in filter_node
        ):
            raw_name = filter_node.get("name")
            if isinstance(raw_name, str) and raw_name:
                matched_names = self._find_similar_names(raw_name)
                filter_node["name"] = (
                    matched_names if matched_names else [raw_name]
                )  # Ensure name is always a list
                return filter_node
            else:
                self._logger.info(
                    f"Skipping condition with invalid or missing name: {filter_node}"
                )
                return None  # Invalid condition structure
        else:
            self._logger.info(
                f"Skipping condition with unexpected structure: {filter_node}"
            )
            return None  # Invalid condition structure

    def _update_filter_names(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates the 'filters' part of the data by replacing names with similar ones.

        Args:
            data: The input search parameters dictionary.

        Returns:
            The data dictionary with filter names updated.
        """
        filters = data.get("filters")
        if not isinstance(filters, dict) or not filters.get("conditions"):
            self._logger.info(
                "No valid filters found or filters are not a dict, skipping name update."
            )
            return data  # Return original data if no filters or invalid format

        updated_filters = self._update_filter_names_recursive(
            filters.copy()
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
    def _build_filter_subquery(self, filters: Union[Dict, None]) -> Composed | SQL:
        """
        Builds the SQL subquery for filtering documents based on the filter object.

        This method orchestrates the generation of filter flags, the collection of
        filter keys, and the construction of the final logic expression.

        Args:
            filters: The dictionary representing the filter structure.

        Returns:
            A Composed or SQL object for the filter subquery.
        """
        if not filters or not filters.get("conditions"):
            self._logger.info(
                "No valid filters provided, creating empty filter subquery."
            )
            return self._get_empty_subquery()

        try:
            # 1. Generate flag definitions using MAX(CASE WHEN ...) AS has_condition_N
            # Also capture which base condition dicts produced a valid flag so logic indexing stays aligned.
            flag_definitions, flag_count, valid_condition_ids = (
                self._generate_filter_flags(filters)
            )
            if not flag_definitions:
                self._logger.info(
                    "Could not generate any filter flags from the provided structure."
                )
                return self._get_empty_subquery()

            # Join flags with newline and indentation so the generated SQL places
            # each flag definition on its own aligned line for readability.
            flag_select_list = SQL(",\n                    ").join(flag_definitions)

            # 2. Collect unique keys
            filter_key_names: Set[str] = set()
            self._collect_keys_recursive(filters, filter_key_names)
            if not filter_key_names:
                self._logger.info("No filter keys found in the provided structure.")
                return self._get_empty_subquery()

            # Sort keys for deterministic SQL generation
            sorted_filter_keys = sorted(list(filter_key_names))
            filter_keys_list = SQL(", ").join(Literal(k) for k in sorted_filter_keys)

            # 3. Build the logic expression (e.g., (has_condition_1 > 0 AND has_condition_2 > 0) OR has_condition_3 > 0)
            # Only consume flag indices for conditions that actually generated flags (valid_condition_ids)
            filter_logic_expr = self._build_filter_logic(filters, valid_condition_ids)
            # Note: filter_logic_expr is a Composable; even if it represents a FALSE literal, downstream CASE WHEN will handle it.

            # 4. Construct the filter subquery using CTEs
            # Generate parts for partial match counting and WHERE clause optimization
            partial_match_sum_expr = SQL(" + ").join(
                [Identifier(f"has_condition_{i+1}") for i in range(flag_count)]
            )

            # Only include documents that have at least one condition met
            any_flag_match_expr = SQL(" OR ").join(
                [
                    SQL("{col} > 0").format(col=Identifier(f"has_condition_{i+1}"))
                    for i in range(flag_count)
                ]
            )

            return SQL(
                """
            WITH FilterFlags AS (
                -- Step 1: Calculate flags for each unique base condition per document using MAX(CASE WHEN ...)
                SELECT
                    f.document_id,
                    {flag_select_list}
                FROM filter f
                -- Pre-filter rows based on all keys involved in the conditions
                WHERE f.key IN ({filter_keys_list})
                GROUP BY f.document_id
            ),
            FilterLogic AS (
                -- Step 2: Apply the specific AND/OR logic and count partial matches
                SELECT
                    ff.document_id,
                    CASE
                        WHEN {filter_logic_expr}
                        THEN 1 -- The document satisfies the overall logic (Full Match)
                        ELSE 0 -- The document does not satisfy the overall logic (Partial or No Match)
                    END AS full_match_score,
                    -- Sum of individual flags (scores can be 0, 1, or 2)
                    ({partial_match_sum_expr}) AS partial_match_count
                FROM FilterFlags ff
                -- Optimization: Only process documents that matched at least one flag based on score
                WHERE ({any_flag_match_expr})
            )
            -- Step 3: Final SELECT, Ranking, and Join
            SELECT
                d.doi,
                0 AS similarity_rank,
                0 AS chunk_similarity_rank,
                fl.full_match_score AS full_match_rank, -- Treated as 1 (match) or 0 (no match); downstream scoring handles this.
                DENSE_RANK() OVER (ORDER BY fl.partial_match_count DESC) AS partial_match_rank,
                0 AS keyword_rank
            FROM FilterLogic fl
            JOIN document d ON d.id = fl.document_id
            WHERE partial_match_count > 0 -- Ensures only documents that truly matched (score > 0) are returned
            -- NO ORDER BY here, as we will use the rank to calculate the score
            -- NO LIMIT here, we want to get all documents that match the filter
            """
            ).format(
                flag_select_list=flag_select_list,
                filter_keys_list=filter_keys_list,
                filter_logic_expr=filter_logic_expr,
                partial_match_sum_expr=partial_match_sum_expr,
                any_flag_match_expr=any_flag_match_expr,
            )
        except Exception as e:
            self._logger.info(f"Unexpected error building filter subquery: {e}")
            raise

    def _get_empty_subquery(self) -> SQL:
        """
        Returns an SQL subquery that yields no results, matching the required columns.

        This is used as a placeholder when a particular search component (e.g., similarity)
        is not applicable.
        """
        return SQL(
            """SELECT
                    NULL::text AS doi,
                    0 AS similarity_rank,
                    0 AS chunk_similarity_rank,
                    0 AS full_match_rank,
                    0 AS partial_match_rank,
                    0 AS keyword_rank
                WHERE FALSE -- Ensure this returns no rows
                LIMIT 0"""
        )

    # --- Filter Flags Generation ---
    def _build_flags_recursive(
        self,
        condition: dict,
        flag_counter: List[int],
        all_flags: List[Composable],
        valid_condition_ids: Set[int],
    ) -> None:
        """
        Recursively traverses the filter structure to generate SQL 'flag' expressions.

        Each base condition is converted into a `MAX(CASE WHEN ...)` expression that
        acts as a flag, indicating if a document meets that condition.

        Args:
            condition: The current node in the filter structure.
            flag_counter: A list containing a single integer to track the flag number.
            all_flags: A list to accumulate the generated SQL flag expressions.
            valid_condition_ids: A set to store the IDs of valid base conditions.
        """
        if "logic" in condition and "conditions" in condition:
            for sub in condition.get("conditions", []):
                if isinstance(sub, dict):
                    self._build_flags_recursive(
                        sub, flag_counter, all_flags, valid_condition_ids
                    )
            return

        if not (
            "name" in condition and "operator" in condition and "value" in condition
        ):
            return

        # Prepare base fields
        name_list = condition.get("name")
        operator_raw = str(condition.get("operator", "")).upper()
        value = condition.get("value")
        unit_text = condition.get(
            "unit"
        )  # Optional unit string to enable unit-aware comparisons
        if not isinstance(name_list, list) or not name_list:
            return

        flag_counter[0] += 1
        flag_name = f"has_condition_{flag_counter[0]}"

        key_values_sql = SQL(", ").join([Literal(v) for v in name_list])
        key_in_clause: Composed = Composed(
            [SQL("f.key IN ("), key_values_sql, SQL(")")]
        )
        flag_sql_to_add: Composable | None = None
        comparison_clause: Composable | None = None
        op_sql = SQL(cast(LiteralString, operator_raw))

        try:
            if operator_raw in ("BETWEEN", "NOT BETWEEN"):
                if isinstance(value, list) and len(value) == 2:
                    v1, v2 = value[0], value[1]
                    is_v1_num = isinstance(v1, NUMBER_TYPES)
                    is_v2_num = isinstance(v2, NUMBER_TYPES)

                    if is_v1_num and is_v2_num:
                        # If a unit is specified, compare using value_si; fallback to value_numeric when value_si is NULL
                        if isinstance(unit_text, str) and unit_text.strip():
                            comparison_clause = Composed(
                                [
                                    SQL("("),
                                    SQL("("),
                                    SQL("f.value_si "),
                                    op_sql,
                                    SQL(" "),
                                    SQL("to_unit({v}, {u})").format(
                                        v=Literal(v1), u=Literal(unit_text.strip())
                                    ),
                                    SQL(" AND "),
                                    SQL("to_unit({v}, {u})").format(
                                        v=Literal(v2), u=Literal(unit_text.strip())
                                    ),
                                    SQL(")"),
                                    SQL(" OR (f.value_si IS NULL AND f.value_numeric "),
                                    op_sql,
                                    SQL(" "),
                                    Literal(v1),
                                    SQL(" AND "),
                                    Literal(v2),
                                    SQL(")"),
                                    SQL(")"),
                                ]
                            )
                        else:
                            # Use unified numeric column for range comparisons
                            comparison_clause = Composed(
                                [
                                    SQL("f.value_numeric "),
                                    op_sql,
                                    SQL(" "),
                                    Literal(v1),
                                    SQL(" AND "),
                                    Literal(v2),
                                ]
                            )
                    # If both values are strict timestamps
                    elif (v1t := self._parse_datetime_strict(v1)) and (
                        v2t := self._parse_datetime_strict(v2)
                    ):
                        # Less strict alternative: also compare by DATE component
                        comparison_clause = Composed(
                            [
                                SQL("("),
                                SQL("f.value_timestamp "),
                                op_sql,
                                SQL(" "),
                                Literal(v1t),
                                SQL(" AND "),
                                Literal(v2t),
                                SQL(" OR f.value_timestamp::date "),
                                op_sql,
                                SQL(" "),
                                Composed([Literal(v1t), SQL("::date")]),
                                SQL(" AND "),
                                Composed([Literal(v2t), SQL("::date")]),
                                SQL(")"),
                            ]
                        )
                    else:
                        # String comparisons
                        comparison_clause = Composed(
                            [
                                SQL("f.value "),
                                op_sql,
                                SQL(" "),
                                Literal(v1),
                                SQL(" AND "),
                                Literal(v2),
                            ]
                        )
                else:
                    flag_counter[0] -= 1
                    return

            elif operator_raw in ("IN", "NOT IN"):
                if isinstance(value, list) and value:
                    if all(isinstance(v, NUMBER_TYPES) for v in value):
                        # If a unit is specified, compare using value_si; fallback to value_numeric when value_si is NULL
                        if isinstance(unit_text, str) and unit_text.strip():
                            values_sql_units = SQL(", ").join(
                                [
                                    SQL("to_unit({v}, {u})").format(
                                        v=Literal(v), u=Literal(unit_text.strip())
                                    )
                                    for v in value
                                ]
                            )
                            values_sql_raw = SQL(", ").join([Literal(v) for v in value])
                            comparison_clause = Composed(
                                [
                                    SQL("("),
                                    SQL("f.value_si "),
                                    op_sql,
                                    SQL(" ("),
                                    values_sql_units,
                                    SQL(")"),
                                    SQL(" OR (f.value_si IS NULL AND f.value_numeric "),
                                    op_sql,
                                    SQL(" ("),
                                    values_sql_raw,
                                    SQL("))"),
                                    SQL(")"),
                                ]
                            )
                        else:
                            # Unified numeric IN/NOT IN using numeric column
                            values_sql = SQL(", ").join([Literal(v) for v in value])
                            comparison_clause = Composed(
                                [
                                    SQL("f.value_numeric "),
                                    op_sql,
                                    SQL(" ("),
                                    values_sql,
                                    SQL(")"),
                                ]
                            )
                    elif all(isinstance(v, str) for v in value):
                        values_sql = SQL(", ").join([Literal(v) for v in value])
                        comparison_clause = Composed(
                            [SQL("f.value "), op_sql, SQL(" ("), values_sql, SQL(")")]
                        )
                    else:
                        flag_counter[0] -= 1
                        return
                else:
                    flag_counter[0] -= 1
                    return
            elif operator_raw == "IS NOT NULL":
                comparison_clause = SQL("f.value IS NOT NULL")
            elif operator_raw == "IS NULL":
                comparison_clause = SQL("f.value IS NULL")
            # LIKE family with prioritized scoring
            elif (
                operator_raw in ("ILIKE", "LIKE")
                or (operator_raw == "=" and isinstance(value, str))
            ) and self._parse_datetime_strict(
                value
            ) is None:  # Ensure we don't treat timestamps as strings
                # Aggregated priority: 2 if any value has prefix match, else 1 if any value contains, else 0
                flag_sql_to_add = SQL(
                    """MAX(CASE 
                        WHEN {key_in_clause} AND f.value ILIKE {prefix} THEN 2
                        WHEN {key_in_clause} AND f.value ILIKE {contains} THEN 1
                        ELSE 0
                    END) AS {flag_name}"""
                ).format(
                    key_in_clause=key_in_clause,
                    prefix=Literal(str(value) + "%"),
                    contains=Literal("%" + str(value) + "%"),
                    flag_name=Identifier(flag_name),
                )

            elif (
                operator_raw in ("NOT ILIKE", "NOT LIKE")
                or (operator_raw == "!=" and isinstance(value, str))
            ) and self._parse_datetime_strict(
                value
            ) is None:  # Ensure we don't treat timestamps as strings
                comparison_clause = SQL("f.value NOT ILIKE {v}").format(
                    op=op_sql,
                    v=Literal("%" + str(value) + "%"),
                )

            # Comparison operators
            elif operator_raw in ("=", "!=", ">", "<", ">=", "<="):
                if isinstance(value, list):
                    flag_counter[0] -= 1
                    return
                # Handle timestamps strictly
                ts_val = self._parse_datetime_strict(value)
                if ts_val is not None:
                    # Less strict alternative: also compare by DATE component
                    comparison_clause = Composed(
                        [
                            SQL("("),
                            SQL("f.value_timestamp "),
                            op_sql,
                            SQL(" "),
                            Literal(ts_val),
                            SQL(" OR f.value_timestamp::date "),
                            op_sql,
                            SQL(" "),
                            Composed([Literal(ts_val), SQL("::date")]),
                            SQL(")"),
                        ]
                    )
                elif isinstance(value, bool):
                    if operator_raw not in ("=", "!="):
                        flag_counter[0] -= 1
                        return

                    comparison_clause = SQL("f.value_boolean {op} {v}").format(
                        op=op_sql,
                        v=Literal(bool(value)),
                    )
                elif isinstance(value, NUMBER_TYPES):
                    # If a unit is specified, compare against value_si using to_unit; fallback to value_numeric when value_si is NULL
                    if isinstance(unit_text, str) and unit_text.strip():
                        # For equality/inequality, cast both sides to text to avoid rounding issues
                        if operator_raw in ("=", "!="):
                            comparison_clause = Composed(
                                [
                                    SQL("("),
                                    SQL("f.value_si::text "),
                                    op_sql,
                                    SQL(" "),
                                    SQL("to_unit({v}, {u})::text").format(
                                        v=Literal(value), u=Literal(unit_text.strip())
                                    ),
                                    SQL(" OR (f.value_si IS NULL AND f.value_numeric "),
                                    op_sql,
                                    SQL(" "),
                                    Literal(value),
                                    SQL(")"),
                                    SQL(")"),
                                ]
                            )
                        else:
                            comparison_clause = Composed(
                                [
                                    SQL("("),
                                    SQL("f.value_si "),
                                    op_sql,
                                    SQL(" "),
                                    SQL("to_unit({v}, {u})").format(
                                        v=Literal(value), u=Literal(unit_text.strip())
                                    ),
                                    SQL(" OR (f.value_si IS NULL AND f.value_numeric "),
                                    op_sql,
                                    SQL(" "),
                                    Literal(value),
                                    SQL(")"),
                                    SQL(")"),
                                ]
                            )
                    else:
                        comparison_clause = SQL("f.value_numeric {op} {v}").format(
                            op=op_sql,
                            v=Literal(value),
                        )
                else:
                    flag_counter[0] -= 1
                    return
            else:
                flag_counter[0] -= 1
                return

            if flag_sql_to_add is not None:
                all_flags.append(flag_sql_to_add)
                valid_condition_ids.add(id(condition))
            elif comparison_clause is not None:
                # Aggregated boolean: 1 if any row for this document matches the comparison, else 0
                all_flags.append(
                    SQL(
                        "MAX(CASE WHEN {key_in_clause} AND {cmp} THEN 1 ELSE 0 END) AS {name}"
                    ).format(
                        key_in_clause=key_in_clause,
                        cmp=comparison_clause,
                        name=Identifier(flag_name),
                    )
                )
                valid_condition_ids.add(id(condition))
            else:
                flag_counter[0] -= 1
        except Exception:
            flag_counter[0] -= 1

    def _generate_filter_flags(
        self, filt: dict
    ) -> Tuple[List[Composable], int, Set[int]]:
        """
        Generates all filter flag expressions for a given filter structure.

        Args:
            filt: The filter dictionary.

        Returns:
            A tuple containing the list of flag expressions, the total count of flags,
            and the set of IDs for valid conditions.
        """
        flag_counter = [0]
        all_flags: List[Composable] = []
        valid_condition_ids: Set[int] = set()
        try:
            self._build_flags_recursive(
                filt, flag_counter, all_flags, valid_condition_ids
            )
        except Exception as e:
            self._logger.info(f"Unexpected error during recursive flag building: {e}")
            return [], 0, set()
        return all_flags, flag_counter[0], valid_condition_ids

    # --- Filter Logic Combination ---
    def _build_filter_logic(
        self, filters: Dict, valid_condition_ids: Set[int]
    ) -> SQL | Composed:
        """
        Builds the final boolean logic expression from the filter structure.

        This orchestrates the recursive construction of the logic based on the
        generated flags.

        Args:
            filters: The filter dictionary.
            valid_condition_ids: A set of IDs for conditions that are valid.

        Returns:
            A Composed or SQL object representing the boolean logic.
        """
        logic_flag_counter = [0]
        return self._build_logic_recursive(
            filters, logic_flag_counter, valid_condition_ids
        )

    def _collect_keys_recursive(self, condition: dict, all_keys: Set[str]) -> None:
        """
        Recursively collects all unique filter key names from the filter structure.

        Args:
            condition: The current node in the filter structure.
            all_keys: A set to accumulate the unique key names.
        """
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
        self,
        condition: dict,
        flag_idx_counter: List[int],
        valid_condition_ids: Set[int],
    ) -> SQL | Composed:
        """
        Recursively builds the SQL logic expression (e.g., (has_condition_1 > 0 AND has_condition_2 > 0)).
        Uses a separate flag_idx_counter to refer to flags sequentially.
        Returns a psycopg Composable object (SQL/Composed).
        """
        if "logic" in condition and "conditions" in condition:
            nested_conditions = condition.get("conditions", [])
            if not nested_conditions:
                self._logger.info(
                    f"Empty nested conditions for logic '{condition['logic']}'. Returning FALSE."
                )
                return SQL("FALSE")

            logic_parts: List[Composable] = []
            for sub_condition in nested_conditions:
                if isinstance(sub_condition, dict):
                    part = self._build_logic_recursive(
                        sub_condition, flag_idx_counter, valid_condition_ids
                    )
                    if (
                        isinstance(part, (SQL, Composed))
                        and part.as_string() != "FALSE"
                    ):
                        logic_parts.append(part)
                else:
                    self._logger.info(
                        f"Skipping non-dict item in logic conditions: {sub_condition}"
                    )

            if not logic_parts:  # All sub-conditions were invalid
                self._logger.info(
                    f"No valid logic parts for logic '{condition['logic']}'. Returning FALSE."
                )
                return SQL("FALSE")

            if len(logic_parts) == 1:
                # Ensure concrete type is SQL | Composed for type checkers
                part = logic_parts[0]
                if isinstance(part, Composed):
                    return part
                else:
                    # Wrap SQL into Composed to satisfy return type union
                    return Composed([part])

            op = condition.get("logic", "AND").upper()
            # Interleave parts with the operator and wrap in parentheses
            interleaved: List[Composable] = []
            for idx, part in enumerate(logic_parts):
                if idx > 0:
                    interleaved.append(SQL(cast(LiteralString, f" {op} ")))
                interleaved.append(part)
            return Composed([SQL("("), *interleaved, SQL(")")])

        elif (
            "name" in condition and "operator" in condition and "value" in condition
        ):  # Base condition
            # This corresponds to a flag generated by _build_flags_recursive.
            # We need to ensure this base condition is valid before consuming a flag index.
            name_list = condition.get("name")
            if not isinstance(name_list, list) or not name_list:
                self._logger.info(
                    f"Skipping logic part for condition with invalid 'name': {condition}. Returning FALSE."
                )
                return SQL("FALSE")  # This effectively makes this branch of logic false

            if id(condition) not in valid_condition_ids:
                return SQL("FALSE")
            flag_idx_counter[0] += 1
            return SQL("{flag_idx} > 0").format(
                flag_idx=Identifier(f"has_condition_{flag_idx_counter[0]}")
            )
        else:
            # This path might be hit if the filter structure is malformed at this level
            self._logger.info(
                f"Invalid condition structure for logic building (not a logic block or base condition): {condition}. Returning FALSE."
            )
            return SQL("FALSE")  # Treat malformed parts as FALSE
