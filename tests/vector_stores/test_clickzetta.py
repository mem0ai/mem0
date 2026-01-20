import json
import uuid
from unittest.mock import MagicMock, patch

import pytest

from mem0.vector_stores.clickzetta import ClickZetta, OutputData


# ---------------------- Fixtures ---------------------- #


@pytest.fixture
@patch("mem0.vector_stores.clickzetta.clickzetta_dbapi")
def clickzetta_fixture(mock_dbapi):
    """Create a ClickZetta instance with mocked database connection."""
    mock_connection = MagicMock()
    mock_cursor = MagicMock()
    mock_connection.cursor.return_value = mock_cursor
    mock_dbapi.connect.return_value = mock_connection
    
    # Mock table existence check to return empty (table doesn't exist)
    mock_cursor.fetchall.return_value = [(0,)]
    
    clickzetta = ClickZetta(
        collection_name="test_collection",
        embedding_model_dims=384,
        service="test-service",
        instance="test-instance",
        workspace="test-workspace",
        schema="test_schema",
        username="test-user",
        password="test-password",
        vcluster="test-vcluster",
        protocol="http",
        distance_metric="cosine",
    )
    return clickzetta, mock_connection, mock_cursor


# ---------------------- Initialization Tests ---------------------- #


def test_initialization(clickzetta_fixture):
    """Test that ClickZetta initializes correctly."""
    clickzetta, mock_connection, mock_cursor = clickzetta_fixture
    
    assert clickzetta.collection_name == "test_collection"
    assert clickzetta.embedding_model_dims == 384
    assert clickzetta.distance_metric == "cosine"
    assert clickzetta.schema == "test_schema"
    assert clickzetta.protocol == "http"


def test_create_connection(clickzetta_fixture):
    """Test that connection is created with correct parameters."""
    clickzetta, mock_connection, _ = clickzetta_fixture
    assert clickzetta.connection is not None


def test_create_col(clickzetta_fixture):
    """Test collection creation."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    mock_cursor.fetchall.return_value = [(0,)]
    
    clickzetta.create_col(vector_size=384, distance="cosine")
    
    # Verify CREATE TABLE was called
    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    create_calls = [c for c in calls if "CREATE TABLE" in c]
    assert len(create_calls) > 0


def test_create_col_already_exists(clickzetta_fixture):
    """Test that collection creation is skipped if table exists."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    mock_cursor.fetchall.return_value = [(1,)]  # Table exists
    
    clickzetta.create_col(vector_size=384, distance="cosine")
    
    # Verify CREATE TABLE was NOT called
    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    create_calls = [c for c in calls if "CREATE TABLE" in c]
    assert len(create_calls) == 0


# ---------------------- Insert Tests ---------------------- #


def test_insert(clickzetta_fixture):
    """Test vector insertion."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"user_id": "user1"}, {"user_id": "user2"}]
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    
    clickzetta.insert(vectors=vectors, payloads=payloads, ids=ids)
    
    # Verify INSERT was called twice
    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    insert_calls = [c for c in calls if "INSERT INTO" in c]
    assert len(insert_calls) == 2


def test_insert_generates_ids(clickzetta_fixture):
    """Test that IDs are generated if not provided."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{"user_id": "user1"}]
    
    clickzetta.insert(vectors=vectors, payloads=payloads)
    
    # Verify INSERT was called
    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    insert_calls = [c for c in calls if "INSERT INTO" in c]
    assert len(insert_calls) == 1


def test_insert_generates_payloads(clickzetta_fixture):
    """Test that empty payloads are generated if not provided."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    vectors = [[0.1, 0.2, 0.3]]
    ids = ["test-id"]
    
    clickzetta.insert(vectors=vectors, ids=ids)
    
    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    insert_calls = [c for c in calls if "INSERT INTO" in c]
    assert len(insert_calls) == 1


def test_insert_with_special_characters(clickzetta_fixture):
    """Test insertion with special characters in payload."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{"data": "Hello 'world' with \"quotes\""}]
    ids = ["test-id"]
    
    clickzetta.insert(vectors=vectors, payloads=payloads, ids=ids)
    
    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    insert_calls = [c for c in calls if "INSERT INTO" in c]
    assert len(insert_calls) == 1


def test_insert_failure_raises_exception(clickzetta_fixture):
    """Test that insert failure raises exception."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    mock_cursor.execute.side_effect = Exception("Insert failed")
    
    vectors = [[0.1, 0.2, 0.3]]
    
    with pytest.raises(Exception) as exc_info:
        clickzetta.insert(vectors=vectors)
    
    assert "Insert failed" in str(exc_info.value)


# ---------------------- Search Tests ---------------------- #


def test_search(clickzetta_fixture):
    """Test vector search."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    mock_results = [
        ("id1", '{"user_id": "user1", "data": "test data"}', 0.1),
        ("id2", '{"user_id": "user1", "data": "test data 2"}', 0.2),
    ]
    mock_cursor.fetchall.return_value = mock_results
    
    vectors = [0.1, 0.2, 0.3]
    results = clickzetta.search(query="test", vectors=vectors, limit=5)
    
    assert len(results) == 2
    assert isinstance(results[0], OutputData)
    assert results[0].id == "id1"
    assert results[0].payload["user_id"] == "user1"


def test_search_with_filters(clickzetta_fixture):
    """Test search with filters."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    mock_results = [
        ("id1", '{"user_id": "user1", "agent_id": "agent1"}', 0.1),
    ]
    mock_cursor.fetchall.return_value = mock_results
    
    vectors = [0.1, 0.2, 0.3]
    filters = {"user_id": "user1", "agent_id": "agent1"}
    results = clickzetta.search(query="test", vectors=vectors, limit=5, filters=filters)
    
    # Verify filter clause was included in query
    call_args = mock_cursor.execute.call_args[0][0]
    assert "user_id" in call_args
    assert "agent_id" in call_args
    
    assert len(results) == 1
    assert results[0].payload["user_id"] == "user1"


def test_search_with_single_filter(clickzetta_fixture):
    """Test search with single filter."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    mock_results = [("id1", '{"user_id": "alice"}', 0.1)]
    mock_cursor.fetchall.return_value = mock_results
    
    filters = {"user_id": "alice"}
    results = clickzetta.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5, filters=filters)
    
    call_args = mock_cursor.execute.call_args[0][0]
    assert "user_id" in call_args
    assert len(results) == 1


def test_search_with_no_filters(clickzetta_fixture):
    """Test search with no filters."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    mock_results = [("id1", '{"key": "value"}', 0.1)]
    mock_cursor.fetchall.return_value = mock_results
    
    results = clickzetta.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5, filters=None)
    
    assert len(results) == 1


def test_search_empty_results(clickzetta_fixture):
    """Test search with no results."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    mock_cursor.fetchall.return_value = []
    
    vectors = [0.1, 0.2, 0.3]
    results = clickzetta.search(query="test", vectors=vectors, limit=5)
    
    assert len(results) == 0


def test_search_with_invalid_json_payload(clickzetta_fixture):
    """Test search with invalid JSON payload."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    mock_results = [("id1", "invalid json {", 0.1)]
    mock_cursor.fetchall.return_value = mock_results
    
    results = clickzetta.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5)
    
    assert len(results) == 1
    assert results[0].payload == {}  # Should default to empty dict


def test_search_with_null_payload(clickzetta_fixture):
    """Test search with null payload."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    mock_results = [("id1", None, 0.1)]
    mock_cursor.fetchall.return_value = mock_results
    
    results = clickzetta.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5)
    
    assert len(results) == 1
    assert results[0].payload == {}


# ---------------------- Delete Tests ---------------------- #


def test_delete(clickzetta_fixture):
    """Test vector deletion."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    vector_id = str(uuid.uuid4())
    clickzetta.delete(vector_id=vector_id)
    
    call_args = mock_cursor.execute.call_args[0][0]
    assert "DELETE FROM" in call_args
    assert vector_id in call_args


# ---------------------- Update Tests ---------------------- #


def test_update(clickzetta_fixture):
    """Test vector update."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    vector_id = str(uuid.uuid4())
    new_vector = [0.2, 0.3, 0.4]
    new_payload = {"user_id": "user2"}
    
    clickzetta.update(vector_id=vector_id, vector=new_vector, payload=new_payload)
    
    call_args = mock_cursor.execute.call_args[0][0]
    assert "UPDATE" in call_args
    assert vector_id in call_args


def test_update_vector_only(clickzetta_fixture):
    """Test updating only the vector."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    vector_id = str(uuid.uuid4())
    new_vector = [0.2, 0.3, 0.4]
    
    clickzetta.update(vector_id=vector_id, vector=new_vector)
    
    call_args = mock_cursor.execute.call_args[0][0]
    assert "vector =" in call_args
    assert "payload =" not in call_args


def test_update_payload_only(clickzetta_fixture):
    """Test updating only the payload."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    vector_id = str(uuid.uuid4())
    new_payload = {"user_id": "user2"}
    
    clickzetta.update(vector_id=vector_id, payload=new_payload)
    
    call_args = mock_cursor.execute.call_args[0][0]
    assert "payload =" in call_args
    assert "vector =" not in call_args


def test_update_nothing(clickzetta_fixture):
    """Test update with no changes."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    vector_id = str(uuid.uuid4())
    clickzetta.update(vector_id=vector_id)
    
    # Should not execute any query
    assert mock_cursor.execute.call_count == 0


# ---------------------- Get Tests ---------------------- #


def test_get(clickzetta_fixture):
    """Test getting a single vector."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    vector_id = str(uuid.uuid4())
    mock_result = [(vector_id, [0.1, 0.2, 0.3], '{"user_id": "user1"}')]
    mock_cursor.fetchall.return_value = mock_result
    
    result = clickzetta.get(vector_id=vector_id)
    
    assert result is not None
    assert result.id == vector_id
    assert result.payload["user_id"] == "user1"


def test_get_not_found(clickzetta_fixture):
    """Test getting a non-existent vector."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    mock_cursor.fetchall.return_value = []
    
    result = clickzetta.get(vector_id="non-existent-id")
    
    assert result is None


def test_get_with_invalid_payload(clickzetta_fixture):
    """Test get with invalid JSON payload."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    vector_id = str(uuid.uuid4())
    mock_result = [(vector_id, [0.1, 0.2, 0.3], "invalid json")]
    mock_cursor.fetchall.return_value = mock_result
    
    result = clickzetta.get(vector_id=vector_id)
    
    assert result is not None
    assert result.payload == {}


# ---------------------- List Collections Tests ---------------------- #


def test_list_cols(clickzetta_fixture):
    """Test listing collections."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    mock_result = [("table1",), ("table2",), ("test_collection",)]
    mock_cursor.fetchall.return_value = mock_result
    
    result = clickzetta.list_cols()
    
    assert len(result) == 3
    assert "test_collection" in result


# ---------------------- Delete Collection Tests ---------------------- #


def test_delete_col(clickzetta_fixture):
    """Test collection deletion."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    clickzetta.delete_col()
    
    call_args = mock_cursor.execute.call_args[0][0]
    assert "DROP TABLE" in call_args
    assert "test_collection" in call_args


# ---------------------- Collection Info Tests ---------------------- #


def test_col_info(clickzetta_fixture):
    """Test getting collection info."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    mock_cursor.fetchall.return_value = [(100,)]
    
    result = clickzetta.col_info()
    
    assert result["name"] == "test_collection"
    assert result["schema"] == "test_schema"
    assert result["row_count"] == 100
    assert result["embedding_dims"] == 384
    assert result["distance_metric"] == "cosine"


# ---------------------- List Vectors Tests ---------------------- #


def test_list(clickzetta_fixture):
    """Test listing vectors."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    mock_results = [
        ("id1", '{"user_id": "user1"}'),
        ("id2", '{"user_id": "user2"}'),
    ]
    mock_cursor.fetchall.return_value = mock_results
    
    results = clickzetta.list(limit=100)
    
    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[1].id == "id2"


def test_list_with_filters(clickzetta_fixture):
    """Test listing vectors with filters."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    mock_results = [("id1", '{"user_id": "user1"}')]
    mock_cursor.fetchall.return_value = mock_results
    
    filters = {"user_id": "user1"}
    results = clickzetta.list(filters=filters, limit=100)
    
    call_args = mock_cursor.execute.call_args[0][0]
    assert "user_id" in call_args
    
    assert len(results) == 1


def test_list_with_no_filters(clickzetta_fixture):
    """Test listing vectors with no filters."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    
    mock_results = [("id1", '{"key": "value"}')]
    mock_cursor.fetchall.return_value = mock_results
    
    results = clickzetta.list(filters=None, limit=100)
    
    assert len(results) == 1


# ---------------------- Reset Tests ---------------------- #


def test_reset(clickzetta_fixture):
    """Test resetting the collection."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    mock_cursor.fetchall.return_value = [(0,)]
    
    clickzetta.reset()
    
    calls = [str(c) for c in mock_cursor.execute.call_args_list]
    drop_calls = [c for c in calls if "DROP TABLE" in c]
    create_calls = [c for c in calls if "CREATE TABLE" in c]
    
    assert len(drop_calls) > 0
    assert len(create_calls) > 0


# ---------------------- Filter Clause Tests ---------------------- #


def test_build_filter_clause_empty(clickzetta_fixture):
    """Test filter clause with no filters."""
    clickzetta, _, _ = clickzetta_fixture
    
    result = clickzetta._build_filter_clause(None)
    assert result == ""
    
    result = clickzetta._build_filter_clause({})
    assert result == ""


def test_build_filter_clause_string_value(clickzetta_fixture):
    """Test filter clause with string value."""
    clickzetta, _, _ = clickzetta_fixture
    
    filters = {"user_id": "user1"}
    result = clickzetta._build_filter_clause(filters)
    
    assert "user_id" in result
    assert "user1" in result


def test_build_filter_clause_numeric_value(clickzetta_fixture):
    """Test filter clause with numeric value."""
    clickzetta, _, _ = clickzetta_fixture
    
    filters = {"count": 10}
    result = clickzetta._build_filter_clause(filters)
    
    assert "count" in result
    assert "10" in result


def test_build_filter_clause_range_value(clickzetta_fixture):
    """Test filter clause with range value."""
    clickzetta, _, _ = clickzetta_fixture
    
    filters = {"score": {"gte": 0.5, "lte": 1.0}}
    result = clickzetta._build_filter_clause(filters)
    
    assert "score" in result
    assert ">=" in result
    assert "<=" in result


def test_build_filter_clause_multiple_filters(clickzetta_fixture):
    """Test filter clause with multiple filters."""
    clickzetta, _, _ = clickzetta_fixture
    
    filters = {"user_id": "user1", "agent_id": "agent1", "run_id": "run1"}
    result = clickzetta._build_filter_clause(filters)
    
    assert "user_id" in result
    assert "agent_id" in result
    assert "run_id" in result
    assert "AND" in result


# ---------------------- Distance Expression Tests ---------------------- #


def test_build_distance_expression_cosine(clickzetta_fixture):
    """Test distance expression for cosine metric."""
    clickzetta, _, _ = clickzetta_fixture
    clickzetta.distance_metric = "cosine"
    
    result = clickzetta._build_distance_expression([0.1, 0.2, 0.3])
    
    assert "cosine_distance" in result


def test_build_distance_expression_euclidean(clickzetta_fixture):
    """Test distance expression for euclidean metric."""
    clickzetta, _, _ = clickzetta_fixture
    clickzetta.distance_metric = "euclidean"
    
    result = clickzetta._build_distance_expression([0.1, 0.2, 0.3])
    
    assert "L2_distance" in result


def test_build_distance_expression_dot_product(clickzetta_fixture):
    """Test distance expression for dot product metric."""
    clickzetta, _, _ = clickzetta_fixture
    clickzetta.distance_metric = "dot_product"
    
    result = clickzetta._build_distance_expression([0.1, 0.2, 0.3])
    
    assert "dot_product" in result


def test_build_distance_expression_default(clickzetta_fixture):
    """Test distance expression for unknown metric defaults to cosine."""
    clickzetta, _, _ = clickzetta_fixture
    clickzetta.distance_metric = "unknown"
    
    result = clickzetta._build_distance_expression([0.1, 0.2, 0.3])
    
    assert "cosine_distance" in result


# ---------------------- Score Conversion Tests ---------------------- #


def test_score_conversion_cosine(clickzetta_fixture):
    """Test score conversion for cosine distance."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    clickzetta.distance_metric = "cosine"
    
    # cosine_distance = 0.2, score should be 1 - 0.2/2 = 0.9
    mock_results = [("id1", '{"user_id": "user1"}', 0.2)]
    mock_cursor.fetchall.return_value = mock_results
    
    results = clickzetta.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5)
    
    assert abs(results[0].score - 0.9) < 0.001


def test_score_conversion_euclidean(clickzetta_fixture):
    """Test score conversion for euclidean distance."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    clickzetta.distance_metric = "euclidean"
    
    # L2_distance = 1.0, score should be 1 / (1 + 1.0) = 0.5
    mock_results = [("id1", '{"user_id": "user1"}', 1.0)]
    mock_cursor.fetchall.return_value = mock_results
    
    results = clickzetta.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5)
    
    assert abs(results[0].score - 0.5) < 0.001


def test_score_conversion_dot_product(clickzetta_fixture):
    """Test score conversion for dot product."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    clickzetta.distance_metric = "dot_product"
    
    # distance = -0.8 (negated dot product), score should be 0.8
    mock_results = [("id1", '{"user_id": "user1"}', -0.8)]
    mock_cursor.fetchall.return_value = mock_results
    
    results = clickzetta.search(query="test", vectors=[0.1, 0.2, 0.3], limit=5)
    
    assert abs(results[0].score - 0.8) < 0.001


# ---------------------- Connection Tests ---------------------- #


@patch("mem0.vector_stores.clickzetta.clickzetta_dbapi")
def test_connection_failure(mock_dbapi):
    """Test handling of connection failure."""
    mock_dbapi.connect.side_effect = Exception("Connection failed")
    
    with pytest.raises(Exception) as exc_info:
        ClickZetta(
            collection_name="test",
            embedding_model_dims=384,
            service="test",
            instance="test",
            workspace="test",
            schema="test",
            username="test",
            password="test",
            vcluster="test",
        )
    
    assert "Connection failed" in str(exc_info.value)


# ---------------------- Query Execution Tests ---------------------- #


def test_execute_query_select(clickzetta_fixture):
    """Test SELECT query returns results."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    mock_cursor.fetchall.return_value = [("row1",), ("row2",)]
    
    results = clickzetta._execute_query("SELECT * FROM test")
    
    assert len(results) == 2
    mock_cursor.fetchall.assert_called_once()


def test_execute_query_failure(clickzetta_fixture):
    """Test query failure raises exception."""
    clickzetta, _, mock_cursor = clickzetta_fixture
    mock_cursor.reset_mock()
    mock_cursor.execute.side_effect = Exception("Query failed")
    
    with pytest.raises(Exception) as exc_info:
        clickzetta._execute_query("SELECT * FROM test")
    
    assert "Query failed" in str(exc_info.value)
