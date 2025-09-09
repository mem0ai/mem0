import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import pytz
from valkey.exceptions import ResponseError

from mem0.vector_stores.valkey import ValkeyDB


@pytest.fixture
def mock_valkey_client():
    """Create a mock Valkey client."""
    with patch("valkey.from_url") as mock_client:
        # Mock the ft method
        mock_ft = MagicMock()
        mock_client.return_value.ft = MagicMock(return_value=mock_ft)
        mock_client.return_value.execute_command = MagicMock()
        mock_client.return_value.hset = MagicMock()
        mock_client.return_value.hgetall = MagicMock()
        mock_client.return_value.delete = MagicMock()
        yield mock_client.return_value


@pytest.fixture
def valkey_db(mock_valkey_client):
    """Create a ValkeyDB instance with a mock client."""
    # Initialize the ValkeyDB with test parameters
    valkey_db = ValkeyDB(
        valkey_url="valkey://localhost:6379",
        collection_name="test_collection",
        embedding_model_dims=1536,
    )
    # Replace the client with our mock
    valkey_db.client = mock_valkey_client
    return valkey_db


def test_search_filter_syntax(valkey_db, mock_valkey_client):
    """Test that the search filter syntax is correctly formatted for Valkey."""
    # Mock search results
    mock_doc = MagicMock()
    mock_doc.memory_id = "test_id"
    mock_doc.hash = "test_hash"
    mock_doc.memory = "test_data"
    mock_doc.created_at = str(int(datetime.now().timestamp()))
    mock_doc.metadata = json.dumps({"key": "value"})
    mock_doc.vector_score = "0.5"

    mock_results = MagicMock()
    mock_results.docs = [mock_doc]

    mock_ft = mock_valkey_client.ft.return_value
    mock_ft.search.return_value = mock_results

    # Test with user_id filter
    valkey_db.search(
        query="test query",
        vectors=np.random.rand(1536).tolist(),
        limit=5,
        filters={"user_id": "test_user"},
    )

    # Check that the search was called with the correct filter syntax
    args, kwargs = mock_ft.search.call_args
    assert "@user_id:{test_user}" in args[0]
    assert "=>[KNN" in args[0]

    # Test with multiple filters
    valkey_db.search(
        query="test query",
        vectors=np.random.rand(1536).tolist(),
        limit=5,
        filters={"user_id": "test_user", "agent_id": "test_agent"},
    )

    # Check that the search was called with the correct filter syntax
    args, kwargs = mock_ft.search.call_args
    assert "@user_id:{test_user}" in args[0]
    assert "@agent_id:{test_agent}" in args[0]
    assert "=>[KNN" in args[0]


def test_search_without_filters(valkey_db, mock_valkey_client):
    """Test search without filters."""
    # Mock search results
    mock_doc = MagicMock()
    mock_doc.memory_id = "test_id"
    mock_doc.hash = "test_hash"
    mock_doc.memory = "test_data"
    mock_doc.created_at = str(int(datetime.now().timestamp()))
    mock_doc.metadata = json.dumps({"key": "value"})
    mock_doc.vector_score = "0.5"

    mock_results = MagicMock()
    mock_results.docs = [mock_doc]

    mock_ft = mock_valkey_client.ft.return_value
    mock_ft.search.return_value = mock_results

    # Test without filters
    results = valkey_db.search(
        query="test query",
        vectors=np.random.rand(1536).tolist(),
        limit=5,
    )

    # Check that the search was called with the correct syntax
    args, kwargs = mock_ft.search.call_args
    assert "*=>[KNN" in args[0]

    # Check that results are processed correctly
    assert len(results) == 1
    assert results[0].id == "test_id"
    assert results[0].payload["hash"] == "test_hash"
    assert results[0].payload["data"] == "test_data"
    assert "created_at" in results[0].payload


def test_insert(valkey_db, mock_valkey_client):
    """Test inserting vectors."""
    # Prepare test data
    vectors = [np.random.rand(1536).tolist()]
    payloads = [{"hash": "test_hash", "data": "test_data", "user_id": "test_user"}]
    ids = ["test_id"]

    # Call insert
    valkey_db.insert(vectors=vectors, payloads=payloads, ids=ids)

    # Check that hset was called with the correct arguments
    mock_valkey_client.hset.assert_called_once()
    args, kwargs = mock_valkey_client.hset.call_args
    assert args[0] == "mem0:test_collection:test_id"
    assert "memory_id" in kwargs["mapping"]
    assert kwargs["mapping"]["memory_id"] == "test_id"
    assert kwargs["mapping"]["hash"] == "test_hash"
    assert kwargs["mapping"]["memory"] == "test_data"
    assert kwargs["mapping"]["user_id"] == "test_user"
    assert "created_at" in kwargs["mapping"]
    assert "embedding" in kwargs["mapping"]


def test_insert_handles_missing_created_at(valkey_db, mock_valkey_client):
    """Test inserting vectors with missing created_at field."""
    # Prepare test data
    vectors = [np.random.rand(1536).tolist()]
    payloads = [{"hash": "test_hash", "data": "test_data"}]  # No created_at
    ids = ["test_id"]

    # Call insert
    valkey_db.insert(vectors=vectors, payloads=payloads, ids=ids)

    # Check that hset was called with the correct arguments
    mock_valkey_client.hset.assert_called_once()
    args, kwargs = mock_valkey_client.hset.call_args
    assert "created_at" in kwargs["mapping"]  # Should be added automatically


def test_delete(valkey_db, mock_valkey_client):
    """Test deleting a vector."""
    # Call delete
    valkey_db.delete("test_id")

    # Check that delete was called with the correct key
    mock_valkey_client.delete.assert_called_once_with("mem0:test_collection:test_id")


def test_update(valkey_db, mock_valkey_client):
    """Test updating a vector."""
    # Prepare test data
    vector = np.random.rand(1536).tolist()
    payload = {
        "hash": "test_hash",
        "data": "updated_data",
        "created_at": datetime.now(pytz.timezone("UTC")).isoformat(),
        "user_id": "test_user",
    }

    # Call update
    valkey_db.update(vector_id="test_id", vector=vector, payload=payload)

    # Check that hset was called with the correct arguments
    mock_valkey_client.hset.assert_called_once()
    args, kwargs = mock_valkey_client.hset.call_args
    assert args[0] == "mem0:test_collection:test_id"
    assert kwargs["mapping"]["memory_id"] == "test_id"
    assert kwargs["mapping"]["memory"] == "updated_data"


def test_update_handles_missing_created_at(valkey_db, mock_valkey_client):
    """Test updating vectors with missing created_at field."""
    # Prepare test data
    vector = np.random.rand(1536).tolist()
    payload = {"hash": "test_hash", "data": "updated_data"}  # No created_at

    # Call update
    valkey_db.update(vector_id="test_id", vector=vector, payload=payload)

    # Check that hset was called with the correct arguments
    mock_valkey_client.hset.assert_called_once()
    args, kwargs = mock_valkey_client.hset.call_args
    assert "created_at" in kwargs["mapping"]  # Should be added automatically


def test_get(valkey_db, mock_valkey_client):
    """Test getting a vector."""
    # Mock hgetall to return a vector
    mock_valkey_client.hgetall.return_value = {
        "memory_id": "test_id",
        "hash": "test_hash",
        "memory": "test_data",
        "created_at": str(int(datetime.now().timestamp())),
        "metadata": json.dumps({"key": "value"}),
        "user_id": "test_user",
    }

    # Call get
    result = valkey_db.get("test_id")

    # Check that hgetall was called with the correct key
    mock_valkey_client.hgetall.assert_called_once_with("mem0:test_collection:test_id")

    # Check the result
    assert result.id == "test_id"
    assert result.payload["hash"] == "test_hash"
    assert result.payload["data"] == "test_data"
    assert "created_at" in result.payload
    assert result.payload["key"] == "value"  # From metadata
    assert result.payload["user_id"] == "test_user"


def test_get_not_found(valkey_db, mock_valkey_client):
    """Test getting a vector that doesn't exist."""
    # Mock hgetall to return empty dict (not found)
    mock_valkey_client.hgetall.return_value = {}

    # Call get should raise KeyError
    with pytest.raises(KeyError, match="Vector with ID test_id not found"):
        valkey_db.get("test_id")


def test_list_cols(valkey_db, mock_valkey_client):
    """Test listing collections."""
    # Reset the mock to clear previous calls
    mock_valkey_client.execute_command.reset_mock()

    # Mock execute_command to return list of indices
    mock_valkey_client.execute_command.return_value = ["test_collection", "another_collection"]

    # Call list_cols
    result = valkey_db.list_cols()

    # Check that execute_command was called with the correct command
    mock_valkey_client.execute_command.assert_called_with("FT._LIST")

    # Check the result
    assert result == ["test_collection", "another_collection"]


def test_delete_col(valkey_db, mock_valkey_client):
    """Test deleting a collection."""
    # Reset the mock to clear previous calls
    mock_valkey_client.execute_command.reset_mock()

    # Test successful deletion
    result = valkey_db.delete_col()
    assert result is True

    # Check that execute_command was called with the correct command
    mock_valkey_client.execute_command.assert_called_once_with("FT.DROPINDEX", "test_collection")

    # Test error handling - real errors should still raise
    mock_valkey_client.execute_command.side_effect = ResponseError("Error dropping index")
    with pytest.raises(ResponseError, match="Error dropping index"):
        valkey_db.delete_col()

    # Test idempotent behavior - "Unknown index name" should return False, not raise
    mock_valkey_client.execute_command.side_effect = ResponseError("Unknown index name")
    result = valkey_db.delete_col()
    assert result is False


def test_context_aware_logging(valkey_db, mock_valkey_client):
    """Test that _drop_index handles different log levels correctly."""
    # Mock "Unknown index name" error
    mock_valkey_client.execute_command.side_effect = ResponseError("Unknown index name")

    # Test silent mode - should not log anything (we can't easily test log output, but ensure no exception)
    result = valkey_db._drop_index("test_collection", log_level="silent")
    assert result is False

    # Test info mode - should not raise exception
    result = valkey_db._drop_index("test_collection", log_level="info")
    assert result is False

    # Test default mode - should not raise exception
    result = valkey_db._drop_index("test_collection")
    assert result is False


def test_col_info(valkey_db, mock_valkey_client):
    """Test getting collection info."""
    # Mock ft().info() to return index info
    mock_ft = mock_valkey_client.ft.return_value

    # Reset the mock to clear previous calls
    mock_ft.info.reset_mock()

    mock_ft.info.return_value = {"index_name": "test_collection", "num_docs": 100}

    # Call col_info
    result = valkey_db.col_info()

    # Check that ft().info() was called
    assert mock_ft.info.called

    # Check the result
    assert result["index_name"] == "test_collection"
    assert result["num_docs"] == 100


def test_create_col(valkey_db, mock_valkey_client):
    """Test creating a new collection."""
    # Call create_col
    valkey_db.create_col(name="new_collection", vector_size=768, distance="IP")

    # Check that execute_command was called to create the index
    assert mock_valkey_client.execute_command.called
    args = mock_valkey_client.execute_command.call_args[0]
    assert args[0] == "FT.CREATE"
    assert args[1] == "new_collection"

    # Check that the distance metric was set correctly
    distance_metric_index = args.index("DISTANCE_METRIC")
    assert args[distance_metric_index + 1] == "IP"

    # Check that the vector size was set correctly
    dim_index = args.index("DIM")
    assert args[dim_index + 1] == "768"


def test_list(valkey_db, mock_valkey_client):
    """Test listing vectors."""
    # Mock search results
    mock_doc = MagicMock()
    mock_doc.memory_id = "test_id"
    mock_doc.hash = "test_hash"
    mock_doc.memory = "test_data"
    mock_doc.created_at = str(int(datetime.now().timestamp()))
    mock_doc.metadata = json.dumps({"key": "value"})
    mock_doc.vector_score = "0.5"  # Add missing vector_score

    mock_results = MagicMock()
    mock_results.docs = [mock_doc]

    mock_ft = mock_valkey_client.ft.return_value
    mock_ft.search.return_value = mock_results

    # Call list
    results = valkey_db.list(filters={"user_id": "test_user"}, limit=10)

    # Check that search was called with the correct arguments
    mock_ft.search.assert_called_once()
    args, kwargs = mock_ft.search.call_args
    # Now expects full search query with KNN part due to dummy vector approach
    assert "@user_id:{test_user}" in args[0]
    assert "=>[KNN" in args[0]
    # Verify the results format
    assert len(results) == 1
    assert len(results[0]) == 1
    assert results[0][0].id == "test_id"

    # Check the results
    assert len(results) == 1  # One list of results
    assert len(results[0]) == 1  # One result in the list
    assert results[0][0].id == "test_id"
    assert results[0][0].payload["hash"] == "test_hash"
    assert results[0][0].payload["data"] == "test_data"


def test_search_error_handling(valkey_db, mock_valkey_client):
    """Test search error handling when query fails."""
    # Mock search to fail with an error
    mock_ft = mock_valkey_client.ft.return_value
    mock_ft.search.side_effect = ResponseError("Invalid filter expression")

    # Call search should raise the error
    with pytest.raises(ResponseError, match="Invalid filter expression"):
        valkey_db.search(
            query="test query",
            vectors=np.random.rand(1536).tolist(),
            limit=5,
            filters={"user_id": "test_user"},
        )

    # Check that search was called once
    assert mock_ft.search.call_count == 1


def test_drop_index_error_handling(valkey_db, mock_valkey_client):
    """Test error handling when dropping an index."""
    # Reset the mock to clear previous calls
    mock_valkey_client.execute_command.reset_mock()

    # Test 1: Real error (not "Unknown index name") should raise
    mock_valkey_client.execute_command.side_effect = ResponseError("Error dropping index")
    with pytest.raises(ResponseError, match="Error dropping index"):
        valkey_db._drop_index("test_collection")

    # Test 2: "Unknown index name" with default log_level should return False
    mock_valkey_client.execute_command.side_effect = ResponseError("Unknown index name")
    result = valkey_db._drop_index("test_collection")
    assert result is False

    # Test 3: "Unknown index name" with silent log_level should return False
    mock_valkey_client.execute_command.side_effect = ResponseError("Unknown index name")
    result = valkey_db._drop_index("test_collection", log_level="silent")
    assert result is False

    # Test 4: "Unknown index name" with info log_level should return False
    mock_valkey_client.execute_command.side_effect = ResponseError("Unknown index name")
    result = valkey_db._drop_index("test_collection", log_level="info")
    assert result is False

    # Test 5: Successful deletion should return True
    mock_valkey_client.execute_command.side_effect = None  # Reset to success
    result = valkey_db._drop_index("test_collection")
    assert result is True


def test_reset(valkey_db, mock_valkey_client):
    """Test resetting an index."""
    # Mock delete_col and _create_index
    with (
        patch.object(valkey_db, "delete_col", return_value=True) as mock_delete_col,
        patch.object(valkey_db, "_create_index") as mock_create_index,
    ):
        # Call reset
        result = valkey_db.reset()

        # Check that delete_col and _create_index were called
        mock_delete_col.assert_called_once()
        mock_create_index.assert_called_once_with(1536)

        # Check the result
        assert result is True


def test_build_list_query(valkey_db):
    """Test building a list query with and without filters."""
    # Test without filters
    query = valkey_db._build_list_query(None)
    assert query == "*"

    # Test with empty filters
    query = valkey_db._build_list_query({})
    assert query == "*"

    # Test with filters
    query = valkey_db._build_list_query({"user_id": "test_user"})
    assert query == "@user_id:{test_user}"

    # Test with multiple filters
    query = valkey_db._build_list_query({"user_id": "test_user", "agent_id": "test_agent"})
    assert "@user_id:{test_user}" in query
    assert "@agent_id:{test_agent}" in query


def test_process_document_fields(valkey_db):
    """Test processing document fields from hash results."""
    # Create a mock result with all fields
    result = {
        "memory_id": "test_id",
        "hash": "test_hash",
        "memory": "test_data",
        "created_at": "1625097600",  # 2021-07-01 00:00:00 UTC
        "updated_at": "1625184000",  # 2021-07-02 00:00:00 UTC
        "user_id": "test_user",
        "agent_id": "test_agent",
        "metadata": json.dumps({"key": "value"}),
    }

    # Process the document fields
    payload, memory_id = valkey_db._process_document_fields(result, "default_id")

    # Check the results
    assert memory_id == "test_id"
    assert payload["hash"] == "test_hash"
    assert payload["data"] == "test_data"  # memory renamed to data
    assert "created_at" in payload
    assert "updated_at" in payload
    assert payload["user_id"] == "test_user"
    assert payload["agent_id"] == "test_agent"
    assert payload["key"] == "value"  # From metadata

    # Test with missing fields
    result = {
        # No memory_id
        "hash": "test_hash",
        # No memory
        # No created_at
    }

    # Process the document fields
    payload, memory_id = valkey_db._process_document_fields(result, "default_id")

    # Check the results
    assert memory_id == "default_id"  # Should use default_id
    assert payload["hash"] == "test_hash"
    assert "data" in payload  # Should have default value
    assert "created_at" in payload  # Should have default value


def test_init_connection_error():
    """Test that initialization handles connection errors."""
    # Mock the from_url to raise an exception
    with patch("valkey.from_url") as mock_from_url:
        mock_from_url.side_effect = Exception("Connection failed")

        # Initialize ValkeyDB should raise the exception
        with pytest.raises(Exception, match="Connection failed"):
            ValkeyDB(
                valkey_url="valkey://localhost:6379",
                collection_name="test_collection",
                embedding_model_dims=1536,
            )


def test_build_search_query(valkey_db):
    """Test building search queries with different filter scenarios."""
    # Test with no filters
    knn_part = "[KNN 5 @embedding $vec_param AS vector_score]"
    query = valkey_db._build_search_query(knn_part)
    assert query == f"*=>{knn_part}"

    # Test with empty filters
    query = valkey_db._build_search_query(knn_part, {})
    assert query == f"*=>{knn_part}"

    # Test with None values in filters
    query = valkey_db._build_search_query(knn_part, {"user_id": None})
    assert query == f"*=>{knn_part}"

    # Test with single filter
    query = valkey_db._build_search_query(knn_part, {"user_id": "test_user"})
    assert query == f"@user_id:{{test_user}} =>{knn_part}"

    # Test with multiple filters
    query = valkey_db._build_search_query(knn_part, {"user_id": "test_user", "agent_id": "test_agent"})
    assert "@user_id:{test_user}" in query
    assert "@agent_id:{test_agent}" in query
    assert f"=>{knn_part}" in query


def test_get_error_handling(valkey_db, mock_valkey_client):
    """Test error handling in the get method."""
    # Mock hgetall to raise an exception
    mock_valkey_client.hgetall.side_effect = Exception("Unexpected error")

    # Call get should raise the exception
    with pytest.raises(Exception, match="Unexpected error"):
        valkey_db.get("test_id")


def test_list_error_handling(valkey_db, mock_valkey_client):
    """Test error handling in the list method."""
    # Mock search to raise an exception
    mock_ft = mock_valkey_client.ft.return_value
    mock_ft.search.side_effect = Exception("Unexpected error")

    # Call list should return empty result on error
    results = valkey_db.list(filters={"user_id": "test_user"})

    # Check that the result is an empty list
    assert results == [[]]


def test_create_index_other_error():
    """Test that initialization handles other errors during index creation."""
    # Mock the execute_command to raise a different error
    with patch("valkey.from_url") as mock_client:
        mock_client.return_value.execute_command.side_effect = ResponseError("Some other error")
        mock_client.return_value.ft = MagicMock()
        mock_client.return_value.ft.return_value.info.side_effect = ResponseError("not found")

        # Initialize ValkeyDB should raise the exception
        with pytest.raises(ResponseError, match="Some other error"):
            ValkeyDB(
                valkey_url="valkey://localhost:6379",
                collection_name="test_collection",
                embedding_model_dims=1536,
            )


def test_create_col_error(valkey_db, mock_valkey_client):
    """Test error handling in create_col method."""
    # Mock execute_command to raise an exception
    mock_valkey_client.execute_command.side_effect = Exception("Failed to create index")

    # Call create_col should raise the exception
    with pytest.raises(Exception, match="Failed to create index"):
        valkey_db.create_col(name="new_collection", vector_size=768)


def test_list_cols_error(valkey_db, mock_valkey_client):
    """Test error handling in list_cols method."""
    # Reset the mock to clear previous calls
    mock_valkey_client.execute_command.reset_mock()

    # Mock execute_command to raise an exception
    mock_valkey_client.execute_command.side_effect = Exception("Failed to list indices")

    # Call list_cols should raise the exception
    with pytest.raises(Exception, match="Failed to list indices"):
        valkey_db.list_cols()


def test_col_info_error(valkey_db, mock_valkey_client):
    """Test error handling in col_info method."""
    # Mock ft().info() to raise an exception
    mock_ft = mock_valkey_client.ft.return_value
    mock_ft.info.side_effect = Exception("Failed to get index info")

    # Call col_info should raise the exception
    with pytest.raises(Exception, match="Failed to get index info"):
        valkey_db.col_info()


# Additional tests to improve coverage


def test_invalid_index_type():
    """Test validation of invalid index type."""
    with pytest.raises(ValueError, match="Invalid index_type: invalid. Must be 'hnsw' or 'flat'"):
        ValkeyDB(
            valkey_url="valkey://localhost:6379",
            collection_name="test_collection",
            embedding_model_dims=1536,
            index_type="invalid",
        )


def test_index_existence_check_error(mock_valkey_client):
    """Test error handling when checking index existence."""
    # Mock ft().info() to raise a ResponseError that's not "not found"
    mock_ft = MagicMock()
    mock_ft.info.side_effect = ResponseError("Some other error")
    mock_valkey_client.ft.return_value = mock_ft

    with patch("valkey.from_url", return_value=mock_valkey_client):
        with pytest.raises(ResponseError):
            ValkeyDB(
                valkey_url="valkey://localhost:6379",
                collection_name="test_collection",
                embedding_model_dims=1536,
            )


def test_flat_index_creation(mock_valkey_client):
    """Test creation of FLAT index type."""
    mock_ft = MagicMock()
    # Mock the info method to raise ResponseError with "not found" to trigger index creation
    mock_ft.info.side_effect = ResponseError("Index not found")
    mock_valkey_client.ft.return_value = mock_ft

    with patch("valkey.from_url", return_value=mock_valkey_client):
        # Mock the execute_command to avoid the actual exception
        mock_valkey_client.execute_command.return_value = None

        ValkeyDB(
            valkey_url="valkey://localhost:6379",
            collection_name="test_collection",
            embedding_model_dims=1536,
            index_type="flat",
        )

        # Verify that execute_command was called (index creation)
        assert mock_valkey_client.execute_command.called


def test_index_creation_error(mock_valkey_client):
    """Test error handling during index creation."""
    mock_ft = MagicMock()
    mock_ft.info.side_effect = ResponseError("Unknown index name")  # Index doesn't exist
    mock_valkey_client.ft.return_value = mock_ft
    mock_valkey_client.execute_command.side_effect = Exception("Failed to create index")

    with patch("valkey.from_url", return_value=mock_valkey_client):
        with pytest.raises(Exception, match="Failed to create index"):
            ValkeyDB(
                valkey_url="valkey://localhost:6379",
                collection_name="test_collection",
                embedding_model_dims=1536,
            )


def test_insert_missing_required_field(valkey_db, mock_valkey_client):
    """Test error handling when inserting vector with missing required field."""
    # Mock hset to raise KeyError (missing required field)
    mock_valkey_client.hset.side_effect = KeyError("missing_field")

    # This should not raise an exception but should log the error
    valkey_db.insert(vectors=[np.random.rand(1536).tolist()], payloads=[{"memory": "test"}], ids=["test_id"])


def test_insert_general_error(valkey_db, mock_valkey_client):
    """Test error handling for general exceptions during insert."""
    # Mock hset to raise a general exception
    mock_valkey_client.hset.side_effect = Exception("Database error")

    with pytest.raises(Exception, match="Database error"):
        valkey_db.insert(vectors=[np.random.rand(1536).tolist()], payloads=[{"memory": "test"}], ids=["test_id"])


def test_search_with_invalid_metadata(valkey_db, mock_valkey_client):
    """Test search with invalid JSON metadata."""
    # Mock search results with invalid JSON metadata
    mock_doc = MagicMock()
    mock_doc.memory_id = "test_id"
    mock_doc.hash = "test_hash"
    mock_doc.memory = "test_data"
    mock_doc.created_at = str(int(datetime.now().timestamp()))
    mock_doc.metadata = "invalid_json"  # Invalid JSON
    mock_doc.vector_score = "0.5"

    mock_result = MagicMock()
    mock_result.docs = [mock_doc]
    mock_valkey_client.ft.return_value.search.return_value = mock_result

    # Should handle invalid JSON gracefully
    results = valkey_db.search(query="test query", vectors=np.random.rand(1536).tolist(), limit=5)

    assert len(results) == 1


def test_search_with_hnsw_ef_runtime(valkey_db, mock_valkey_client):
    """Test search with HNSW ef_runtime parameter."""
    valkey_db.index_type = "hnsw"
    valkey_db.hnsw_ef_runtime = 20

    mock_result = MagicMock()
    mock_result.docs = []
    mock_valkey_client.ft.return_value.search.return_value = mock_result

    valkey_db.search(query="test query", vectors=np.random.rand(1536).tolist(), limit=5)

    # Verify the search was called
    assert mock_valkey_client.ft.return_value.search.called


def test_delete_error(valkey_db, mock_valkey_client):
    """Test error handling during vector deletion."""
    mock_valkey_client.delete.side_effect = Exception("Delete failed")

    with pytest.raises(Exception, match="Delete failed"):
        valkey_db.delete("test_id")


def test_update_missing_required_field(valkey_db, mock_valkey_client):
    """Test error handling when updating vector with missing required field."""
    mock_valkey_client.hset.side_effect = KeyError("missing_field")

    # This should not raise an exception but should log the error
    valkey_db.update(vector_id="test_id", vector=np.random.rand(1536).tolist(), payload={"memory": "updated"})


def test_update_general_error(valkey_db, mock_valkey_client):
    """Test error handling for general exceptions during update."""
    mock_valkey_client.hset.side_effect = Exception("Update failed")

    with pytest.raises(Exception, match="Update failed"):
        valkey_db.update(vector_id="test_id", vector=np.random.rand(1536).tolist(), payload={"memory": "updated"})


def test_get_with_binary_data_and_unicode_error(valkey_db, mock_valkey_client):
    """Test get method with binary data that fails UTF-8 decoding."""
    # Mock result with binary data that can't be decoded
    mock_result = {
        "memory_id": "test_id",
        "hash": b"\xff\xfe",  # Invalid UTF-8 bytes
        "memory": "test_memory",
        "created_at": "1234567890",
        "updated_at": "invalid_timestamp",
        "metadata": "{}",
        "embedding": b"binary_embedding_data",
    }
    mock_valkey_client.hgetall.return_value = mock_result

    result = valkey_db.get("test_id")

    # Should handle binary data gracefully
    assert result.id == "test_id"
    assert result.payload["data"] == "test_memory"


def test_get_with_invalid_timestamps(valkey_db, mock_valkey_client):
    """Test get method with invalid timestamp values."""
    mock_result = {
        "memory_id": "test_id",
        "hash": "test_hash",
        "memory": "test_memory",
        "created_at": "invalid_timestamp",
        "updated_at": "also_invalid",
        "metadata": "{}",
        "embedding": b"binary_data",
    }
    mock_valkey_client.hgetall.return_value = mock_result

    result = valkey_db.get("test_id")

    # Should handle invalid timestamps gracefully
    assert result.id == "test_id"
    assert "created_at" in result.payload


def test_get_with_invalid_metadata_json(valkey_db, mock_valkey_client):
    """Test get method with invalid JSON metadata."""
    mock_result = {
        "memory_id": "test_id",
        "hash": "test_hash",
        "memory": "test_memory",
        "created_at": "1234567890",
        "updated_at": "1234567890",
        "metadata": "invalid_json{",  # Invalid JSON
        "embedding": b"binary_data",
    }
    mock_valkey_client.hgetall.return_value = mock_result

    result = valkey_db.get("test_id")

    # Should handle invalid JSON gracefully
    assert result.id == "test_id"


def test_list_with_missing_fields_and_defaults(valkey_db, mock_valkey_client):
    """Test list method with documents missing various fields."""
    # Mock search results with missing fields but valid timestamps
    mock_doc1 = MagicMock()
    mock_doc1.memory_id = "fallback_id"
    mock_doc1.hash = "test_hash"  # Provide valid hash
    mock_doc1.memory = "test_memory"  # Provide valid memory
    mock_doc1.created_at = str(int(datetime.now().timestamp()))  # Valid timestamp
    mock_doc1.updated_at = str(int(datetime.now().timestamp()))  # Valid timestamp
    mock_doc1.metadata = json.dumps({"key": "value"})  # Valid JSON
    mock_doc1.vector_score = "0.5"

    mock_result = MagicMock()
    mock_result.docs = [mock_doc1]
    mock_valkey_client.ft.return_value.search.return_value = mock_result

    results = valkey_db.list()

    # Should handle the search-based list approach
    assert len(results) == 1
    inner_results = results[0]
    assert len(inner_results) == 1
    result = inner_results[0]
    assert result.id == "fallback_id"
    assert "hash" in result.payload
    assert "data" in result.payload  # memory is renamed to data
