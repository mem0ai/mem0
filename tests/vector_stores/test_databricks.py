from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from databricks.sdk.service.vectorsearch import VectorIndexType
from mem0.vector_stores.databricks import Databricks
import pytest


# ---------------------- Fixtures ---------------------- #


def _make_status(state="SUCCEEDED", error=None):
    return SimpleNamespace(state=SimpleNamespace(value=state), error=error)


def _make_exec_response(state="SUCCEEDED", error=None):
    return SimpleNamespace(status=_make_status(state, error))


@pytest.fixture
def mock_workspace_client():
    """Patch WorkspaceClient and provide a fully mocked client with required sub-clients."""
    with patch("mem0.vector_stores.databricks.WorkspaceClient") as mock_wc_cls:
        mock_wc = MagicMock(name="WorkspaceClient")

        # warehouses.list -> iterable of objects with name/id
        warehouse_obj = SimpleNamespace(name="test-warehouse", id="wh-123")
        mock_wc.warehouses.list.return_value = [warehouse_obj]

        # vector search endpoints
        mock_wc.vector_search_endpoints.get_endpoint.side_effect = [Exception("not found"), MagicMock()]
        mock_wc.vector_search_endpoints.create_endpoint_and_wait.return_value = None

        # tables.exists
        exists_obj = SimpleNamespace(table_exists=False)
        mock_wc.tables.exists.return_value = exists_obj
        mock_wc.tables.create.return_value = None
        mock_wc.table_constraints.create.return_value = None

        # vector_search_indexes list/create/query/delete
        mock_wc.vector_search_indexes.list_indexes.return_value = []
        mock_wc.vector_search_indexes.create_index.return_value = SimpleNamespace(name="catalog.schema.mem0")
        mock_wc.vector_search_indexes.query_index.return_value = SimpleNamespace(result=SimpleNamespace(data_array=[]))
        mock_wc.vector_search_indexes.delete_index.return_value = None
        mock_wc.vector_search_indexes.get_index.return_value = SimpleNamespace(name="mem0")

        # statement execution
        mock_wc.statement_execution.execute_statement.return_value = _make_exec_response()

        mock_wc_cls.return_value = mock_wc
        yield mock_wc


@pytest.fixture
def db_instance_delta(mock_workspace_client):
    return Databricks(
        workspace_url="https://test",
        access_token="tok",
        endpoint_name="vs-endpoint",
        catalog="catalog",
        schema="schema",
        table_name="table",
        collection_name="mem0",
        warehouse_name="test-warehouse",
        index_type=VectorIndexType.DELTA_SYNC,
        embedding_model_endpoint_name="embedding-endpoint",
    )


@pytest.fixture
def db_instance_direct(mock_workspace_client):
    # For DIRECT_ACCESS we want table exists path to skip creation; adjust mock first
    mock_workspace_client.tables.exists.return_value = SimpleNamespace(table_exists=True)
    return Databricks(
        workspace_url="https://test",
        access_token="tok",
        endpoint_name="vs-endpoint",
        catalog="catalog",
        schema="schema",
        table_name="table",
        collection_name="mem0",
        warehouse_name="test-warehouse",
        index_type=VectorIndexType.DIRECT_ACCESS,
        embedding_dimension=4,
        embedding_model_endpoint_name="embedding-endpoint",
    )


# ---------------------- Initialization Tests ---------------------- #


def test_initialization_delta_sync(db_instance_delta, mock_workspace_client):
    # Endpoint ensure called (first attempt get_endpoint fails then create)
    mock_workspace_client.vector_search_endpoints.create_endpoint_and_wait.assert_called_once()
    # Table creation sequence
    mock_workspace_client.tables.create.assert_called_once()
    # Index created with expected args
    assert (
        mock_workspace_client.vector_search_indexes.create_index.call_args.kwargs["index_type"]
        == VectorIndexType.DELTA_SYNC
    )
    assert mock_workspace_client.vector_search_indexes.create_index.call_args.kwargs["primary_key"] == "memory_id"


def test_initialization_direct_access(db_instance_direct, mock_workspace_client):
    # DIRECT_ACCESS should include embedding column
    assert "embedding" in db_instance_direct.column_names
    assert (
        mock_workspace_client.vector_search_indexes.create_index.call_args.kwargs["index_type"]
        == VectorIndexType.DIRECT_ACCESS
    )


def test_create_col_invalid_type(mock_workspace_client):
    # Force invalid type by manually constructing and calling create_col after monkeypatching index_type
    inst = Databricks(
        workspace_url="https://test",
        access_token="tok",
        endpoint_name="vs-endpoint",
        catalog="catalog",
        schema="schema",
        table_name="table",
        collection_name="mem0",
        warehouse_name="test-warehouse",
        index_type=VectorIndexType.DELTA_SYNC,
    )
    inst.index_type = "BAD_TYPE"
    with pytest.raises(ValueError):
        inst.create_col()


# ---------------------- Insert Tests ---------------------- #


def test_insert_generates_sql(db_instance_direct, mock_workspace_client):
    vectors = [[0.1, 0.2, 0.3, 0.4]]
    payloads = [
        {
            "data": "hello world",
            "user_id": "u1",
            "agent_id": "a1",
            "run_id": "r1",
            "metadata": '{"topic":"greeting"}',
            "hash": "h1",
        }
    ]
    ids = ["id1"]
    db_instance_direct.insert(vectors=vectors, payloads=payloads, ids=ids)
    args, kwargs = mock_workspace_client.statement_execution.execute_statement.call_args
    sql = kwargs["statement"] if "statement" in kwargs else args[0]
    assert "INSERT INTO" in sql
    assert "catalog.schema.table" in sql
    assert "id1" in sql
    # Embedding list rendered
    assert "array(0.1, 0.2, 0.3, 0.4)" in sql


# ---------------------- Search Tests ---------------------- #


def test_search_delta_sync_text(db_instance_delta, mock_workspace_client):
    # Simulate query results
    row = [
        "id1",
        "hash1",
        "agent1",
        "run1",
        "user1",
        "memory text",
        '{"topic":"greeting"}',
        "2024-01-01T00:00:00",
        "2024-01-01T00:00:00",
        0.42,
    ]
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(data_array=[row])
    )
    results = db_instance_delta.search(query="hello", vectors=None, limit=1)
    mock_workspace_client.vector_search_indexes.query_index.assert_called_once()
    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].score == 0.42
    assert results[0].payload["data"] == "memory text"


def test_search_direct_access_vector(db_instance_direct, mock_workspace_client):
    row = [
        "id2",
        "hash2",
        "agent2",
        "run2",
        "user2",
        "memory two",
        '{"topic":"info"}',
        "2024-01-02T00:00:00",
        "2024-01-02T00:00:00",
        [0.1, 0.2, 0.3, 0.4],
        0.77,
    ]
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(data_array=[row])
    )
    results = db_instance_direct.search(query="", vectors=[0.1, 0.2, 0.3, 0.4], limit=1)
    assert len(results) == 1
    assert results[0].id == "id2"
    assert results[0].score == 0.77


def test_search_missing_params_raises(db_instance_delta):
    with pytest.raises(ValueError):
        db_instance_delta.search(query="", vectors=[0.1, 0.2])  # DELTA_SYNC requires query text


# ---------------------- Delete Tests ---------------------- #


def test_delete_vector(db_instance_delta, mock_workspace_client):
    db_instance_delta.delete("id-delete")
    args, kwargs = mock_workspace_client.statement_execution.execute_statement.call_args
    sql = kwargs.get("statement") or args[0]
    assert "DELETE FROM" in sql and "id-delete" in sql


# ---------------------- Update Tests ---------------------- #


def test_update_vector(db_instance_direct, mock_workspace_client):
    db_instance_direct.update(
        vector_id="id-upd",
        vector=[0.4, 0.5, 0.6, 0.7],
        payload={"custom": "val", "user_id": "skip"},  # user_id should be excluded
    )
    args, kwargs = mock_workspace_client.statement_execution.execute_statement.call_args
    sql = kwargs.get("statement") or args[0]
    assert "UPDATE" in sql and "id-upd" in sql
    assert "embedding = [0.4, 0.5, 0.6, 0.7]" in sql
    assert "custom = 'val'" in sql
    assert "user_id" not in sql  # excluded


# ---------------------- Get Tests ---------------------- #


def test_get_vector(db_instance_delta, mock_workspace_client):
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(
            data_array=[
                {
                    "memory_id": "id-get",
                    "hash": "h",
                    "agent_id": "a",
                    "run_id": "r",
                    "user_id": "u",
                    "memory": "some memory",
                    "metadata": '{"tag":"x"}',
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                    "score": 0.99,
                }
            ]
        )
    )
    res = db_instance_delta.get("id-get")
    assert res.id == "id-get"
    assert res.payload["data"] == "some memory"
    assert res.payload["tag"] == "x"


# ---------------------- Collection Info / Listing Tests ---------------------- #


def test_list_cols(db_instance_delta, mock_workspace_client):
    mock_workspace_client.vector_search_indexes.list_indexes.return_value = [
        SimpleNamespace(name="catalog.schema.mem0"),
        SimpleNamespace(name="catalog.schema.other"),
    ]
    cols = db_instance_delta.list_cols()
    assert "catalog.schema.mem0" in cols and "catalog.schema.other" in cols


def test_col_info(db_instance_delta):
    info = db_instance_delta.col_info()
    assert info["name"] == "mem0"
    assert any(col.name == "memory_id" for col in info["fields"])


def test_list_memories(db_instance_delta, mock_workspace_client):
    row = {
        "memory_id": "id3",
        "hash": "hash3",
        "agent_id": "agent3",
        "run_id": "run3",
        "user_id": "user3",
        "memory": "memory three",
        "metadata": '{"topic":"misc"}',
        "created_at": "2024-01-03T00:00:00",
        "updated_at": "2024-01-03T00:00:00",
        "score": 0.33,
    }
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(data_array=[row])
    )
    res = db_instance_delta.list(limit=1)
    assert isinstance(res, list)
    assert len(res[0]) == 1
    assert res[0][0].id == "id3"


# ---------------------- Reset Tests ---------------------- #


def test_reset(db_instance_delta, mock_workspace_client):
    # Make delete raise to exercise fallback path then allow recreation
    mock_workspace_client.vector_search_indexes.delete_index.side_effect = [Exception("fail fq"), None, None]
    with patch.object(db_instance_delta, "create_col", wraps=db_instance_delta.create_col) as create_spy:
        db_instance_delta.reset()
        assert create_spy.called
