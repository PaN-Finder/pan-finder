import importlib.util
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import numpy as np
import pytest
from psycopg.sql import Composable

VALUE_VECTOR_KEYS = (
    "authors",
    "creator",
    "scientificMetadata.author",
    "owner",
    "metadata.authors.name",
    "principalInvestigator",
    "investigator",
    "scientificMetadata.measurement.team",
)

# --- Dynamic Import ---
# Assuming search_query_builder.py is in the same directory as the test file
search_query_builder_file = Path(__file__).parent / "search_query_builder.py"
spec = importlib.util.spec_from_file_location(
    "search_query_builder", str(search_query_builder_file)
)
assert spec is not None, "Spec is None"
search_query_builder = importlib.util.module_from_spec(spec)
assert spec.loader is not None, "Loader is None"
spec.loader.exec_module(search_query_builder)
SearchQueryBuilder = search_query_builder.SearchQueryBuilder
SubqueriesUsed = search_query_builder.SubqueriesUsed
# --- End Dynamic Import ---


# --- Mocks ---
@pytest.fixture
def mock_sentence_transformer():
    mock = MagicMock()

    def _encode(input_, *args, **kwargs):
        # Single string → 1-D array; list of strings → 2-D array (n, 3)
        if isinstance(input_, str):
            return np.array([0.1, 0.2, 0.3])
        return np.array([[0.1, 0.2, 0.3]] * len(input_))

    mock.encode.side_effect = _encode
    return mock


@pytest.fixture
def mock_postgres_client():
    """Mock a psycopg_pool.ConnectionPool with .connection() CM and a connection with .cursor() CM."""
    # Cursor and its context manager
    mock_cursor = MagicMock(name="MockCursor")
    mock_cursor.fetchall.return_value = []  # Default: no similar names found
    mock_cursor_cm = MagicMock(name="MockCursorContextManager")
    mock_cursor_cm.__enter__.return_value = mock_cursor
    mock_cursor_cm.__exit__ = MagicMock(return_value=None)

    # Connection and its cursor behavior
    mock_conn = MagicMock(name="MockConnection")

    # Ensure calling conn.cursor(row_factory=...) returns a context manager
    def _cursor_side_effect(*args, **kwargs):
        return mock_cursor_cm

    mock_conn.cursor.side_effect = _cursor_side_effect

    # Pool.connection() returns a context manager yielding the connection
    mock_conn_cm = MagicMock(name="MockConnectionContextManager")
    mock_conn_cm.__enter__.return_value = mock_conn
    mock_conn_cm.__exit__ = MagicMock(return_value=None)

    mock_pool = MagicMock(name="MockConnectionPool")
    mock_pool.connection.return_value = mock_conn_cm

    return mock_pool, mock_cursor


@pytest.fixture
def builder(mock_sentence_transformer, mock_postgres_client):
    pool, _ = mock_postgres_client
    return SearchQueryBuilder(
        mock_sentence_transformer, pool, value_vector_keys=VALUE_VECTOR_KEYS
    )


# --- End Mocks ---


# --- Test Cases ---


def test_init(mock_sentence_transformer, mock_postgres_client):
    """Test if the builder initializes correctly."""
    pool, _ = mock_postgres_client
    builder_instance = SearchQueryBuilder(
        mock_sentence_transformer, pool, value_vector_keys=VALUE_VECTOR_KEYS
    )
    assert builder_instance.sentence_transformer == mock_sentence_transformer
    assert builder_instance.pool == pool


@pytest.mark.parametrize(
    "keywords, expected_sql",
    [
        ([], ""),
        (["test"], "test"),
        (["foo", "bar"], "foo|bar"),
        (["multi word", "test"], "multi|word|test"),
        (["special-char!", "ok"], "specialchar|ok"),
        ([" leading ", " trailing "], "leading|trailing"),
        (["a", "b", ""], "a|b"),
        (["||pipe||test"], "pipe|test"),
        # Duplicates are preserved (no dedup logic today)
        (["dna", "dna", "rna"], "dna|dna|rna"),
        # Dangerous / punctuation mostly stripped
        ([";DROP", "TABLE"], "DROP|TABLE"),
        # All sanitize away -> empty
        (["!!!", "@@@"], ""),
    ],
)
def test_build_keywords_tsquery_text(builder, keywords, expected_sql):
    """Test keyword formatting for ts_query."""
    assert builder._build_keywords_tsquery_text(keywords) == expected_sql


def test_find_similar_names_found(
    builder, mock_postgres_client, mock_sentence_transformer
):
    """Test finding similar names when matches exist in DB."""
    _, mock_cursor = mock_postgres_client
    mock_cursor.fetchall.return_value = [
        {"name": "similar_name", "distance": 0.1},
        {"name": "another_name", "distance": 0.2},
    ]
    raw_name = "test_name"
    similar_names = builder._find_similar_names(raw_name)

    mock_sentence_transformer.encode.assert_called_once_with(raw_name)
    mock_cursor.execute.assert_called_once_with(
        ANY,  # SQL query string
        (
            [0.1, 0.2, 0.3],
            [0.1, 0.2, 0.3],
            builder._SIMILARITY_THRESHOLD_NAMES,
            [0.1, 0.2, 0.3],
            [0.1, 0.2, 0.3],
            builder._SIMILARITY_THRESHOLD_NAMES,
            [0.1, 0.2, 0.3],
            [0.1, 0.2, 0.3],
            builder._SIMILARITY_THRESHOLD_NAMES,
            builder._SIMILARITY_MINIMUM_RESULTS,
        ),  # Params
    )
    assert similar_names == ["similar_name", "another_name"]


def test_find_similar_names_not_found(
    builder, mock_postgres_client, mock_sentence_transformer
):
    """Test finding similar names when no matches exist."""
    _, mock_cursor = mock_postgres_client
    mock_cursor.fetchall.return_value = []  # Simulate no results
    raw_name = "unique_name"
    similar_names = builder._find_similar_names(raw_name)

    mock_sentence_transformer.encode.assert_called_once_with(raw_name)
    mock_cursor.execute.assert_called_once()
    # If nothing is found, it should return the original name in a list
    assert similar_names == [raw_name]


def test_find_similar_names_empty_input(
    builder, mock_postgres_client, mock_sentence_transformer
):
    """Test finding similar names with empty input."""
    _, mock_cursor = mock_postgres_client
    similar_names = builder._find_similar_names("")
    mock_sentence_transformer.encode.assert_not_called()
    mock_cursor.execute.assert_not_called()
    assert similar_names == []


def test_update_filter_names_simple(builder, mock_postgres_client):
    """Test updating a simple filter structure."""
    client, mock_cursor = mock_postgres_client
    # Mock _find_similar_names directly for simplicity here
    with patch.object(
        builder, "_find_similar_names", return_value=["category_alias", "cat"]
    ) as mock_find:
        data = {
            "filters": {
                "logic": "AND",
                "conditions": [{"name": "category", "operator": "=", "value": "books"}],
            }
        }
        updated_data = builder._update_filter_names(data)
        mock_find.assert_called_once_with("category")
        assert updated_data["filters"]["conditions"][0]["name"] == [
            "category_alias",
            "cat",
        ]


def test_update_filter_names_nested(builder, mock_postgres_client):
    """Test updating a nested filter structure."""
    client, mock_cursor = mock_postgres_client

    # Mock _find_similar_names to return different results based on input
    def find_mock(name):
        if name == "category":
            return ["cat"]
        elif name == "price":
            return ["cost", "value"]
        else:
            return [name]  # Default: return original name

    with patch.object(
        builder, "_find_similar_names", side_effect=find_mock
    ) as mock_find:
        data = {
            "filters": {
                "logic": "AND",
                "conditions": [
                    {"name": "category", "operator": "=", "value": "electronics"},
                    {
                        "logic": "OR",
                        "conditions": [
                            {"name": "price", "operator": "<", "value": 100},
                            {"name": "in_stock", "operator": "=", "value": True},
                        ],
                    },
                ],
            }
        }
        updated_data = builder._update_filter_names(data)
        assert mock_find.call_count == 3
        assert updated_data["filters"]["conditions"][0]["name"] == ["cat"]
        assert updated_data["filters"]["conditions"][1]["conditions"][0]["name"] == [
            "cost",
            "value",
        ]
        assert updated_data["filters"]["conditions"][1]["conditions"][1]["name"] == [
            "in_stock"
        ]


def test_generate_filter_flags_vector_string_operator(builder):
    filters_obj = {
        "logic": "OR",
        "conditions": [
            {
                "name": ["authors", "publisher"],
                "operator": "ILIKE",
                "value": "ESS",
            }
        ],
    }

    condition_vectors = builder._build_condition_vector_map(filters_obj)
    flags, count, valid_condition_ids = builder._generate_filter_flags(
        filters_obj, condition_vectors
    )

    assert count == 1
    assert valid_condition_ids == {id(filters_obj["conditions"][0])}

    flag_sql = flags[0].as_string()
    assert (
        "f.key IN ('authors', 'publisher') AND f.value ILIKE 'ESS%' THEN 2" in flag_sql
    )
    assert (
        "f.key IN ('authors', 'publisher') AND f.value ILIKE '%ESS%' THEN 1" in flag_sql
    )
    assert "f.key IN ('authors')" in flag_sql
    assert "f.value_vector IS NOT NULL" in flag_sql
    assert "< 0.35 THEN 1" in flag_sql


def test_update_filter_names_no_filters(builder):
    """Test updating when no filters are present."""
    with patch.object(builder, "_find_similar_names") as mock_find:
        data = {"intention": "test"}
        updated_data = builder._update_filter_names(data)
        mock_find.assert_not_called()
        assert "filters" not in updated_data or updated_data["filters"] is None


def test_update_filter_names_invalid_structure(builder):
    """Test updating with invalid filter structures."""
    with patch.object(builder, "_find_similar_names") as mock_find:
        # Case 1: filters is not a dict
        data1 = {"filters": "not a dict"}
        updated_data1 = builder._update_filter_names(data1)
        assert (
            updated_data1["filters"] == "not a dict"
        )  # Should not change invalid types
        mock_find.assert_not_called()

        # Case 2: condition is not a dict
        data2 = {"filters": {"logic": "AND", "conditions": ["not a dict"]}}
        updated_data2 = builder._update_filter_names(data2)
        assert (
            updated_data2["filters"] is None
        )  # Invalid condition leads to empty filters
        mock_find.assert_not_called()

        # Case 3: condition missing required keys
        data3 = {
            "filters": {"logic": "AND", "conditions": [{"name": "test"}]}
        }  # Missing op/val
        updated_data3 = builder._update_filter_names(data3)
        assert (
            updated_data3["filters"] is None
        )  # Invalid condition leads to empty filters
        mock_find.assert_not_called()


def test_generate_filter_flags_simple(builder, snapshot):
    """Test generating flags for a simple filter."""
    # Assume names are already updated (lists)
    filters_obj = {
        "logic": "AND",
        "conditions": [
            {"name": ["category"], "operator": "ILIKE", "value": "books"},
            {"name": ["price"], "operator": ">", "value": 10.5},
            {"name": ["available"], "operator": "=", "value": True},
            {"name": ["year"], "operator": "BETWEEN", "value": [2000, 2010]},
            {"name": ["author"], "operator": "IN", "value": ["Doe", "Smith"]},
            {
                "name": ["pages"],
                "operator": "IS NOT NULL",
                "value": None,
            },  # Value ignored for IS NULL/IS NOT NULL
        ],
    }
    flags, count, valid_condition_ids = builder._generate_filter_flags(filters_obj)
    assert count == 6
    assert all(isinstance(f, Composable) for f in flags)
    assert valid_condition_ids == {
        id(filters_obj["conditions"][0]),
        id(filters_obj["conditions"][1]),
        id(filters_obj["conditions"][2]),
        id(filters_obj["conditions"][3]),
        id(filters_obj["conditions"][4]),
        id(filters_obj["conditions"][5]),
    }  # All conditions are valid
    snapshot.assert_match(
        "\n".join(f.as_string() for f in flags), "generate_filter_flags_simple"
    )


def test_generate_filter_flags_string_operators(builder, snapshot):
    """String operators (=, !=, LIKE variants) produce flags; invalid relational ops on strings are skipped."""
    filters_obj = {
        "logic": "OR",
        "conditions": [
            {"name": ["title"], "operator": "=", "value": "Test Title"},
            {"name": ["status"], "operator": "!=", "value": "draft"},
            {"name": ["tag"], "operator": "LIKE", "value": "important"},
            {"name": ["label"], "operator": "ILIKE", "value": "urgent"},
            {"name": ["label"], "operator": "NOT LIKE", "value": "old"},
            {"name": ["category"], "operator": "NOT ILIKE", "value": "misc"},
            # Invalid for strings (should be skipped)
            {"name": ["name"], "operator": ">", "value": "A"},
            {"name": ["name"], "operator": ">=", "value": "B"},
            {"name": ["name"], "operator": "<", "value": "C"},
            {"name": ["name"], "operator": "<=", "value": "D"},
        ],
    }
    flags, count, valid_condition_ids = builder._generate_filter_flags(filters_obj)
    assert count == 6
    assert len(flags) == 6
    assert all(isinstance(f, Composable) for f in flags)
    snapshot.assert_match(
        "\n".join(f.as_string() for f in flags),
        "generate_filter_flags_string_operators",
    )


def test_generate_filter_flags_numeric_operators(builder, snapshot):
    """Numeric comparisons should all be accepted."""
    filters_obj = {
        "logic": "OR",
        "conditions": [
            {"name": ["count"], "operator": "=", "value": 5},
            {"name": ["score"], "operator": "!=", "value": 0.9},
            {"name": ["rating"], "operator": "<", "value": 3.5},
            {"name": ["level"], "operator": "<=", "value": 10},
            {"name": ["version"], "operator": ">=", "value": 2},
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filters_obj)
    assert count == 5
    assert len(flags) == 5
    assert all(isinstance(f, Composable) for f in flags)
    snapshot.assert_match(
        "\n".join(f.as_string() for f in flags),
        "generate_filter_flags_numeric_operators",
    )


def test_generate_filter_flags_boolean_operators(builder, snapshot):
    """Booleans accept only = and !=; relational ops are skipped."""
    filters_obj = {
        "logic": "OR",
        "conditions": [
            {"name": ["is_active"], "operator": "=", "value": True},
            {"name": ["is_active"], "operator": "!=", "value": False},
            {"name": ["is_active"], "operator": ">", "value": True},
            {"name": ["is_active"], "operator": ">=", "value": True},
            {"name": ["is_active"], "operator": "<", "value": False},
            {"name": ["is_active"], "operator": "<=", "value": False},
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filters_obj)
    assert count == 2
    assert len(flags) == 2
    assert all(isinstance(f, Composable) for f in flags)
    snapshot.assert_match(
        "\n".join(f.as_string() for f in flags),
        "generate_filter_flags_boolean_operators",
    )


def test_generate_filter_flags_timestamp_operators(builder, snapshot):
    """Timestamp-like fields accept comparison and BETWEEN variants."""
    filters_obj = {
        "logic": "OR",
        "conditions": [
            {"name": ["created_at"], "operator": "=", "value": "2023-01-01"},
            {"name": ["created_at"], "operator": "!=", "value": "2023-01-02"},
            {"name": ["created_at"], "operator": "<", "value": "2023-01-03"},
            {"name": ["created_at"], "operator": "<=", "value": "2023-01-04"},
            {"name": ["created_at"], "operator": ">", "value": "2023-01-05"},
            {"name": ["created_at"], "operator": ">=", "value": "2023-01-06"},
            {
                "name": ["created_at"],
                "operator": "BETWEEN",
                "value": ["2023-01-01", "2023-01-02"],
            },
            {
                "name": ["created_at"],
                "operator": "NOT BETWEEN",
                "value": ["2023-01-03", "2023-01-04"],
            },
            # With hours/minutes/seconds
            {"name": ["created_at"], "operator": "=", "value": "2023-01-01 12:11:10"},
            {"name": ["created_at"], "operator": "!=", "value": "2023-01-01 12:11:10"},
            {"name": ["created_at"], "operator": "<", "value": "2023-01-01 12:11:10"},
            {"name": ["created_at"], "operator": "<=", "value": "2023-01-01 12:11:10"},
            {"name": ["created_at"], "operator": ">", "value": "2023-01-01 12:11:10"},
            {"name": ["created_at"], "operator": ">=", "value": "2023-01-01 12:11:10"},
            {
                "name": ["created_at"],
                "operator": "BETWEEN",
                "value": ["2023-01-01 12:11:10", "2023-01-02 12:11:10"],
            },
            {
                "name": ["created_at"],
                "operator": "NOT BETWEEN",
                "value": ["2023-01-03 12:11:10", "2023-01-04 12:11:10"],
            },
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filters_obj)
    assert count == 16
    assert len(flags) == 16
    assert all(isinstance(f, Composable) for f in flags)
    snapshot.assert_match(
        "\n".join(f.as_string() for f in flags),
        "generate_filter_flags_timestamp_operators",
    )


def test_generate_filter_flags_null_checks(builder, snapshot):
    """IS NULL/IS NOT NULL checks should generate a flag and ignore value."""
    filters_obj = {
        "logic": "OR",
        "conditions": [
            {"name": ["description"], "operator": "IS NULL", "value": "ignored"},
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filters_obj)
    assert count == 1
    assert len(flags) == 1
    assert all(isinstance(f, Composable) for f in flags)
    snapshot.assert_match(
        "\n".join(f.as_string() for f in flags),
        "generate_filter_flags_null_checks",
    )


def test_generate_filter_flags_range_and_in(builder, snapshot):
    """Range (NOT BETWEEN) and list (NOT IN) operators should work for numerics."""
    filters_obj = {
        "logic": "OR",
        "conditions": [
            {"name": ["range"], "operator": "NOT BETWEEN", "value": [100.5, 200.0]},
            {"name": ["ids"], "operator": "NOT IN", "value": [1, 2, 3]},
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filters_obj)
    assert count == 2
    assert len(flags) == 2
    assert all(isinstance(f, Composable) for f in flags)
    snapshot.assert_match(
        "\n".join(f.as_string() for f in flags),
        "generate_filter_flags_range_and_in",
    )


def test_generate_filter_flags_mixed_types(builder, snapshot):
    """Mixed numeric list with a string should be skipped; numeric-only lists are accepted."""
    filters_obj = {
        "logic": "OR",
        "conditions": [
            {
                "name": ["mixed_in"],
                "operator": "IN",
                "value": [1, "test", 3.14],
            },  # skip
            {"name": ["mixed_in"], "operator": "IN", "value": [1, 3.14]},  # ok
            {
                "name": ["mixed_between"],
                "operator": "BETWEEN",
                "value": [5, 15.5],
            },  # ok
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filters_obj)
    assert count == 2
    assert len(flags) == 2
    assert all(isinstance(f, Composable) for f in flags)
    snapshot.assert_match(
        "\n".join(f.as_string() for f in flags),
        "generate_filter_flags_mixed_types",
    )


def test_generate_filter_flags_numeric_operator_with_unit_and_fallback(builder):
    """Numeric comparison with unit should compare value_si against to_unit and fallback to value_numeric when value_si is NULL."""
    filt = {
        "logic": "AND",
        "conditions": [
            {"name": ["energy"], "operator": ">=", "value": 5, "unit": "meV"}
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filt)
    assert count == 1 and len(flags) == 1
    sql_text = flags[0].as_string()
    # Check both the SI comparison and the fallback numeric comparison appear
    assert "f.value_si >= to_unit(5, 'meV')" in sql_text
    assert "OR (f.value_si IS NULL AND f.value_numeric >= 5)" in sql_text


def test_generate_filter_flags_between_with_unit_and_fallback(builder):
    """BETWEEN with unit should compare using SI and fallback to numeric when SI is NULL."""
    filt = {
        "logic": "AND",
        "conditions": [
            {"name": ["dose"], "operator": "BETWEEN", "value": [1, 10], "unit": "Gy"}
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filt)
    assert count == 1 and len(flags) == 1
    sql_text = flags[0].as_string()
    assert "f.value_si BETWEEN to_unit(1, 'Gy') AND to_unit(10, 'Gy')" in sql_text
    assert "OR (f.value_si IS NULL AND f.value_numeric BETWEEN 1 AND 10)" in sql_text


def test_generate_filter_flags_in_with_unit_and_fallback(builder):
    """IN with unit should compare using SI and fallback to numeric when SI is NULL."""
    filt = {
        "logic": "AND",
        "conditions": [
            {
                "name": ["dose_rate"],
                "operator": "IN",
                "value": [1, 2, 5],
                "unit": "Gy/s",
            }
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filt)
    assert count == 1 and len(flags) == 1
    sql_text = flags[0].as_string()
    assert (
        "f.value_si IN (to_unit(1, 'Gy/s'), to_unit(2, 'Gy/s'), to_unit(5, 'Gy/s'))"
        in sql_text
    )
    assert "OR (f.value_si IS NULL AND f.value_numeric IN (1, 2, 5))" in sql_text


def test_generate_filter_flags_equality_with_unit_casts_to_text(builder):
    """For '=' with unit, value_si and to_unit must be cast to text to avoid rounding issues."""
    filt = {
        "logic": "AND",
        "conditions": [
            {"name": ["energy"], "operator": "=", "value": 5, "unit": "meV"}
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filt)
    assert count == 1 and len(flags) == 1
    sql_text = flags[0].as_string()
    # Ensure text casts present on both sides
    assert "f.value_si::text = to_unit(5, 'meV')::text" in sql_text
    # Fallback should remain numeric without text cast
    assert "OR (f.value_si IS NULL AND f.value_numeric = 5)" in sql_text


def test_generate_filter_flags_inequality_with_unit_casts_to_text(builder):
    """For '!=' with unit, value_si and to_unit must be cast to text to avoid rounding issues."""
    filt = {
        "logic": "AND",
        "conditions": [
            {"name": ["energy"], "operator": "!=", "value": 7.5, "unit": "meV"}
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filt)
    assert count == 1 and len(flags) == 1
    sql_text = flags[0].as_string()
    # Ensure text casts present on both sides
    assert "f.value_si::text != to_unit(7.5, 'meV')::text" in sql_text
    # Fallback should remain numeric without text cast
    assert "OR (f.value_si IS NULL AND f.value_numeric != 7.5)" in sql_text


def test_generate_filter_flags_invalid_value_skipped(builder):
    """Invalid value type for '=' (list) should be skipped entirely."""
    filters_obj = {
        "logic": "OR",
        "conditions": [
            {"name": ["invalid_val"], "operator": "=", "value": [1, 2]},
        ],
    }
    flags, count, valid_ids = builder._generate_filter_flags(filters_obj)
    assert count == 0
    assert flags == []
    assert valid_ids == set()


def test_generate_filter_flags_multiple_names(builder, snapshot):
    """Multiple name aliases should still generate a single flag for the condition."""
    filters_obj = {
        "logic": "OR",
        "conditions": [
            {"name": ["alias1", "alias2"], "operator": "=", "value": "shared"},
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filters_obj)
    assert count == 1
    assert len(flags) == 1
    assert all(isinstance(f, Composable) for f in flags)
    snapshot.assert_match(
        "\n".join(f.as_string() for f in flags),
        "generate_filter_flags_multiple_names",
    )


def test_generate_filter_flags_nested(builder, snapshot):
    """Test generating flags for nested filters."""
    filters_obj = {
        "logic": "AND",
        "conditions": [
            {"name": ["category"], "operator": "=", "value": "electronics"},
            {
                "logic": "OR",
                "conditions": [
                    {"name": ["price"], "operator": "<", "value": 100},
                    {"name": ["in_stock"], "operator": "=", "value": True},
                ],
            },
        ],
    }
    flags, count, valid_condition_ids = builder._generate_filter_flags(filters_obj)
    assert count == 3  # One for category, one for price, one for in_stock
    expected_ids = {
        id(filters_obj["conditions"][0]),
        id(filters_obj["conditions"][1]["conditions"][0]),
        id(filters_obj["conditions"][1]["conditions"][1]),
    }
    assert valid_condition_ids == expected_ids
    assert all(isinstance(f, Composable) for f in flags)
    snapshot.assert_match(
        "\n".join(f.as_string() for f in flags), "generate_filter_flags_nested"
    )


def test_generate_filter_flags_invalid_conditions(builder, snapshot):
    """Test flag generation with invalid conditions mixed in."""
    filters_obj = {
        "logic": "AND",
        "conditions": [
            {"name": ["category"], "operator": "=", "value": "valid"},
            {
                "name": ["elephant"],
                "operator": ">",
                "value": "giraffe",
            },  # Invalid operator for string
            {"name": [], "operator": "=", "value": "invalid name"},  # Invalid name list
            {"operator": "=", "value": "missing name"},
            {
                "name": ["price"],
                "operator": "INVALID_OP",
                "value": 100,
            },  # Invalid operator
            {
                "name": ["year"],
                "operator": "BETWEEN",
                "value": [2000],
            },  # Invalid value for BETWEEN
        ],
    }
    flags, count, valid_condition_ids = builder._generate_filter_flags(filters_obj)
    assert count == 1  # Only the valid category condition should count
    assert valid_condition_ids == {id(filters_obj["conditions"][0])}
    assert all(isinstance(f, Composable) for f in flags)
    snapshot.assert_match(
        "\n".join(f.as_string() for f in flags),
        "generate_filter_flags_invalid_conditions",
    )


def test_collect_keys_recursive(builder):
    """Test collecting unique keys from filters."""
    filters_obj = {
        "logic": "AND",
        "conditions": [
            {
                "name": ["category", "cat_alias"],
                "operator": "=",
                "value": "electronics",
            },
            {
                "logic": "OR",
                "conditions": [
                    {"name": ["price"], "operator": "<", "value": 100},
                    {"name": ["in_stock", "available"], "operator": "=", "value": True},
                    {"name": ["price"], "operator": ">", "value": 50},  # Duplicate key
                ],
            },
            {
                "name": [""],
                "operator": "=",
                "value": "empty name",
            },  # Empty name ignored
            {"name": None, "operator": "=", "value": "None name"},  # None name ignored
        ],
    }
    unique_keys = set()
    builder._collect_keys_recursive(filters_obj, unique_keys)
    assert unique_keys == {"category", "cat_alias", "price", "in_stock", "available"}


def test_build_filter_logic_simple(builder):
    """Test building logic SQL for simple AND/OR."""
    filters_and = {
        "logic": "AND",
        "conditions": [
            {"name": ["a"], "operator": "=", "value": 1},
            {"name": ["b"], "operator": "=", "value": 2},
        ],
    }
    valid_condition_ids = set(id(cond) for cond in filters_and["conditions"])

    logic_and = builder._build_filter_logic(filters_and, valid_condition_ids)
    assert logic_and.as_string() == '("has_condition_1" > 0 AND "has_condition_2" > 0)'

    filters_or = {
        "logic": "OR",
        "conditions": [
            {"name": ["a"], "operator": "=", "value": 1},
            {"name": ["b"], "operator": "=", "value": 2},
        ],
    }
    valid_condition_ids = set(id(cond) for cond in filters_or["conditions"])

    logic_or = builder._build_filter_logic(filters_or, valid_condition_ids)
    assert logic_or.as_string() == '("has_condition_1" > 0 OR "has_condition_2" > 0)'


def test_build_filter_logic_nested(builder):
    """Test building logic SQL for nested conditions."""
    filters_nested = {
        "logic": "AND",
        "conditions": [
            {"name": ["a"], "operator": "=", "value": 1},  # flag 1
            {
                "logic": "OR",
                "conditions": [
                    {"name": ["b"], "operator": "=", "value": 2},  # flag 2
                    {"name": ["c"], "operator": "=", "value": 3},  # flag 3
                ],
            },
        ],
    }
    valid_condition_ids = set(id(cond) for cond in filters_nested["conditions"])
    valid_condition_ids.update(
        id(cond) for cond in filters_nested["conditions"][1]["conditions"]
    )  # Include nested conditions

    logic_nested = builder._build_filter_logic(filters_nested, valid_condition_ids)
    expected = (
        '("has_condition_1" > 0 AND ("has_condition_2" > 0 OR "has_condition_3" > 0))'
    )
    assert logic_nested.as_string() == expected


def test_build_filter_logic_with_invalid(builder):
    """Test building logic SQL when some conditions are invalid."""
    filters_invalid = {
        "logic": "AND",
        "conditions": [
            {"name": ["a"], "operator": "=", "value": 1},  # flag 1 (valid)
            {"name": [], "operator": "=", "value": 2},  # invalid name -> FALSE
            {
                "logic": "OR",
                "conditions": [
                    {"name": ["b"], "operator": "=", "value": 3},  # flag 2 (valid)
                    {"operator": "=", "value": 4},  # missing name -> FALSE
                ],
            },
        ],
    }
    valid_condition_ids = set(id(cond) for cond in filters_invalid["conditions"])
    valid_condition_ids.update(
        id(cond) for cond in filters_invalid["conditions"][2]["conditions"]
    )  # Include nested conditions

    logic_invalid = builder._build_filter_logic(filters_invalid, valid_condition_ids)
    # Expected: (flag1=1 AND (FALSE OR (flag2=1 OR FALSE))) -> (flag1>0 AND flag2>0)
    expected = '("has_condition_1" > 0 AND "has_condition_2" > 0)'
    assert logic_invalid.as_string() == expected


def test_build_filter_logic_empty(builder):
    """Test building logic SQL for empty/fully invalid filters."""
    # Empty filters
    assert builder._build_filter_logic({}, set()).as_string() == "FALSE"
    assert (
        builder._build_filter_logic(
            {"logic": "AND", "conditions": []}, set()
        ).as_string()
        == "FALSE"
    )
    assert (
        builder._build_filter_logic(
            {"logic": "AND", "conditions": [{"name": []}]}, set()
        ).as_string()
        == "FALSE"
    )


def test_get_empty_subquery(builder, snapshot):
    """Test the SQL generated for an empty subquery."""
    sql = builder._get_empty_subquery()
    snapshot.assert_match(sql.as_string(), "empty_subquery")


def test_build_filter_subquery_no_filters(builder, snapshot):
    """Test building the subquery when no filters are provided."""
    sql, activated = builder._build_filter_subquery(None)
    assert activated is False
    snapshot.assert_match(sql.as_string(), "build_filter_subquery_no_filters")
    sql_empty, activated_empty = builder._build_filter_subquery({})
    assert activated_empty is False
    assert sql.as_string() == sql_empty.as_string()  # Should be identical
    sql_empty_cond, activated_cond = builder._build_filter_subquery(
        {"logic": "AND", "conditions": []}
    )
    assert activated_cond is False
    assert sql.as_string() == sql_empty_cond.as_string()  # Should be identical


def test_build_query_intention_only(builder, snapshot):
    """Test build_query with only intention."""
    data = {"intention": "find science papers"}
    # Mock filter name update to do nothing for this test
    with patch.object(builder, "_update_filter_names", side_effect=lambda d: d):
        sql, subqueries_used = builder.build_query(data)
        assert subqueries_used["similarity"] is True
        assert subqueries_used["chunk_similarity"] is True
        assert subqueries_used["keyword"] is False
        assert subqueries_used["full_match"] is False
        assert subqueries_used["partial_match"] is False
        snapshot.assert_match(sql.as_string(), "build_query_intention_only")


def test_build_query_intention_keywords(builder, snapshot):
    """Test build_query with intention and keywords."""
    data = {"intention": "find biology papers", "keywords": ["dna", "rna sequence"]}
    with patch.object(builder, "_update_filter_names", side_effect=lambda d: d):
        sql, subqueries_used = builder.build_query(data)
        assert subqueries_used["keyword"] is True
        snapshot.assert_match(sql.as_string(), "build_query_intention_keywords")


def test_build_query_intention_filters(builder, snapshot):
    """Test build_query with intention and filters (mocking name update)."""
    # client, mock_cursor = mock_postgres_client # No longer needed for this test

    data = {
        "intention": "papers about planets",
        "filters": {
            "logic": "AND",
            "conditions": [
                {"name": "year", "operator": ">", "value": 2020},
                {"name": "journal", "operator": "ILIKE", "value": "Nature"},
            ],
        },
    }
    # Patch _find_similar_names to simply return the original name in a list
    with patch.object(
        builder, "_find_similar_names", side_effect=lambda name: [name]
    ) as mock_find:
        sql, subqueries_used = builder.build_query(data)
        # Assert that _find_similar_names was called for 'year' and 'journal'
        mock_find.assert_any_call("year")
        mock_find.assert_any_call("journal")
        assert mock_find.call_count == 2
        assert subqueries_used["full_match"] is True
        assert subqueries_used["partial_match"] is True

    snapshot.assert_match(sql.as_string(), "build_query_intention_filters")


def test_build_query_invalid_filters(builder, snapshot):
    """Test build_query with invalid filters."""
    data = {
        "intention": "test invalid filters",
        "filters": {
            "logic": "AND",
            "conditions": [
                {"name": "year", "operator": ">", "value": 2020},
                {
                    "name": "elephant",
                    "operator": ">",
                    "value": "giraffe",
                },  # Invalid operator for string
            ],
        },
    }
    # Patch _find_similar_names to return the original name in a list
    with patch.object(builder, "_find_similar_names", side_effect=lambda name: [name]):
        sql, subqueries_used = builder.build_query(data)
        assert subqueries_used["full_match"] is True  # year condition is valid
        assert subqueries_used["partial_match"] is True

    snapshot.assert_match(sql.as_string(), "build_query_invalid_filters")


def test_build_query_all_parts(builder, snapshot):
    """Test build_query with intention, keywords, and nested filters."""

    # Define the mock behavior for finding similar names
    def find_mock(name):
        if name == "year":
            return ["publication_year"]
        if name == "author":
            return ["authors", "creator"]
        if name == "topic":
            return ["subject", "field"]
        return [name]  # Default

    # No need to set mock_cursor.fetchall.side_effect anymore

    data = {
        "intention": "research on LLMs",
        "keywords": ["transformer", "attention mechanism"],
        "filters": {
            "logic": "OR",
            "conditions": [
                {"name": "year", "operator": ">=", "value": 2022},
                {
                    "logic": "AND",
                    "conditions": [
                        {"name": "author", "operator": "ILIKE", "value": "vaswani"},
                        {"name": "topic", "operator": "IN", "value": ["NLP", "AI"]},
                        {"name": "energy", "operator": ">=", "value": 5, "unit": "meV"},
                    ],
                },
            ],
        },
    }
    # Patch _find_similar_names with the defined mock function
    with patch.object(
        builder, "_find_similar_names", side_effect=find_mock
    ) as mock_find:
        sql, subqueries_used = builder.build_query(data)
        # Assert calls were made as expected
        mock_find.assert_any_call("year")
        mock_find.assert_any_call("author")
        mock_find.assert_any_call("topic")
        mock_find.assert_any_call("energy")
        assert mock_find.call_count == 4
        assert subqueries_used["similarity"] is True
        assert subqueries_used["keyword"] is True
        assert subqueries_used["full_match"] is True

    snapshot.assert_match(sql.as_string(), "build_query_all_parts")


def test_build_query_invalid_input(builder):
    """Test build_query with invalid input type."""
    with pytest.raises(ValueError, match="Input 'params' must be a dictionary."):
        builder.build_query("not a dict")


def test_build_query_keywords_only_no_intention(builder, snapshot):
    """When only keywords are provided, intention embedding shouldn't be computed."""
    data = {"keywords": ["protein", "folding mechanism"]}
    with (
        patch.object(builder, "_update_filter_names", side_effect=lambda d: d),
        patch.object(builder.sentence_transformer, "encode") as mock_encode,
    ):
        sql, subqueries_used = builder.build_query(data)
        mock_encode.assert_not_called()
        assert subqueries_used["similarity"] is False
        assert subqueries_used["keyword"] is True
    snapshot.assert_match(sql.as_string(), "build_query_keywords_only_no_intention")


def test_build_query_filters_only_no_intention(builder, snapshot):
    """Filters without intention should not trigger embedding encoding."""
    data = {
        "filters": {
            "logic": "AND",
            "conditions": [
                {"name": "year", "operator": ">", "value": 2021},
                {"name": "journal", "operator": "ILIKE", "value": "Science"},
            ],
        }
    }
    with (
        patch.object(builder, "_find_similar_names", side_effect=lambda n: [n]),
        patch.object(builder.sentence_transformer, "encode") as mock_encode,
    ):
        sql, subqueries_used = builder.build_query(data)
        mock_encode.assert_not_called()
        assert subqueries_used["similarity"] is False
        assert subqueries_used["full_match"] is True
    snapshot.assert_match(sql.as_string(), "build_query_filters_only_no_intention")


def test_build_filter_subquery_all_invalid_conditions(builder):
    """All invalid conditions should yield the empty subquery."""
    invalid_filters = {
        "logic": "AND",
        "conditions": [
            {"name": [], "operator": "=", "value": 1},  # empty name list
            {"operator": "=", "value": 2},  # missing name
            {
                "name": ["x"],
                "operator": "IN",
                "value": [],
            },  # empty IN list (should skip)
        ],
    }
    empty = builder._get_empty_subquery().as_string()
    subquery, activated = builder._build_filter_subquery(invalid_filters)
    assert subquery.as_string() == empty
    assert activated is False


def test_generate_filter_flags_case_insensitive_operator(builder):
    """Lowercase ilike should be accepted same as ILIKE."""
    filt = {
        "logic": "AND",
        "conditions": [
            {"name": ["journal"], "operator": "ilike", "value": "nature"},
        ],
    }
    flags, count, valid_ids = builder._generate_filter_flags(filt)
    assert count == 1
    assert len(flags) == 1
    assert len(valid_ids) == 1
    sql_fragment = flags[0].as_string()
    assert "ILIKE" in sql_fragment  # normalized


def test_generate_filter_flags_in_empty_list_skipped(builder):
    """IN with empty list should not create a flag."""
    filt = {
        "logic": "AND",
        "conditions": [{"name": ["id"], "operator": "IN", "value": []}],
    }
    flags, count, valid_ids = builder._generate_filter_flags(filt)
    assert count == 0
    assert flags == []
    assert valid_ids == set()


def test_generate_filter_flags_between_boundary(builder):
    """BETWEEN boundaries should appear verbatim (inclusive semantics)."""
    filt = {
        "logic": "AND",
        "conditions": [
            {"name": ["year"], "operator": "BETWEEN", "value": [2000, 2010]}
        ],
    }
    flags, count, _ = builder._generate_filter_flags(filt)
    assert count == 1
    text = flags[0].as_string()
    assert (
        text
        == "MAX(CASE WHEN f.key IN ('year') AND f.value_numeric BETWEEN 2000 AND 2010 THEN 1 ELSE 0 END) AS \"has_condition_1\""
    )


def test_update_filter_names_filters_become_empty_sets_none(builder):
    """If all conditions invalid after update, filters should become None."""
    data = {
        "filters": {
            "logic": "AND",
            "conditions": [
                {"name": "", "operator": "=", "value": 1},  # invalid empty name
                {"operator": "=", "value": 2},  # missing name
            ],
        }
    }
    updated = builder._update_filter_names(data)
    assert updated["filters"] is None


def test_build_query_all_invalid_filters_behaves_like_no_filters(builder):
    """Query with all invalid filters should match SQL of a query with no filters."""
    params_with_invalid = {
        "intention": "explore galaxies",
        "filters": {
            "logic": "AND",
            "conditions": [{"name": "", "operator": "=", "value": 1}],
        },
    }
    params_no_filters = {"intention": "explore galaxies"}
    with patch.object(builder, "_find_similar_names", side_effect=lambda n: [n]):
        sql_invalid, su_invalid = builder.build_query(params_with_invalid)
    sql_none, su_none = builder.build_query(params_no_filters)
    assert sql_invalid.as_string() == sql_none.as_string()
    assert su_invalid["full_match"] is False
    assert su_none["full_match"] is False


def test_build_keywords_tsquery_text_large_list(builder):
    """Large keyword lists should not error and keep ordering."""
    big_list = [f"k{i}" for i in range(50)]
    tsq = builder._build_keywords_tsquery_text(big_list)
    assert tsq.startswith("k0|") and tsq.count("|") == 49


# --- End Test Cases ---
