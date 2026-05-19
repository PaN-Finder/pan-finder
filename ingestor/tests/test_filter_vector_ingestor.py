from filter_vector_ingestor import FilterVectorIngestor


def _make_ingestor(split_keys: set[str] | None = None) -> FilterVectorIngestor:
    ingestor = FilterVectorIngestor.__new__(FilterVectorIngestor)
    ingestor.value_vector_split_keys = split_keys or set()
    return ingestor


def test_process_only_splits_configured_author_like_keys() -> None:
    ingestor = _make_ingestor(split_keys={"authors"})
    captured_single: list[tuple[int, str]] = []
    captured_multi: list[tuple[int, str, list[str]]] = []

    def process_single_names(cursor, rows: list[tuple[int, str]]) -> None:
        captured_single.extend(rows)

    def process_multi_names(cursor, rows: list[tuple[int, str, list[str]]]) -> None:
        captured_multi.extend(rows)

    class _CursorStub:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _ConnectionStub:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self):
            return _CursorStub()

        def commit(self) -> None:
            return None

    ingestor.db_conn_factory = lambda: _ConnectionStub()
    ingestor._process_single_names = process_single_names
    ingestor._process_multi_names = process_multi_names

    ingestor.process(
        [
            (1, 10, "authors", "Else Marie Friis, Peter R. Crane"),
            (
                2,
                10,
                "parameters.SamplePatient_info",
                "pulmonary failure, renal failure, bacterial pneumonia",
            ),
        ]
    )

    assert captured_single == [
        (2, "pulmonary failure, renal failure, bacterial pneumonia"),
    ]
    assert captured_multi == [
        (10, "authors", ["Else Marie Friis", "Peter R. Crane"]),
    ]


def test_process_keeps_last_first_single_name_for_split_keys() -> None:
    ingestor = _make_ingestor(split_keys={"authors"})
    captured_single: list[tuple[int, str]] = []
    captured_multi: list[tuple[int, str, list[str]]] = []

    def process_single_names(cursor, rows: list[tuple[int, str]]) -> None:
        captured_single.extend(rows)

    def process_multi_names(cursor, rows: list[tuple[int, str, list[str]]]) -> None:
        captured_multi.extend(rows)

    class _CursorStub:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    class _ConnectionStub:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self):
            return _CursorStub()

        def commit(self) -> None:
            return None

    ingestor.db_conn_factory = lambda: _ConnectionStub()
    ingestor._process_single_names = process_single_names
    ingestor._process_multi_names = process_multi_names

    ingestor.process(
        [
            (1, 10, "authors", "Marone, Federica"),
        ]
    )

    assert captured_single == [(1, "Marone, Federica")]
    assert captured_multi == []
