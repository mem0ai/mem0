import json
import pytest
from unittest.mock import MagicMock, patch
from mem0.vector_stores.databricks import Databricks


@pytest.fixture
def mock_workspace_client():
    """Create a mock WorkspaceClient."""
    with patch("mem0.vector_stores.databricks.WorkspaceClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        # Mock vector search endpoints
        mock_client.vector_search_endpoints.get_endpoint.return_value = MagicMock()
        mock_client.vector_search_endpoints.create_endpoint_and_wait.return_value = MagicMock()

        # Mock vector search indexes
        mock_client.vector_search_indexes.create_index.return_value = MagicMock()
        mock_client.vector_search_indexes.get_index.return_value = MagicMock()
        mock_client.vector_search_indexes.list_indexes.return_value = []
        mock_client.vector_search_indexes.delete_index.return_value = MagicMock()
        mock_client.vector_search_indexes.query_index.return_value = MagicMock()

        # Mock tables
        mock_client.tables.get.return_value = MagicMock()

        # Mock statement execution
        mock_response = MagicMock()
        mock_response.status.state = "SUCCEEDED"
        mock_client.statement_execution.execute_statement.return_value = mock_response

        yield mock_client


@pytest.fixture
def databricks_db(mock_workspace_client):
    """Create a Databricks instance with a mock client."""
    with patch('mem0.vector_stores.databricks.WorkspaceClient') as mock_client_class:
        mock_client_class.return_value = mock_workspace_client
        
        # Mock that index already exists to skip creation during init
        mock_workspace_client.vector_search_indexes.list_indexes.return_value = [
            MagicMock(name="test_catalog.test_schema.test_index")
        ]
        
        # Patch the Databricks class methods to prevent real initialization calls
        with patch.object(Databricks, 'list_cols', return_value=["test_catalog.test_schema.test_index"]):
            databricks_db = Databricks(
                workspace_url="https://test.databricks.com",
                access_token="test_token",
                endpoint_name="test_endpoint",
                index_name="test_catalog.test_schema.test_index",
                source_table_name="test_catalog.test_schema.test_table",
                embedding_dimension=1536,
            )
        
        # Replace the client with our mock
        databricks_db.client = mock_workspace_client
        return databricks_db
def test_init_with_access_token(mock_workspace_client):
    """Test initialization with personal access token."""
    with patch("mem0.vector_stores.databricks.WorkspaceClient") as mock_client_class:
        mock_client_class.return_value = mock_workspace_client

        # Mock that index already exists to skip creation during init
        mock_workspace_client.vector_search_indexes.list_indexes.return_value = [MagicMock(name="test_index")]

        db = Databricks(
            workspace_url="https://test.databricks.com",
            access_token="test_token",
            endpoint_name="test_endpoint",
            index_name="test_index",
            source_table_name="test_table",
        )

        assert db.workspace_url == "https://test.databricks.com"
        assert db.endpoint_name == "test_endpoint"
        assert db.index_name == "test_index"


def test_init_with_service_principal(mock_workspace_client):
    """Test initialization with service principal credentials."""
    with patch("mem0.vector_stores.databricks.WorkspaceClient") as mock_client_class:
        mock_client_class.return_value = mock_workspace_client

        # Mock that index already exists to skip creation during init
        mock_workspace_client.vector_search_indexes.list_indexes.return_value = [MagicMock(name="test_index")]

        db = Databricks(
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


def test_endpoint_creation_when_not_exists(mock_workspace_client):
    """Test endpoint creation when it doesn't exist."""
    # Mock endpoint not existing initially
    mock_workspace_client.vector_search_endpoints.get_endpoint.side_effect = [Exception("Not found"), MagicMock()]

    # Mock that index already exists to skip creation during init
    mock_workspace_client.vector_search_indexes.list_indexes.return_value = [MagicMock(name="test_index")]

    with patch("mem0.vector_stores.databricks.WorkspaceClient") as mock_client_class:
        mock_client_class.return_value = mock_workspace_client

        Databricks(
            workspace_url="https://test.databricks.com",
            access_token="test_token",
            endpoint_name="test_endpoint",
            index_name="test_index",
            source_table_name="test_table",
        )

        # Check that create_endpoint_and_wait was called
        mock_workspace_client.vector_search_endpoints.create_endpoint_and_wait.assert_called_once()


def test_index_creation_when_not_exists(mock_workspace_client):
    """Test index creation when it doesn't exist."""
    # Mock index not existing initially (empty list from list_indexes)
    mock_workspace_client.vector_search_endpoints.get_endpoint.return_value = MagicMock()
    mock_workspace_client.vector_search_indexes.list_indexes.return_value = []
    mock_workspace_client.tables.get.return_value = MagicMock()  # Table exists

    with patch("mem0.vector_stores.databricks.WorkspaceClient") as mock_client_class:
        mock_client_class.return_value = mock_workspace_client

        # Mock that create_col doesn't fail by patching the problematic SDK call
        with patch.object(Databricks, "create_col") as mock_create_col:
            Databricks(
                workspace_url="https://test.databricks.com",
                access_token="test_token",
                endpoint_name="test_endpoint",
                index_name="test_index",
                source_table_name="test_table",
                embedding_dimension=768,
            )

            # Check that create_col was called
            mock_create_col.assert_called_once()


def test_create_col(databricks_db, mock_workspace_client):
    """Test creating a new collection (index)."""
    # Mock table exists
    mock_workspace_client.tables.get.return_value = MagicMock()

    # Mock index creation
    mock_new_index = MagicMock()
    mock_workspace_client.vector_search_indexes.create_index.return_value = mock_new_index

    # Call create_col
    databricks_db.create_col(name="new_index", vector_size=768)

    # Check that create_index was called
    mock_workspace_client.vector_search_indexes.create_index.assert_called()
    assert databricks_db.index_name == "test_catalog.test_schema.test_index"  # Should remain unchanged


def test_search_with_text_query(databricks_db, mock_workspace_client):
    """Test search with text query."""
    # Set up for text-based search
    databricks_db.embedding_source_column = "text"
    databricks_db.embedding_model_endpoint_name = "e5-small-v2"

    # Mock search results
    mock_result_data = MagicMock()
    mock_result_data.data_array = [
        {
            "id": "test_id",
            "hash": "test_hash",
            "memory": "test_data",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "metadata": json.dumps({"key": "value"}),
            "agent_id": "agent1",
            "run_id": "run1",
            "user_id": "user1",
        }
    ]

    mock_results = MagicMock()
    mock_results.result = mock_result_data
    mock_workspace_client.vector_search_indexes.query_index.return_value = mock_results

    # Call search
    results = databricks_db.search(
        query="test query",
        vectors=[],  # Not used for text search
        limit=5,
        filters={"user_id": "test_user"},
    )

    # Check that query_index was called with correct parameters
    mock_workspace_client.vector_search_indexes.query_index.assert_called_once()
    _, kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args
    assert kwargs["query_text"] == "test query"
    assert kwargs["num_results"] == 5
    assert "filters_json" in kwargs

    # Check results
    assert len(results) == 1
    # Results should contain MemoryResult objects with proper structure


def test_search_with_vector_query(databricks_db, mock_workspace_client):
    """Test search with vector query."""
    # Mock search results
    mock_result_data = MagicMock()
    mock_result_data.data_array = [
        {
            "id": "test_id",
            "hash": "test_hash",
            "memory": "test_data",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "metadata": json.dumps({}),
            "agent_id": "",
            "run_id": "",
            "user_id": "",
        }
    ]

    mock_results = MagicMock()
    mock_results.result = mock_result_data
    mock_workspace_client.vector_search_indexes.query_index.return_value = mock_results

    # Call search with vector
    test_vector = [0.1, 0.2, 0.3] * 512  # 1536 dimensions
    databricks_db.search(query="", vectors=test_vector, limit=3)

    # Check that query_index was called with vector
    mock_workspace_client.vector_search_indexes.query_index.assert_called_once()
    _, kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args
    assert kwargs["query_vector"] == test_vector
    assert kwargs["num_results"] == 3


def test_get(databricks_db, mock_workspace_client):
    """Test getting a vector by ID."""
    # Mock search results for get operation
    mock_result_data = MagicMock()
    mock_result_data.data_array = [
        {
            "id": "test_id",
            "hash": "test_hash",
            "memory": "test_data",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "metadata": json.dumps({"key": "value"}),
            "user_id": "test_user",
            "agent_id": "test_agent",
            "run_id": "test_run",
        }
    ]

    mock_results = MagicMock()
    mock_results.result = mock_result_data
    mock_workspace_client.vector_search_indexes.query_index.return_value = mock_results

    # Call get
    result = databricks_db.get("test_id")

    # Check that query_index was called with ID filter
    mock_workspace_client.vector_search_indexes.query_index.assert_called_once()
    _, kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args
    assert kwargs["num_results"] == 1
    assert "filters_json" in kwargs

    # Check result
    assert result.id == "test_id"
    assert result.payload["hash"] == "test_hash"
    assert result.payload["data"] == "test_data"
    assert result.payload["user_id"] == "test_user"
    assert result.payload["key"] == "value"  # From metadata


def test_get_not_found(databricks_db, mock_workspace_client):
    """Test getting a vector that doesn't exist."""
    # Mock empty search results
    mock_result_data = MagicMock()
    mock_result_data.data_array = []

    mock_results = MagicMock()
    mock_results.result = mock_result_data
    mock_workspace_client.vector_search_indexes.query_index.return_value = mock_results

    # Call get should raise KeyError
    with pytest.raises(KeyError, match="Vector with ID test_id not found"):
        databricks_db.get("test_id")


def test_list_cols(databricks_db, mock_workspace_client):
    """Test listing collections (indexes)."""
    # Mock list_indexes response
    mock_index1 = MagicMock()
    mock_index1.name = "index1"
    mock_index2 = MagicMock()
    mock_index2.name = "index2"

    mock_workspace_client.vector_search_indexes.list_indexes.return_value = [mock_index1, mock_index2]

    # Call list_cols
    result = databricks_db.list_cols()

    # Check that list_indexes was called
    mock_workspace_client.vector_search_indexes.list_indexes.assert_called_once_with(endpoint_name="test_endpoint")

    # Check result
    assert result == ["index1", "index2"]


def test_delete_col(databricks_db, mock_workspace_client):
    """Test deleting a collection (index)."""
    # Call delete_col
    databricks_db.delete_col()

    # Check that delete_index was called
    mock_workspace_client.vector_search_indexes.delete_index.assert_called_once_with(
        index_name="test_catalog.test_schema.test_index"
    )


def test_col_info(databricks_db, mock_workspace_client):
    """Test getting collection info."""
    # Mock index object
    mock_index = MagicMock()
    mock_index.name = "test_index"
    mock_workspace_client.vector_search_indexes.get_index.return_value = mock_index

    # Call col_info
    result = databricks_db.col_info()

    # Check that get_index was called
    mock_workspace_client.vector_search_indexes.get_index.assert_called_with(
        index_name="test_catalog.test_schema.test_index"
    )

    # Check result
    assert "name" in result
    assert "fields" in result


def test_list(databricks_db, mock_workspace_client):
    """Test listing memories."""
    # Mock search results
    mock_result_data = MagicMock()
    mock_result_data.data_array = [
        {
            "id": "id1",
            "hash": "hash1",
            "memory": "data1",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "metadata": json.dumps({"type": "memory1"}),
            "agent_id": "agent1",
            "run_id": "run1",
            "user_id": "user1",
        },
        {
            "id": "id2",
            "hash": "hash2",
            "memory": "data2",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "metadata": json.dumps({"type": "memory2"}),
            "agent_id": "agent2",
            "run_id": "run2",
            "user_id": "user2",
        },
    ]

    mock_results = MagicMock()
    mock_results.result = mock_result_data
    mock_workspace_client.vector_search_indexes.query_index.return_value = mock_results

    # Call list
    results = databricks_db.list(filters={"user_id": "test_user"}, limit=10)

    # Check that query_index was called
    mock_workspace_client.vector_search_indexes.query_index.assert_called_once()
    _, kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args
    assert kwargs["num_results"] == 10
    assert "filters_json" in kwargs

    # Check results format (nested list)
    assert len(results) == 1
    assert len(results[0]) == 2
    assert results[0][0].id == "id1"
    assert results[0][0].payload["data"] == "data1"
    assert results[0][0].payload["type"] == "memory1"
    assert results[0][1].id == "id2"
    assert results[0][1].payload["data"] == "data2"
    assert results[0][1].payload["type"] == "memory2"


def test_reset(databricks_db, mock_workspace_client):
    """Test resetting an index."""
    # Mock the methods called during reset
    with (
        patch.object(databricks_db, "delete_col") as mock_delete,
        patch.object(databricks_db, "create_col") as mock_create,
    ):
        # Call reset
        databricks_db.reset()

        # Check that delete_col and create_col were called
        mock_delete.assert_called_once()
        mock_create.assert_called_once()


def test_insert_with_payloads(databricks_db, mock_workspace_client):
    """Test inserting with payloads."""
    # Mock successful execution
    mock_response = MagicMock()
    mock_response.status.state = "SUCCEEDED"
    mock_workspace_client.statement_execution.execute_statement.return_value = mock_response

    # Call insert
    databricks_db.insert(
        vectors=[[0.1, 0.2, 0.3] * 512], payloads=[{"data": "test memory", "user_id": "user1"}], ids=["test_id"]
    )

    # Check that execute_statement was called
    mock_workspace_client.statement_execution.execute_statement.assert_called()


def test_insert_auto_embedding_mode(databricks_db, mock_workspace_client):
    """Test inserting in auto-embedding mode."""
    # Set up auto-embedding mode
    databricks_db.embedding_source_column = "text"
    databricks_db.embedding_model_endpoint_name = "e5-small-v2"

    # Mock successful execution
    mock_response = MagicMock()
    mock_response.status.state = "SUCCEEDED"
    mock_workspace_client.statement_execution.execute_statement.return_value = mock_response

    # Call insert (vectors should be ignored)
    databricks_db.insert(
        vectors=[[0.1, 0.2, 0.3] * 512],  # Should be ignored
        payloads=[{"data": "test memory", "user_id": "user1"}],
        ids=["test_id"],
    )

    # Check that execute_statement was called
    mock_workspace_client.statement_execution.execute_statement.assert_called()


def test_delete(databricks_db, mock_workspace_client):
    """Test deleting a vector."""
    # Mock successful execution
    mock_response = MagicMock()
    mock_response.status.state = "SUCCEEDED"
    mock_workspace_client.statement_execution.execute_statement.return_value = mock_response

    # Call delete
    databricks_db.delete("test_id")

    # Check that execute_statement was called with DELETE SQL
    mock_workspace_client.statement_execution.execute_statement.assert_called()
    _, kwargs = mock_workspace_client.statement_execution.execute_statement.call_args
    assert "DELETE FROM" in kwargs["statement"]


def test_update(databricks_db, mock_workspace_client):
    """Test updating a vector."""
    # Mock successful execution
    mock_response = MagicMock()
    mock_response.status.state = "SUCCEEDED"
    mock_workspace_client.statement_execution.execute_statement.return_value = mock_response

    # Call update
    databricks_db.update(
        vector_id="test_id", vector=[0.1, 0.2, 0.3] * 512, payload={"data": "updated memory", "user_id": "user1"}
    )

    # Check that execute_statement was called with UPDATE SQL
    mock_workspace_client.statement_execution.execute_statement.assert_called()
    _, kwargs = mock_workspace_client.statement_execution.execute_statement.call_args
    assert "UPDATE" in kwargs["statement"]


def test_ensure_source_table_exists_creates_table(databricks_db, mock_workspace_client):
    """Test source table creation when it doesn't exist."""
    # Mock table not existing
    mock_workspace_client.tables.get.side_effect = Exception("Table not found")

    # Mock successful table creation
    mock_response = MagicMock()
    mock_response.status.state = "SUCCEEDED"
    mock_workspace_client.statement_execution.execute_statement.return_value = mock_response

    # Call _ensure_source_table_exists
    databricks_db._ensure_source_table_exists()

    # Check that execute_statement was called with CREATE TABLE SQL
    mock_workspace_client.statement_execution.execute_statement.assert_called()
    _, kwargs = mock_workspace_client.statement_execution.execute_statement.call_args
    assert "CREATE TABLE" in kwargs["statement"]


def test_ensure_source_table_exists_table_already_exists(databricks_db, mock_workspace_client):
    """Test when source table already exists."""
    # Mock table existing
    mock_workspace_client.tables.get.return_value = MagicMock()

    # Call _ensure_source_table_exists
    databricks_db._ensure_source_table_exists()

    # Check that execute_statement was NOT called
    mock_workspace_client.statement_execution.execute_statement.assert_not_called()


def test_create_index_with_embedding_model(mock_workspace_client):
    """Test index creation with Databricks-computed embeddings."""
    mock_workspace_client.vector_search_endpoints.get_endpoint.return_value = MagicMock()
    mock_workspace_client.vector_search_indexes.list_indexes.return_value = []
    mock_workspace_client.tables.get.return_value = MagicMock()  # Table exists

    with patch("mem0.vector_stores.databricks.WorkspaceClient") as mock_client_class:
        mock_client_class.return_value = mock_workspace_client

        # Mock that create_col doesn't fail by patching the problematic SDK call
        with patch.object(Databricks, "create_col") as mock_create_col:
            Databricks(
                workspace_url="https://test.databricks.com",
                access_token="test_token",
                endpoint_name="test_endpoint",
                index_name="test_index",
                source_table_name="test_table",
                embedding_source_column="text",
                embedding_model_endpoint_name="e5-small-v2",
            )

            # Check that create_col was called
            mock_create_col.assert_called_once()


def test_create_index_with_self_managed_embeddings(mock_workspace_client):
    """Test index creation with self-managed embeddings."""
    mock_workspace_client.vector_search_endpoints.get_endpoint.return_value = MagicMock()
    mock_workspace_client.vector_search_indexes.list_indexes.return_value = []
    mock_workspace_client.tables.get.return_value = MagicMock()  # Table exists

    with patch("mem0.vector_stores.databricks.WorkspaceClient") as mock_client_class:
        mock_client_class.return_value = mock_workspace_client

        # Mock that create_col doesn't fail by patching the problematic SDK call
        with patch.object(Databricks, "create_col") as mock_create_col:
            Databricks(
                workspace_url="https://test.databricks.com",
                access_token="test_token",
                endpoint_name="test_endpoint",
                index_name="test_index",
                source_table_name="test_table",
                embedding_dimension=768,
            )

            # Check that create_col was called
            mock_create_col.assert_called_once()


def test_storage_optimized_endpoint_type(mock_workspace_client):
    """Test creation with storage-optimized endpoint type."""
    mock_workspace_client.vector_search_endpoints.get_endpoint.side_effect = Exception("Not found")
    mock_workspace_client.vector_search_indexes.list_indexes.return_value = [MagicMock(name="test_index")]
    mock_workspace_client.tables.get.return_value = MagicMock()  # Table exists

    with patch("mem0.vector_stores.databricks.WorkspaceClient") as mock_client_class:
        mock_client_class.return_value = mock_workspace_client

        db = Databricks(
            workspace_url="https://test.databricks.com",
            access_token="test_token",
            endpoint_name="test_endpoint",
            index_name="test_index",
            source_table_name="test_table",
            endpoint_type="STORAGE_OPTIMIZED",
        )

        # Check that endpoint was created with correct type
        mock_workspace_client.vector_search_endpoints.create_endpoint_and_wait.assert_called()

        assert db.endpoint_type == "STORAGE_OPTIMIZED"


def test_client_initialization_error():
    """Test error handling during client initialization."""
    with patch("mem0.vector_stores.databricks.WorkspaceClient") as mock_client_class:
        mock_client_class.side_effect = Exception("Failed to initialize client")

        with pytest.raises(Exception, match="Failed to initialize client"):
            Databricks(
                workspace_url="https://test.databricks.com",
                access_token="test_token",
                endpoint_name="test_endpoint",
                index_name="test_index",
                source_table_name="test_table",
            )


def test_search_error_handling(databricks_db, mock_workspace_client):
    """Test search error handling."""
    # Mock query_index to raise an exception
    mock_workspace_client.vector_search_indexes.query_index.side_effect = Exception("Search failed")

    # Call search should raise the exception
    with pytest.raises(Exception, match="Search failed"):
        databricks_db.search(query="test", vectors=[0.1, 0.2], limit=5)


def test_list_error_handling(databricks_db, mock_workspace_client):
    """Test list error handling."""
    # Mock query_index to raise an exception
    mock_workspace_client.vector_search_indexes.query_index.side_effect = Exception("List failed")

    # Call list should return empty nested list on error
    results = databricks_db.list()
    assert results == [[]]


def test_search_with_invalid_metadata(databricks_db, mock_workspace_client):
    """Test search with invalid JSON metadata."""
    # Mock search results with invalid metadata
    mock_result_data = MagicMock()
    mock_result_data.data_array = [
        {
            "id": "test_id",
            "hash": "test_hash",
            "memory": "test_data",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "metadata": "invalid_json{",  # Invalid JSON
            "agent_id": "",
            "run_id": "",
            "user_id": "",
        }
    ]

    mock_results = MagicMock()
    mock_results.result = mock_result_data
    mock_workspace_client.vector_search_indexes.query_index.return_value = mock_results

    # Should handle invalid JSON gracefully
    results = databricks_db.search(query="test", vectors=[], limit=5)

    assert len(results) == 1
    # Should still return result despite invalid metadata


def test_insert_no_payloads_warning(databricks_db, mock_workspace_client, caplog):
    """Test insert logs warning when no payloads provided in auto-embedding mode."""
    # Set up auto-embedding mode
    databricks_db.embedding_source_column = "text"
    databricks_db.embedding_model_endpoint_name = "e5-small-v2"

    # Call insert without payloads
    databricks_db.insert(vectors=[[0.1, 0.2]], payloads=None, ids=["test_id"])

    # Check that warning was logged
    assert "No payloads provided for insertion" in caplog.text


def test_insert_no_vectors_warning(databricks_db, mock_workspace_client, caplog):
    """Test insert logs warning when no vectors provided."""
    # Call insert without vectors (not in auto-embedding mode)
    databricks_db.insert(vectors=None, payloads=[{"data": "test"}], ids=["test_id"])

    # Check that warning was logged
    assert "No vectors provided for insertion" in caplog.text


def test_update_no_vector_id_error(databricks_db, mock_workspace_client, caplog):
    """Test update logs error when no vector_id provided."""
    # Call update without vector_id
    databricks_db.update(vector_id=None, payload={"data": "test"})

    # Check that error was logged
    assert "vector_id is required for update operation" in caplog.text


def test_update_no_fields_warning(databricks_db, mock_workspace_client, caplog):
    """Test update logs warning when no fields to update."""
    # Call update with no meaningful changes
    databricks_db.update(vector_id="test_id")

    # Check that warning was logged
    assert "No fields to update" in caplog.text
