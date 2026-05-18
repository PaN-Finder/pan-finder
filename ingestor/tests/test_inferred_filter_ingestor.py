from inferred_filter_ingestor import InferredFilterIngestor


class _ConnectionStub:
    def __init__(self, cursor) -> None:
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self):
        return self._cursor

    def commit(self) -> None:
        raise AssertionError("commit should not be called in this test")


class _CursorStub:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, query: str, params: tuple[object, ...]) -> None:
        self.executed.append((query, params))

    def fetchall(self) -> list[tuple[int, str, str]]:
        return []


def _make_ingestor() -> InferredFilterIngestor:
    ingestor = InferredFilterIngestor.__new__(InferredFilterIngestor)
    ingestor.source_keys = InferredFilterIngestor.DEFAULT_SOURCE_KEYS
    ingestor.document_ids = []
    ingestor.dry_run = False
    ingestor._normalized_key_index = {}
    ingestor._normalized_description_index = {}
    ingestor._resolution_cache = {}
    return ingestor


def test_fetch_source_rows_scopes_to_selected_document_ids() -> None:
    ingestor = _make_ingestor()
    ingestor.document_ids = [10, 20]
    cursor = _CursorStub()

    ingestor._fetch_source_rows(cursor)

    query, params = cursor.executed[0]
    assert "document_id = ANY(%s)" in query
    assert params == (list(ingestor.source_keys), [10, 20])


def test_fetch_source_rows_runs_on_all_documents_when_selection_is_empty() -> None:
    ingestor = _make_ingestor()
    cursor = _CursorStub()

    ingestor._fetch_source_rows(cursor)

    query, params = cursor.executed[0]
    assert "document_id = ANY(%s)" not in query
    assert params == (list(ingestor.source_keys),)


def test_parse_llm_response_discards_invalid_entries() -> None:
    ingestor = _make_ingestor()

    parsed = ingestor._parse_llm_response(
        """
        {
          "filters": [
            {
              "name": "Disease",
              "description": "Disease or condition described by the document",
              "value": "pancreatic cancer",
                            "unit": "",
                            "evidence_indices": [0, "1", -1, "bad", 0]
            },
            {
              "name": "",
              "description": "missing name",
              "value": "ignored"
            },
            {
              "name": "Keywords",
              "description": "not scalar",
              "value": ["bad"]
            }
          ]
        }
        """
    )

    assert parsed == [
        {
            "name": "Disease",
            "description": "Disease or condition described by the document",
            "value": "pancreatic cancer",
            "unit": None,
            "evidence_indices": [0, 1],
        }
    ]


def test_resolve_key_reuses_existing_key_or_description() -> None:
    ingestor = _make_ingestor()
    ingestor._normalized_key_index = {"sample patient sex": ["SamplePatient_sex"]}
    ingestor._normalized_description_index = {
        "patient sex": ["SamplePatient_sex"],
    }
    ingestor._resolve_similarity_match = lambda cursor, proposed_name: None

    assert ingestor._resolve_key(None, "SamplePatientSex") == (
        "SamplePatient_sex",
        False,
    )
    assert ingestor._resolve_key(None, "patient sex") == (
        "SamplePatient_sex",
        False,
    )


def test_resolve_key_creates_normalized_new_key_when_unmatched() -> None:
    ingestor = _make_ingestor()
    ingestor._resolve_similarity_match = lambda cursor, proposed_name: None

    assert ingestor._resolve_key(None, " Body   Organ ") == ("body organ", True)
    assert ingestor._normalized_key_index["body organ"] == ["body organ"]


def test_cluster_source_rows_splits_large_repeated_keys_without_shared_context() -> (
    None
):
    ingestor = _make_ingestor()
    ingestor._MAX_SOURCE_ROWS_PER_CLUSTER = 4

    clusters = ingestor._cluster_source_rows(
        [
            {"key": "title", "value": "Example title"},
            {"key": "summary", "value": "Example summary"},
            {"key": "parameters.Sample_description", "value": "sample alpha"},
            {"key": "parameters.Sample_description", "value": "sample beta"},
            {"key": "parameters.Sample_description", "value": "sample gamma"},
            {"key": "parameters.Sample_description", "value": "sample delta"},
            {"key": "parameters.Sample_description", "value": "sample epsilon"},
        ]
    )

    assert clusters == [
        [
            {"key": "title", "value": "Example title"},
            {"key": "summary", "value": "Example summary"},
        ],
        [
            {"key": "parameters.Sample_description", "value": "sample alpha"},
            {"key": "parameters.Sample_description", "value": "sample beta"},
            {"key": "parameters.Sample_description", "value": "sample gamma"},
            {"key": "parameters.Sample_description", "value": "sample delta"},
        ],
        [
            {"key": "parameters.Sample_description", "value": "sample epsilon"},
        ],
    ]


def test_build_rows_for_source_cluster_only_persists_descriptions_for_new_keys() -> (
    None
):
    ingestor = _make_ingestor()
    ingestor._infer_filters = lambda source_rows: [
        {
            "name": "patient sex",
            "description": "Patient sex",
            "value": "female",
            "unit": None,
            "evidence_indices": [0],
        },
        {
            "name": "Body Organ",
            "description": "Body organ or tissue relevant to the result",
            "value": "pancreas",
            "unit": None,
            "evidence_indices": [0],
        },
    ]
    ingestor._resolve_key = lambda cursor, proposed_name: (
        ("SamplePatient_sex", False)
        if proposed_name == "patient sex"
        else ("body organ", True)
    )

    filter_rows, key_names, description_rows = ingestor._build_rows_for_source_cluster(
        None,
        42,
        [{"key": "title", "value": "Example"}],
    )

    assert filter_rows == [
        (42, "SamplePatient_sex", "female", None, "INFERRED"),
        (42, "body organ", "pancreas", None, "INFERRED"),
    ]
    assert key_names == ["SamplePatient_sex", "body organ"]
    assert description_rows == [
        ("body organ", "Body organ or tissue relevant to the result")
    ]


def test_insert_filter_rows_uses_sql_deduplication_against_existing_filters() -> None:
    ingestor = _make_ingestor()
    cursor = _CursorStub()

    ingestor._insert_filter_rows(
        cursor,
        [
            (42, "SamplePatient_sex", "female", None, "INFERRED"),
            (42, "body organ", "pancreas", None, "INFERRED"),
            (42, "body organ", "pancreas", None, "INFERRED"),
        ],
    )

    query, params = cursor.executed[0]
    assert "WITH candidate_rows AS" in query
    assert "SELECT DISTINCT" in query
    assert "WHERE NOT EXISTS" in query
    assert "existing.type IS DISTINCT FROM 'INFERRED'::filter_type" in query
    assert params == (
        [42, 42, 42],
        ["SamplePatient_sex", "body organ", "body organ"],
        ["female", "pancreas", "pancreas"],
        [None, None, None],
    )


def test_build_rows_for_document_merges_cluster_results() -> None:
    ingestor = _make_ingestor()
    ingestor._infer_document_clusters = lambda cursor, document_id, source_rows: [
        (
            1,
            source_rows[:1],
            [(42, "body organ", "pancreas", None, "INFERRED")],
            ["body organ"],
            [("body organ", "Body organ or tissue relevant to the result")],
            [
                {
                    "row": (42, "body organ", "pancreas", None, "INFERRED"),
                    "key_name": "body organ",
                    "description_row": (
                        "body organ",
                        "Body organ or tissue relevant to the result",
                    ),
                    "evidence_rows": {("title", "Example")},
                }
            ],
        ),
        (
            2,
            source_rows[1:],
            [
                (42, "body organ", "pancreas", None, "INFERRED"),
                (42, "disease", "covid-19", None, "INFERRED"),
            ],
            ["body organ", "disease"],
            [("disease", "Disease or condition")],
            [
                {
                    "row": (42, "body organ", "pancreas", None, "INFERRED"),
                    "key_name": "body organ",
                    "description_row": (
                        "body organ",
                        "Body organ or tissue relevant to the result",
                    ),
                    "evidence_rows": {("summary", "Summary")},
                },
                {
                    "row": (42, "disease", "covid-19", None, "INFERRED"),
                    "key_name": "disease",
                    "description_row": ("disease", "Disease or condition"),
                    "evidence_rows": {("summary", "Summary")},
                },
            ],
        ),
    ]

    filter_rows, key_names, description_rows = ingestor._build_rows_for_document(
        None,
        42,
        [
            {"key": "title", "value": "Example"},
            {"key": "summary", "value": "Summary"},
        ],
    )

    assert filter_rows == [
        (42, "body organ", "pancreas", None, "INFERRED"),
        (42, "disease", "covid-19", None, "INFERRED"),
    ]
    assert key_names == ["body organ", "disease"]
    assert description_rows == [
        ("body organ", "Body organ or tissue relevant to the result"),
        ("disease", "Disease or condition"),
    ]


def test_build_rows_for_document_drops_ambiguous_conflicting_values() -> None:
    ingestor = _make_ingestor()
    ingestor._infer_document_clusters = lambda cursor, document_id, source_rows: [
        (
            1,
            source_rows[:2],
            [(42, "organ", "lung", None, "INFERRED")],
            ["organ"],
            [("organ", "Anatomical organ represented by the dataset")],
            [
                {
                    "row": (42, "organ", "lung", None, "INFERRED"),
                    "key_name": "organ",
                    "description_row": (
                        "organ",
                        "Anatomical organ represented by the dataset",
                    ),
                    "evidence_rows": {
                        ("title", "Lung dataset"),
                        ("summary", "Lung summary"),
                    },
                }
            ],
        ),
        (
            2,
            source_rows[2:],
            [(42, "organ", "kidney", None, "INFERRED")],
            ["organ"],
            [("organ", "Anatomical organ represented by the dataset")],
            [
                {
                    "row": (42, "organ", "kidney", None, "INFERRED"),
                    "key_name": "organ",
                    "description_row": (
                        "organ",
                        "Anatomical organ represented by the dataset",
                    ),
                    "evidence_rows": {
                        ("samples.parameters.Sample_description", "kidney sample")
                    },
                }
            ],
        ),
    ]

    filter_rows, key_names, description_rows = ingestor._build_rows_for_document(
        None,
        42,
        [
            {"key": "title", "value": "Lung dataset"},
            {"key": "summary", "value": "Lung summary"},
            {
                "key": "samples.parameters.Sample_description",
                "value": "kidney sample",
            },
        ],
    )

    assert filter_rows == [
        (42, "organ", "lung", None, "INFERRED"),
    ]
    assert key_names == ["organ"]
    assert description_rows == [
        ("organ", "Anatomical organ represented by the dataset"),
    ]


def test_run_dry_mode_logs_without_writes() -> None:
    cursor = _CursorStub()
    logged_payloads: list[
        tuple[
            int,
            int,
            int,
            list[dict[str, str]],
            list[tuple[int, str, str, str | None, str]],
            list[tuple[str, str]],
        ]
    ] = []
    ingestor = _make_ingestor()
    ingestor.dry_run = True
    ingestor.db_conn_factory = lambda: _ConnectionStub(cursor)

    def load_existing_indexes(cursor) -> None:
        return None

    def fetch_source_rows(cursor) -> list[tuple[int, str, str]]:
        return [
            (101, "title", "Doc A"),
            (202, "summary", "Doc B"),
        ]

    def infer_document_clusters(
        cursor,
        document_id: int,
        source_rows: list[dict[str, str]],
    ) -> list[
        tuple[
            int,
            list[dict[str, str]],
            list[tuple[int, str, str, str | None, str]],
            list[str],
            list[tuple[str, str]],
            list[dict[str, object]],
        ]
    ]:
        return [
            (
                1,
                source_rows,
                [(document_id, "body organ", f"value-{document_id}", None, "INFERRED")],
                ["body organ"],
                [("body organ", f"description-{document_id}")],
                [
                    {
                        "row": (
                            document_id,
                            "body organ",
                            f"value-{document_id}",
                            None,
                            "INFERRED",
                        ),
                        "key_name": "body organ",
                        "description_row": (
                            "body organ",
                            f"description-{document_id}",
                        ),
                        "evidence_rows": {
                            (source_rows[0]["key"], source_rows[0]["value"])
                        },
                    }
                ],
            )
        ]

    def log_dry_run_results(
        document_id: int,
        cluster_index: int,
        cluster_count: int,
        source_rows: list[dict[str, str]],
        filter_rows: list[tuple[int, str, str, str | None, str]],
        description_rows: list[tuple[str, str]],
    ) -> None:
        logged_payloads.append(
            (
                document_id,
                cluster_index,
                cluster_count,
                source_rows,
                filter_rows,
                description_rows,
            )
        )

    def fail_delete_existing_inferred_rows(cursor, document_ids: list[int]) -> None:
        raise AssertionError("delete should not be called in dry run")

    def fail_insert_filter_keys_with_embeddings(cursor, keys) -> None:
        raise AssertionError("filter key insert should not be called in dry run")

    def fail_insert_key_descriptions(
        cursor, description_rows: list[tuple[str, str]]
    ) -> None:
        raise AssertionError("description insert should not be called in dry run")

    def fail_insert_filter_rows(
        cursor, filter_rows: list[tuple[int, str, str, str | None, str]]
    ) -> None:
        raise AssertionError("filter row insert should not be called in dry run")

    ingestor._load_existing_indexes = load_existing_indexes
    ingestor._fetch_source_rows = fetch_source_rows
    ingestor._infer_document_clusters = infer_document_clusters
    ingestor._log_dry_run_results = log_dry_run_results
    ingestor._delete_existing_inferred_rows = fail_delete_existing_inferred_rows
    ingestor.insert_filter_keys_with_embeddings = (
        fail_insert_filter_keys_with_embeddings
    )
    ingestor._insert_key_descriptions = fail_insert_key_descriptions
    ingestor._insert_filter_rows = fail_insert_filter_rows

    ingestor.run()

    assert logged_payloads == [
        (
            101,
            1,
            1,
            [{"key": "title", "value": "Doc A"}],
            [(101, "body organ", "value-101", None, "INFERRED")],
            [("body organ", "description-101")],
        ),
        (
            202,
            1,
            1,
            [{"key": "summary", "value": "Doc B"}],
            [(202, "body organ", "value-202", None, "INFERRED")],
            [("body organ", "description-202")],
        ),
    ]
