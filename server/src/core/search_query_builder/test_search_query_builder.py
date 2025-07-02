import importlib.util
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch, ANY

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
# --- End Dynamic Import ---


# --- Mocks ---
@pytest.fixture
def mock_embedding_model():
    mock = MagicMock()
    mock.encode.return_value = MagicMock(tolist=lambda: [0.1, 0.2, 0.3])
    return mock


@pytest.fixture
def mock_postgres_client():
    # 1. Create the final mock cursor
    mock_cursor = MagicMock(name="MockCursor")
    mock_cursor.fetchall.return_value = []  # Default: no similar names found

    # 2. Create the cursor context manager mock
    mock_cursor_cm = MagicMock(name="MockCursorContextManager")
    mock_cursor_cm.__enter__.return_value = (
        mock_cursor  # This returns the cursor when entering the 'with'
    )
    # Add __exit__ for completeness, although often not strictly needed if no errors/cleanup are tested
    mock_cursor_cm.__exit__ = MagicMock(return_value=None)

    # 3. Create the connection mock
    mock_conn = MagicMock(name="MockConnection")
    mock_conn.cursor.return_value = (
        mock_cursor_cm  # Calling .cursor() returns the context manager
    )

    # 4. Create the client context manager mock (for the outer 'with self.db_client as client:')
    # This mock represents the object returned when __enter__ is called on the main client mock
    mock_client_entered = MagicMock(name="EnteredMockClient")
    # Configure this object to return the mock connection when its cursor method is called
    mock_client_entered.cursor.return_value = mock_cursor_cm

    # 5. Create the main client mock
    mock_client = MagicMock(name="MockPostgresClient")
    # Make the client itself act as the context manager
    mock_client.__enter__ = MagicMock(
        return_value=mock_client_entered
    )  # Entering 'with db_client' returns the configured connection object
    mock_client.__exit__ = MagicMock(return_value=None)

    # Return the main client mock (used by the builder) and the cursor mock (for assertions)
    return mock_client, mock_cursor


@pytest.fixture
def builder(mock_embedding_model, mock_postgres_client):
    client, _ = mock_postgres_client
    return SearchQueryBuilder(mock_embedding_model, client)


# --- End Mocks ---


# --- Test Cases ---


def test_init(mock_embedding_model, mock_postgres_client):
    """Test if the builder initializes correctly."""
    client, _ = mock_postgres_client
    builder_instance = SearchQueryBuilder(mock_embedding_model, client)
    assert builder_instance.embedding_model == mock_embedding_model
    assert builder_instance.db_client == client


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
    ],
)
def test_prepare_keywords_sql(builder, keywords, expected_sql):
    """Test keyword formatting for ts_query."""
    assert builder._prepare_keywords_sql(keywords) == expected_sql


def test_find_similar_names_found(builder, mock_postgres_client, mock_embedding_model):
    """Test finding similar names when matches exist in DB."""
    _, mock_cursor = mock_postgres_client
    mock_cursor.fetchall.return_value = [("similar_name", 0.1), ("another_name", 0.2)]
    raw_name = "test_name"
    similar_names = builder._find_similar_names(raw_name)

    mock_embedding_model.encode.assert_called_once_with(raw_name)
    mock_cursor.execute.assert_called_once_with(
        ANY,  # SQL query string
        (
            [0.1, 0.2, 0.3],
            [0.1, 0.2, 0.3],
            builder._SIMILARITY_THRESHOLD_NAMES,
            [0.1, 0.2, 0.3],
            [0.1, 0.2, 0.3],
            builder._SIMILARITY_THRESHOLD_NAMES,
        ),  # Params
    )
    assert similar_names == ["similar_name", "another_name"]


def test_find_similar_names_not_found(
    builder, mock_postgres_client, mock_embedding_model
):
    """Test finding similar names when no matches exist."""
    _, mock_cursor = mock_postgres_client
    mock_cursor.fetchall.return_value = []  # Simulate no results
    raw_name = "unique_name"
    similar_names = builder._find_similar_names(raw_name)

    mock_embedding_model.encode.assert_called_once_with(raw_name)
    mock_cursor.execute.assert_called_once()
    # If nothing is found, it should return the original name in a list
    assert similar_names == [raw_name]


def test_find_similar_names_empty_input(
    builder, mock_postgres_client, mock_embedding_model
):
    """Test finding similar names with empty input."""
    _, mock_cursor = mock_postgres_client
    similar_names = builder._find_similar_names("")
    mock_embedding_model.encode.assert_not_called()
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
    flags, count = builder._generate_filter_flags(filters_obj)
    assert count == 6
    snapshot.assert_match("\n".join(flags), "generate_filter_flags_simple")


def test_generate_filter_flags_various_operators(builder, snapshot):
    """Test generating flags for various operators and value types."""
    filters_obj = {
        "logic": "OR",
        "conditions": [
            # String comparisons
            {"name": ["title"], "operator": "=", "value": "Test Title"},
            {"name": ["status"], "operator": "!=", "value": "draft"},
            {"name": ["tag"], "operator": "LIKE", "value": "important"},
            {"name": ["label"], "operator": "NOT LIKE", "value": "old"},
            {"name": ["category"], "operator": "NOT ILIKE", "value": "misc"},
            # Numeric comparisons
            {"name": ["count"], "operator": "=", "value": 5},
            {"name": ["score"], "operator": "!=", "value": 0.9},
            {"name": ["rating"], "operator": "<", "value": 3.5},
            {"name": ["level"], "operator": "<=", "value": 10},
            {"name": ["version"], "operator": ">=", "value": 2},
            # Boolean comparison
            {"name": ["is_active"], "operator": "!=", "value": False},
            # NULL checks
            {"name": ["description"], "operator": "IS NULL", "value": "ignored"},
            # List operators
            {
                "name": ["range"],
                "operator": "NOT BETWEEN",
                "value": [100.5, 200.0],
            },
            {"name": ["ids"], "operator": "NOT IN", "value": [1, 2, 3]},
            # Mixed type IN  with string (should be skipped)
            {"name": ["mixed_in"], "operator": "IN", "value": [1, "test", 3.14]},
            # Mixed type IN (should treat as float)
            {"name": ["mixed_in"], "operator": "IN", "value": [1, 3.14]},
            # Mixed type BETWEEN (should treat as float)
            {"name": ["mixed_between"], "operator": "BETWEEN", "value": [5, 15.5]},
            # Invalid value for operator (should be skipped)
            {"name": ["invalid_val"], "operator": "=", "value": [1, 2]},
            # Multiple names
            {
                "name": ["alias1", "alias2"],
                "operator": "=",
                "value": "shared",
            },
        ],
    }
    flags, count = builder._generate_filter_flags(filters_obj)
    # Expect 17 valid flags (invalid_val is skipped)
    assert count == 17
    snapshot.assert_match("\n".join(flags), "generate_filter_flags_various_operators")


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
    flags, count = builder._generate_filter_flags(filters_obj)
    assert count == 3  # One for category, one for price, one for in_stock
    snapshot.assert_match("\n".join(flags), "generate_filter_flags_nested")


def test_generate_filter_flags_invalid_conditions(builder, snapshot):
    """Test flag generation with invalid conditions mixed in."""
    filters_obj = {
        "logic": "AND",
        "conditions": [
            {"name": ["category"], "operator": "=", "value": "valid"},
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
    flags, count = builder._generate_filter_flags(filters_obj)
    assert count == 1  # Only the valid category condition should count
    snapshot.assert_match("\n".join(flags), "generate_filter_flags_invalid_conditions")


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
    logic_and = builder._build_filter_logic(filters_and)
    assert logic_and == "(has_condition_1 > 0 AND has_condition_2 > 0)"

    filters_or = {
        "logic": "OR",
        "conditions": [
            {"name": ["a"], "operator": "=", "value": 1},
            {"name": ["b"], "operator": "=", "value": 2},
        ],
    }
    logic_or = builder._build_filter_logic(filters_or)
    assert logic_or == "(has_condition_1 > 0 OR has_condition_2 > 0)"


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
    logic_nested = builder._build_filter_logic(filters_nested)
    expected = "(has_condition_1 > 0 AND (has_condition_2 > 0 OR has_condition_3 > 0))"
    assert logic_nested == expected


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
    logic_invalid = builder._build_filter_logic(filters_invalid)
    # Expected: (flag1=1 AND (FALSE OR (flag2=1 OR FALSE))) -> (flag1>0 AND flag2>0)
    expected = "(has_condition_1 > 0 AND has_condition_2 > 0)"
    assert logic_invalid == expected


def test_build_filter_logic_empty(builder):
    """Test building logic SQL for empty/fully invalid filters."""
    assert builder._build_filter_logic({}) == "FALSE"
    assert builder._build_filter_logic({"logic": "AND", "conditions": []}) == "FALSE"
    assert (
        builder._build_filter_logic({"logic": "AND", "conditions": [{"name": []}]})
        == "FALSE"
    )


def test_get_empty_subquery(builder, snapshot):
    """Test the SQL generated for an empty subquery."""
    sql = builder._get_empty_subquery()
    snapshot.assert_match(sql, "empty_subquery")


def test_build_filter_subquery_no_filters(builder, snapshot):
    """Test building the subquery when no filters are provided."""
    sql = builder._build_filter_subquery(None)
    snapshot.assert_match(sql, "build_filter_subquery_no_filters")
    sql_empty = builder._build_filter_subquery({})
    assert sql == sql_empty  # Should be identical
    sql_empty_cond = builder._build_filter_subquery({"logic": "AND", "conditions": []})
    assert sql == sql_empty_cond  # Should be identical


def test_build_filter_subquery_with_filters(builder, snapshot):
    """Test building the subquery with a valid filter object."""
    # Mock the helper methods called by _build_filter_subquery
    with patch.object(
        builder,
        "_generate_filter_flags",
        return_value=(["FLAG_DEF_1", "FLAG_DEF_2"], 2),
    ), patch.object(builder, "_collect_keys_recursive") as mock_collect, patch.object(
        builder, "_build_filter_logic", return_value="LOGIC_SQL"
    ):

        filters_obj = {
            "logic": "AND",
            "conditions": [{"name": ["key1"]}, {"name": ["key2"]}],
        }  # Dummy object
        sql = builder._build_filter_subquery(filters_obj)

        # Check that _collect_keys_recursive was called correctly
        mock_collect.assert_called_once()
        # The second argument to _collect_keys_recursive is the set, check its final state
        # Note: This assertion depends on the implementation detail of passing the set directly.
        # It might be better to assert the generated keys_sql part if possible.
        # For now, we trust the snapshot captures the result.

        snapshot.assert_match(sql, "build_filter_subquery_with_filters")


# --- Integration Test for build_query ---


def test_build_query_intention_only(builder, snapshot):
    """Test build_query with only intention."""
    data = {"intention": "find science papers"}
    # Mock filter name update to do nothing for this test
    with patch.object(builder, "_update_filter_names", side_effect=lambda d: d):
        sql = builder.build_query(data)
        snapshot.assert_match(sql, "build_query_intention_only")


def test_build_query_intention_keywords(builder, snapshot):
    """Test build_query with intention and keywords."""
    data = {"intention": "find biology papers", "keywords": ["dna", "rna sequence"]}
    with patch.object(builder, "_update_filter_names", side_effect=lambda d: d):
        sql = builder.build_query(data)
        snapshot.assert_match(sql, "build_query_intention_keywords")


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
        sql = builder.build_query(data)
        # Assert that _find_similar_names was called for 'year' and 'journal'
        mock_find.assert_any_call("year")
        mock_find.assert_any_call("journal")
        assert mock_find.call_count == 2

    snapshot.assert_match(sql, "build_query_intention_filters")


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
                    ],
                },
            ],
        },
    }
    # Patch _find_similar_names with the defined mock function
    with patch.object(
        builder, "_find_similar_names", side_effect=find_mock
    ) as mock_find:
        sql = builder.build_query(data)
        # Assert calls were made as expected
        mock_find.assert_any_call("year")
        mock_find.assert_any_call("author")
        mock_find.assert_any_call("topic")
        assert mock_find.call_count == 3

    snapshot.assert_match(sql, "build_query_all_parts")


def test_build_query_invalid_input(builder):
    """Test build_query with invalid input type."""
    with pytest.raises(ValueError, match="Input 'data' must be a dictionary."):
        builder.build_query("not a dict")


# --- End Test Cases ---
