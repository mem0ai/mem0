import pytest
from unittest.mock import patch, MagicMock, Mock
import uuid
import json
from mem0.vector_stores.databricks import Databricks


# --- Fixtures for Databricks SDK clients ---
@pytest.fixture
def mock_databricks_clients():
    with (
        patch("mem0.vector_stores.databricks.WorkspaceClient") as MockWorkspaceClient,
        patch("mem0.vector_stores.databricks.ColumnInfo") as MockColumnInfo,
        patch("mem0.vector_stores.databricks.VectorIndexType") as MockVectorIndexType,
        patch("mem0.vector_stores.databricks.DeltaSyncVectorIndexSpecRequest") as MockDeltaSyncSpec,
        patch("mem0.vector_stores.databricks.DirectAccessVectorIndexSpec") as MockDirectAccessSpec,
        patch("mem0.vector_stores.databricks.EmbeddingSourceColumn") as MockEmbeddingSourceColumn,
        patch("mem0.vector_stores.databricks.PipelineType") as MockPipelineType,
    ):
        mock_workspace_client = MockWorkspaceClient.return_value
        # Mock vector_search_endpoints and vector_search_indexes
        mock_workspace_client.vector_search_endpoints = Mock()
        mock_workspace_client.vector_search_indexes = Mock()
        mock_workspace_client.tables = Mock()
        mock_workspace_client.statement_execution = Mock()
        # Mock methods
        mock_workspace_client.vector_search_endpoints.get_endpoint = Mock()
        mock_workspace_client.vector_search_endpoints.create_endpoint_and_wait = Mock()
        mock_workspace_client.vector_search_indexes.create_index = Mock()
        mock_workspace_client.vector_search_indexes.list_indexes = Mock(return_value=[])
        mock_workspace_client.vector_search_indexes.delete_index = Mock()
        mock_workspace_client.vector_search_indexes.get_index = Mock()
        mock_workspace_client.vector_search_indexes.query_index = Mock()
        mock_workspace_client.tables.exists = Mock(return_value=Mock(table_exists=True))
        mock_workspace_client.tables.create = Mock()
        mock_workspace_client.statement_execution.execute_statement = Mock()
        yield mock_workspace_client, MockColumnInfo, MockVectorIndexType


@pytest.fixture
def databricks_instance(mock_databricks_clients):
    mock_workspace_client, MockColumnInfo, MockVectorIndexType = mock_databricks_clients
    instance = Databricks(
        workspace_url="https://test-workspace",
        endpoint_name="test-endpoint",
        catalog="test-catalog",
        schema="test-schema",
        table_name="test-table",
        index_name="test-index",
        index_type="DELTA_SYNC",
        embedding_model_endpoint_name="test-embed-endpoint",
        embedding_dimension=3,
        endpoint_type="STANDARD",
        pipeline_type="TRIGGERED",
        warehouse_id="wh-123",
    )
    # Patch the client on the instance
    instance.client = mock_workspace_client
    return instance, mock_workspace_client


# --- Tests for Databricks initialization ---
def test_initialization(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    assert instance.workspace_url == "https://test-workspace"
    assert instance.endpoint_name == "test-endpoint"
    assert instance.catalog == "test-catalog"
    assert instance.schema == "test-schema"
    assert instance.table_name == "test-table"
    assert instance.index_name == "test-index"
    assert instance.embedding_dimension == 3
    assert instance.endpoint_type == "STANDARD"
    assert instance.pipeline_type == "TRIGGERED"
    assert instance.warehouse_id == "wh-123"
    # Check that endpoint and index creation were called
    mock_workspace_client.vector_search_endpoints.get_endpoint.assert_called()
    mock_workspace_client.vector_search_indexes.list_indexes.assert_called()


# --- Tests for create_col ---
def test_create_col(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    instance.create_col()
    mock_workspace_client.vector_search_indexes.create_index.assert_called()


# --- Tests for insert ---
def test_insert_single(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{"user_id": "user1", "run_id": "run1", "agent_id": "agent1"}]
    ids = [str(uuid.uuid4())]
    # Mock successful response
    mock_workspace_client.statement_execution.execute_statement.return_value = Mock(status=Mock(state="SUCCEEDED"))
    instance.insert(vectors, payloads, ids)
    mock_workspace_client.statement_execution.execute_statement.assert_called()


def test_insert_multiple(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"user_id": "user1"}, {"user_id": "user2"}]
    ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    mock_workspace_client.statement_execution.execute_statement.return_value = Mock(status=Mock(state="SUCCEEDED"))
    instance.insert(vectors, payloads, ids)
    assert mock_workspace_client.statement_execution.execute_statement.call_count == 1


# --- Tests for search ---
def test_search_basic(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    # Mock SDK result
    mock_result = Mock()
    mock_result.result = Mock()
    mock_result.result.data_array = [
        ["id1", "hash1", "agent1", "run1", "user1", "memory1", "{}", "2023-01-01T00:00:00Z", "2023-01-01T00:00:00Z"]
    ]
    mock_workspace_client.vector_search_indexes.query_index.return_value = mock_result
    results = instance.search(query="test", vectors=None, limit=1)
    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].payload["memory"] == "memory1"


# --- Tests for update ---
def test_update(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    vector_id = str(uuid.uuid4())
    vector = [0.1, 0.2, 0.3]
    payload = {"user_id": "user1", "memory": "updated memory"}
    mock_workspace_client.statement_execution.execute_statement.return_value = Mock(status=Mock(state="SUCCEEDED"))
    instance.update(vector_id=vector_id, vector=vector, payload=payload)
    mock_workspace_client.statement_execution.execute_statement.assert_called()


# --- Tests for delete ---
def test_delete(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    vector_id = str(uuid.uuid4())
    mock_workspace_client.statement_execution.execute_statement.return_value = Mock(status=Mock(state="SUCCEEDED"))
    instance.delete(vector_id)
    mock_workspace_client.statement_execution.execute_statement.assert_called()


# --- Tests for get ---
def test_get(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    # Mock SDK result
    mock_result = Mock()
    mock_result.result = Mock()
    mock_result.result.data_array = [
        ["id1", "hash1", "agent1", "run1", "user1", "memory1", "{}", "2023-01-01T00:00:00Z", "2023-01-01T00:00:00Z"]
    ]
    mock_workspace_client.vector_search_indexes.query_index.return_value = mock_result
    result = instance.get("id1")
    assert result.id == "id1"
    assert result.payload["memory"] == "memory1"


# --- Tests for list ---
def test_list(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    # Mock SDK result
    mock_result = Mock()
    mock_result.result = Mock()
    mock_result.result.data_array = [
        ["id1", "hash1", "agent1", "run1", "user1", "memory1", "{}", "2023-01-01T00:00:00Z", "2023-01-01T00:00:00Z"]
    ]
    mock_workspace_client.vector_search_indexes.query_index.return_value = mock_result
    results = instance.list()
    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].payload["memory"] == "memory1"


# --- Tests for reset ---
def test_reset(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    instance.reset()
    mock_workspace_client.vector_search_indexes.delete_index.assert_called()
    mock_workspace_client.vector_search_indexes.create_index.assert_called()


# --- Tests for col_info ---
def test_col_info(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    mock_workspace_client.vector_search_indexes.get_index.return_value = Mock(name="test-index")
    info = instance.col_info()
    assert info["name"] == "test-index"


# --- Tests for list_cols ---
def test_list_cols(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    mock_workspace_client.vector_search_indexes.list_indexes.return_value = [Mock(name="index1"), Mock(name="index2")]
    cols = instance.list_cols()
    assert cols == ["index1", "index2"]


# --- Tests for delete_col ---
def test_delete_col(databricks_instance):
    instance, mock_workspace_client = databricks_instance
    instance.delete_col()
    mock_workspace_client.vector_search_indexes.delete_index.assert_called()
