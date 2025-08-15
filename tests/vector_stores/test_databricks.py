import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import pytz

from mem0.vector_stores.databricks import DatabricksDB


@pytest.fixture
def mock_databricks_client():
    """Create a mock Databricks Vector Search client."""
    with patch("databricks.vector_search.client.VectorSearchClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock index object
        mock_index = MagicMock()
        mock_client.get_index.return_value = mock_index
        mock_client.create_delta_sync_index.return_value = mock_index
        
        # Mock endpoint methods
        mock_client.get_endpoint.return_value = MagicMock()
        mock_client.create_endpoint.return_value = MagicMock()
        
        # Mock other methods
        mock_client.list_indexes.return_value = {"vector_indexes": []}
        mock_client.delete_index.return_value = MagicMock()
        
        yield mock_client


@pytest.fixture
def databricks_db(mock_databricks_client):
    """Create a DatabricksDB instance with a mock client."""
    # Mock the endpoint and index existence checks
    mock_databricks_client.get_endpoint.return_value = MagicMock()
    mock_databricks_client.get_index.return_value = MagicMock()
    
    databricks_db = DatabricksDB(
        workspace_url="https://test.databricks.com",
        access_token="test_token",
        endpoint_name="test_endpoint",
        index_name="test_catalog.test_schema.test_index",
        source_table_name="test_catalog.test_schema.test_table",
        embedding_dimension=1536,
    )
    
    # Replace the client with our mock
    databricks_db.client = mock_databricks_client
    return databricks_db


def test_init_with_access_token(mock_databricks_client):
    """Test initialization with personal access token."""
    mock_databricks_client.get_endpoint.return_value = MagicMock()
    mock_databricks_client.get_index.return_value = MagicMock()
    
    db = DatabricksDB(
        workspace_url="https://test.databricks.com",
        access_token="test_token",
        endpoint_name="test_endpoint",
        index_name="test_index",
        source_table_name="test_table",
    )
    
    assert db.workspace_url == "https://test.databricks.com"
    assert db.endpoint_name == "test_endpoint"
    assert db.index_name == "test_index"


def test_init_with_service_principal(mock_databricks_client):
    """Test initialization with service principal credentials."""
    mock_databricks_client.get_endpoint.return_value = MagicMock()
    mock_databricks_client.get_index.return_value = MagicMock()
    
    db = DatabricksDB(
        workspace_url="https://test.databricks.com",
        service_principal_client_id="test_client_id",
        service_principal_client_secret="test_client_secret",
        endpoint_name="test_endpoint",
        index_name="test_index",
        source_table_name="test_table",
    )
    
    assert db.workspace_url == "https://test.databricks.com"
    assert db.endpoint_name == "test_endpoint"
    assert db.index_name == "test_index"


def test_endpoint_creation_when_not_exists(mock_databricks_client):
    """Test endpoint creation when it doesn't exist."""
    # Mock endpoint not existing initially
    mock_databricks_client.get_endpoint.side_effect = [Exception("Not found"), MagicMock()]
    mock_databricks_client.get_index.return_value = MagicMock()
    
    DatabricksDB(
        workspace_url="https://test.databricks.com",
        access_token="test_token",
        endpoint_name="test_endpoint",
        index_name="test_index",
        source_table_name="test_table",
    )
    
    # Check that create_endpoint was called
    mock_databricks_client.create_endpoint.assert_called_once_with(
        name="test_endpoint",
        endpoint_type="STANDARD"
    )


def test_index_creation_when_not_exists(mock_databricks_client):
    """Test index creation when it doesn't exist."""
    # Mock index not existing initially
    mock_databricks_client.get_endpoint.return_value = MagicMock()
    mock_databricks_client.get_index.side_effect = [Exception("Not found"), MagicMock()]
    
    DatabricksDB(
        workspace_url="https://test.databricks.com",
        access_token="test_token",
        endpoint_name="test_endpoint",
        index_name="test_index",
        source_table_name="test_table",
        embedding_dimension=768,
    )
    
    # Check that create_delta_sync_index was called
    mock_databricks_client.create_delta_sync_index.assert_called_once()


def test_create_col(databricks_db, mock_databricks_client):
    """Test creating a new collection (index)."""
    # Mock index creation
    mock_new_index = MagicMock()
    mock_databricks_client.create_delta_sync_index.return_value = mock_new_index
    
    # Call create_col
    result = databricks_db.create_col(name="new_index", vector_size=768)
    
    # Check that create_delta_sync_index was called
    mock_databricks_client.create_delta_sync_index.assert_called()
    assert result == mock_new_index
    assert databricks_db.index_name == "new_index"


def test_search_with_text_query(databricks_db, mock_databricks_client):
    """Test search with text query."""
    # Set up for text-based search
    databricks_db.embedding_source_column = "text"
    
    # Mock search results
    mock_results = {
        "result": {
            "data_array": [
                {
                    "memory_id": "test_id",
                    "hash": "test_hash",
                    "memory": "test_data",
                    "created_at": 1234567890,
                    "metadata": json.dumps({"key": "value"}),
                    "score": 0.95
                }
            ]
        }
    }
    
    mock_index = databricks_db.index
    mock_index.similarity_search.return_value = mock_results
    
    # Call search
    results = databricks_db.search(
        query="test query",
        vectors=[],  # Not used for text search
        limit=5,
        filters={"user_id": "test_user"}
    )
    
    # Check that similarity_search was called with correct parameters
    mock_index.similarity_search.assert_called_once()
    args, kwargs = mock_index.similarity_search.call_args
    assert "query_text" in kwargs
    assert kwargs["query_text"] == "test query"
    assert kwargs["num_results"] == 5
    assert "filters" in kwargs
    
    # Check results
    assert len(results) == 1
    assert results[0].id == "test_id"
    assert results[0].payload["hash"] == "test_hash"
    assert results[0].payload["data"] == "test_data"
    assert results[0].payload["key"] == "value"  # From metadata
    assert results[0].score == 0.95


def test_search_with_vector_query(databricks_db, mock_databricks_client):
    """Test search with vector query."""
    # Mock search results
    mock_results = {
        "result": {
            "data_array": [
                {
                    "memory_id": "test_id",
                    "hash": "test_hash",
                    "memory": "test_data",
                    "created_at": 1234567890,
                    "score": 0.85
                }
            ]
        }
    }
    
    mock_index = databricks_db.index
    mock_index.similarity_search.return_value = mock_results
    
    # Call search with vector
    test_vector = [0.1, 0.2, 0.3] * 512  # 1536 dimensions
    results = databricks_db.search(
        query="",
        vectors=test_vector,
        limit=3
    )
    
    # Check that similarity_search was called with vector
    mock_index.similarity_search.assert_called_once()
    args, kwargs = mock_index.similarity_search.call_args
    assert "query_vector" in kwargs
    assert kwargs["query_vector"] == test_vector
    assert kwargs["num_results"] == 3
    
    # Check results
    assert len(results) == 1
    assert results[0].id == "test_id"
    assert results[0].score == 0.85


def test_search_with_storage_optimized_filters(databricks_db, mock_databricks_client):
    """Test search with storage-optimized endpoint filters."""
    # Set endpoint type to storage-optimized
    databricks_db.endpoint_type = "STORAGE_OPTIMIZED"
    
    # Mock search results
    mock_results = {"result": {"data_array": []}}
    mock_index = databricks_db.index
    mock_index.similarity_search.return_value = mock_results
    
    # Call search with filters
    databricks_db.search(
        query="test",
        vectors=[],
        filters={"user_id": "test_user", "agent_id": "test_agent"}
    )
    
    # Check that filters were converted to SQL-like format
    mock_index.similarity_search.assert_called_once()
    args, kwargs = mock_index.similarity_search.call_args
    assert "filters" in kwargs
    filter_str = kwargs["filters"]
    assert "user_id = 'test_user'" in filter_str
    assert "agent_id = 'test_agent'" in filter_str
    assert " AND " in filter_str


def test_get(databricks_db, mock_databricks_client):
    """Test getting a vector by ID."""
    # Mock search results for get operation
    mock_results = {
        "result": {
            "data_array": [
                {
                    "id": "test_id",
                    "memory_id": "test_id",
                    "hash": "test_hash",
                    "memory": "test_data",
                    "created_at": 1234567890,
                    "updated_at": 1234567900,
                    "metadata": json.dumps({"key": "value"}),
                    "user_id": "test_user"
                }
            ]
        }
    }
    
    mock_index = databricks_db.index
    mock_index.similarity_search.return_value = mock_results
    
    # Call get
    result = databricks_db.get("test_id")
    
    # Check that similarity_search was called with ID filter
    mock_index.similarity_search.assert_called_once()
    args, kwargs = mock_index.similarity_search.call_args
    assert kwargs["num_results"] == 1
    assert "filters" in kwargs
    
    # Check result
    assert result.id == "test_id"
    assert result.payload["hash"] == "test_hash"
    assert result.payload["data"] == "test_data"
    assert result.payload["user_id"] == "test_user"
    assert result.payload["key"] == "value"  # From metadata


def test_get_not_found(databricks_db, mock_databricks_client):
    """Test getting a vector that doesn't exist."""
    # Mock empty search results
    mock_results = {"result": {"data_array": []}}
    mock_index = databricks_db.index
    mock_index.similarity_search.return_value = mock_results
    
    # Call get should raise KeyError
    with pytest.raises(KeyError, match="Vector with ID test_id not found"):
        databricks_db.get("test_id")


def test_list_cols(databricks_db, mock_databricks_client):
    """Test listing collections (indexes)."""
    # Mock list_indexes response
    mock_databricks_client.list_indexes.return_value = {
        "vector_indexes": [
            {"name": "index1"},
            {"name": "index2"}
        ]
    }
    
    # Call list_cols
    result = databricks_db.list_cols()
    
    # Check that list_indexes was called
    mock_databricks_client.list_indexes.assert_called_once_with(endpoint_name="test_endpoint")
    
    # Check result
    assert result == ["index1", "index2"]


def test_delete_col(databricks_db, mock_databricks_client):
    """Test deleting a collection (index)."""
    # Call delete_col
    databricks_db.delete_col()
    
    # Check that delete_index was called
    mock_databricks_client.delete_index.assert_called_once_with("test_catalog.test_schema.test_index")


def test_col_info(databricks_db, mock_databricks_client):
    """Test getting collection info."""
    # Mock index description
    mock_index = MagicMock()
    mock_index.describe.return_value = {"index_type": "DELTA_SYNC", "status": "READY"}
    mock_databricks_client.get_index.return_value = mock_index
    
    # Call col_info
    result = databricks_db.col_info()
    
    # Check that get_index and describe were called
    mock_databricks_client.get_index.assert_called_with("test_catalog.test_schema.test_index")
    mock_index.describe.assert_called_once()
    
    # Check result
    assert result["index_type"] == "DELTA_SYNC"
    assert result["status"] == "READY"


def test_list(databricks_db, mock_databricks_client):
    """Test listing memories."""
    # Mock search results
    mock_results = {
        "result": {
            "data_array": [
                {
                    "memory_id": "id1",
                    "hash": "hash1",
                    "memory": "data1",
                    "created_at": 1234567890,
                    "metadata": json.dumps({"type": "memory1"})
                },
                {
                    "memory_id": "id2", 
                    "hash": "hash2",
                    "memory": "data2",
                    "created_at": 1234567891,
                    "metadata": json.dumps({"type": "memory2"})
                }
            ]
        }
    }
    
    mock_index = databricks_db.index
    mock_index.similarity_search.return_value = mock_results
    
    # Call list
    results = databricks_db.list(filters={"user_id": "test_user"}, limit=10)
    
    # Check that similarity_search was called
    mock_index.similarity_search.assert_called_once()
    args, kwargs = mock_index.similarity_search.call_args
    assert kwargs["num_results"] == 10
    assert "filters" in kwargs
    
    # Check results format (nested list)
    assert len(results) == 1
    assert len(results[0]) == 2
    assert results[0][0].id == "id1"
    assert results[0][0].payload["data"] == "data1"
    assert results[0][0].payload["type"] == "memory1"
    assert results[0][1].id == "id2"
    assert results[0][1].payload["data"] == "data2"
    assert results[0][1].payload["type"] == "memory2"


def test_reset(databricks_db, mock_databricks_client):
    """Test resetting an index."""
    # Mock the methods called during reset
    with patch.object(databricks_db, "delete_col") as mock_delete, \
         patch.object(databricks_db, "_ensure_index_exists") as mock_ensure:
        
        # Call reset
        databricks_db.reset()
        
        # Check that delete_col and _ensure_index_exists were called
        mock_delete.assert_called_once()
        mock_ensure.assert_called_once()


def test_insert_warning(databricks_db, caplog):
    """Test that insert logs a warning for Delta Sync Index."""
    # Call insert (should log warning)
    databricks_db.insert(vectors=[[0.1, 0.2]], payloads=[{"data": "test"}], ids=["test_id"])
    
    # Check that warning was logged
    assert "Direct vector insertion not supported with Delta Sync Index" in caplog.text


def test_delete_warning(databricks_db, caplog):
    """Test that delete logs a warning for Delta Sync Index."""
    # Call delete (should log warning)
    databricks_db.delete("test_id")
    
    # Check that warning was logged
    assert "Direct vector deletion not supported with Delta Sync Index" in caplog.text


def test_update_warning(databricks_db, caplog):
    """Test that update logs a warning for Delta Sync Index."""
    # Call update (should log warning)
    databricks_db.update(vector_id="test_id", vector=[0.1, 0.2], payload={"data": "test"})
    
    # Check that warning was logged
    assert "Direct vector update not supported with Delta Sync Index" in caplog.text


def test_format_timestamp(databricks_db):
    """Test timestamp formatting."""
    # Test with unix timestamp
    formatted = databricks_db._format_timestamp(1234567890)
    assert "2009-02-13" in formatted
    
    # Test with string timestamp
    formatted = databricks_db._format_timestamp("1234567890")
    assert "2009-02-13" in formatted
    
    # Test with ISO string
    iso_string = "2023-01-01T12:00:00Z"
    formatted = databricks_db._format_timestamp(iso_string)
    assert "2023-01-01" in formatted
    
    # Test with None (should return current time)
    formatted = databricks_db._format_timestamp(None)
    assert len(formatted) > 0
    
    # Test with invalid input (should return current time)
    formatted = databricks_db._format_timestamp("invalid")
    assert len(formatted) > 0


def test_search_error_handling(databricks_db, mock_databricks_client):
    """Test search error handling."""
    # Mock similarity_search to raise an exception
    mock_index = databricks_db.index
    mock_index.similarity_search.side_effect = Exception("Search failed")
    
    # Call search should raise the exception
    with pytest.raises(Exception, match="Search failed"):
        databricks_db.search(query="test", vectors=[0.1, 0.2], limit=5)


def test_list_error_handling(databricks_db, mock_databricks_client):
    """Test list error handling."""
    # Mock similarity_search to raise an exception
    mock_index = databricks_db.index
    mock_index.similarity_search.side_effect = Exception("List failed")
    
    # Call list should return empty nested list on error
    results = databricks_db.list()
    assert results == [[]]


def test_search_with_invalid_metadata(databricks_db, mock_databricks_client):
    """Test search with invalid JSON metadata."""
    # Mock search results with invalid metadata
    mock_results = {
        "result": {
            "data_array": [
                {
                    "memory_id": "test_id",
                    "hash": "test_hash",
                    "memory": "test_data",
                    "created_at": 1234567890,
                    "metadata": "invalid_json{",  # Invalid JSON
                    "score": 0.95
                }
            ]
        }
    }
    
    mock_index = databricks_db.index
    mock_index.similarity_search.return_value = mock_results
    
    # Should handle invalid JSON gracefully
    results = databricks_db.search(query="test", vectors=[], limit=5)
    
    assert len(results) == 1
    assert results[0].id == "test_id"
    # Metadata should not be added due to JSON error


def test_create_index_with_embedding_model(mock_databricks_client):
    """Test index creation with Databricks-computed embeddings."""
    mock_databricks_client.get_endpoint.return_value = MagicMock()
    mock_databricks_client.get_index.side_effect = Exception("Not found")
    
    db = DatabricksDB(
        workspace_url="https://test.databricks.com",
        access_token="test_token",
        endpoint_name="test_endpoint",
        index_name="test_index",
        source_table_name="test_table",
        embedding_source_column="text",
        embedding_model_endpoint_name="e5-small-v2"
    )
    
    # Check that create_delta_sync_index was called with embedding model
    mock_databricks_client.create_delta_sync_index.assert_called_once()
    args, kwargs = mock_databricks_client.create_delta_sync_index.call_args
    assert "embedding_source_column" in kwargs
    assert "embedding_model_endpoint_name" in kwargs
    assert kwargs["embedding_source_column"] == "text"
    assert kwargs["embedding_model_endpoint_name"] == "e5-small-v2"


def test_create_index_with_self_managed_embeddings(mock_databricks_client):
    """Test index creation with self-managed embeddings."""
    mock_databricks_client.get_endpoint.return_value = MagicMock()
    mock_databricks_client.get_index.side_effect = Exception("Not found")
    
    db = DatabricksDB(
        workspace_url="https://test.databricks.com",
        access_token="test_token",
        endpoint_name="test_endpoint",
        index_name="test_index",
        source_table_name="test_table",
        embedding_dimension=768
    )
    
    # Check that create_delta_sync_index was called with self-managed settings
    mock_databricks_client.create_delta_sync_index.assert_called_once()
    args, kwargs = mock_databricks_client.create_delta_sync_index.call_args
    assert "embedding_dimension" in kwargs
    assert "embedding_vector_column" in kwargs
    assert kwargs["embedding_dimension"] == 768
    assert kwargs["embedding_vector_column"] == "embedding"


def test_storage_optimized_endpoint_type(mock_databricks_client):
    """Test creation with storage-optimized endpoint type."""
    mock_databricks_client.get_endpoint.side_effect = Exception("Not found")
    mock_databricks_client.get_index.return_value = MagicMock()
    
    db = DatabricksDB(
        workspace_url="https://test.databricks.com",
        access_token="test_token",
        endpoint_name="test_endpoint",
        index_name="test_index",
        source_table_name="test_table",
        endpoint_type="STORAGE_OPTIMIZED"
    )
    
    # Check that endpoint was created with correct type
    mock_databricks_client.create_endpoint.assert_called_once_with(
        name="test_endpoint",
        endpoint_type="STORAGE_OPTIMIZED"
    )
    
    assert db.endpoint_type == "STORAGE_OPTIMIZED"


def test_client_initialization_error():
    """Test error handling during client initialization."""
    with patch("databricks.vector_search.client.VectorSearchClient") as mock_client_class:
        mock_client_class.side_effect = Exception("Failed to initialize client")
        
        with pytest.raises(Exception, match="Failed to initialize client"):
            DatabricksDB(
                workspace_url="https://test.databricks.com",
                access_token="test_token",
                endpoint_name="test_endpoint",
                index_name="test_index",
                source_table_name="test_table"
            )
