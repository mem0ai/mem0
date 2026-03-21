from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("databricks", reason="databricks-sdk package not installed")

from databricks.sdk.service.vectorsearch import VectorIndexType, QueryVectorIndexResponse, ResultManifest, ResultData, ColumnInfo
from mem0.vector_stores.databricks import Databricks


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


def test_search_delta_sync_self_managed_vectors(mock_workspace_client):
    """DELTA_SYNC without embedding model endpoint should use query_vector, not query_text."""
    mock_workspace_client.tables.exists.return_value = SimpleNamespace(table_exists=True)
    # DELTA_SYNC without embedding_model_endpoint_name = self-managed vectors
    inst = Databricks(
        workspace_url="https://test",
        access_token="tok",
        endpoint_name="vs-endpoint",
        catalog="catalog",
        schema="schema",
        table_name="table",
        warehouse_name="test-warehouse",
        index_type=VectorIndexType.DELTA_SYNC,
        embedding_dimension=4,
        # NOTE: no embedding_model_endpoint_name
    )
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(data_array=[])
    )
    inst.search(query="ignored", vectors=[0.1, 0.2, 0.3, 0.4], limit=5)
    call_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_vector" in call_kwargs
    assert "query_text" not in call_kwargs


def test_search_missing_params_raises(db_instance_delta):
    with pytest.raises(ValueError):
        db_instance_delta.search(query="", vectors=[0.1, 0.2])  # DELTA_SYNC with model endpoint requires query text


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
    mock_workspace_client.vector_search_indexes.query_index.return_value = QueryVectorIndexResponse(
        manifest=ResultManifest(columns=[
            ColumnInfo(name="memory_id"),
            ColumnInfo(name="hash"),
            ColumnInfo(name="agent_id"),
            ColumnInfo(name="run_id"),
            ColumnInfo(name="user_id"),
            ColumnInfo(name="memory"),
            ColumnInfo(name="metadata"),
            ColumnInfo(name="created_at"),
            ColumnInfo(name="updated_at"),
            ColumnInfo(name="score"),
        ]),
        result=ResultData(
            data_array=[
                [
                    "id-get",
                    "h",
                    "a",
                    "r",
                    "u",
                    "some memory",
                    '{"tag":"x"}',
                    "2024-01-01T00:00:00",
                    "2024-01-01T00:00:00",
                    "0.99",
                ]
            ]
        )
    )
    res = db_instance_delta.get("id-get")
    assert res.id == "id-get"
    assert res.payload["data"] == "some memory"
    assert res.payload["tag"] == "x"
    # DELTA_SYNC should use query_text, not query_vector
    call_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_text" in call_kwargs
    assert "query_vector" not in call_kwargs


def test_get_vector_direct_access(db_instance_direct, mock_workspace_client):
    """get() on a DIRECT_ACCESS index must use query_vector instead of query_text."""
    mock_workspace_client.vector_search_indexes.query_index.return_value = QueryVectorIndexResponse(
        manifest=ResultManifest(columns=[
            ColumnInfo(name="memory_id"),
            ColumnInfo(name="hash"),
            ColumnInfo(name="agent_id"),
            ColumnInfo(name="run_id"),
            ColumnInfo(name="user_id"),
            ColumnInfo(name="memory"),
            ColumnInfo(name="metadata"),
            ColumnInfo(name="created_at"),
            ColumnInfo(name="updated_at"),
            ColumnInfo(name="embedding"),
            ColumnInfo(name="score"),
        ]),
        result=ResultData(
            data_array=[
                [
                    "id-get-da",
                    "h",
                    "a",
                    "r",
                    "u",
                    "direct access memory",
                    '{"tag":"da"}',
                    "2024-01-01T00:00:00",
                    "2024-01-01T00:00:00",
                    [0.1, 0.2, 0.3, 0.4],
                    "0.88",
                ]
            ]
        )
    )
    res = db_instance_direct.get("id-get-da")
    assert res.id == "id-get-da"
    assert res.payload["data"] == "direct access memory"
    # DIRECT_ACCESS should use query_vector, not query_text
    call_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_vector" in call_kwargs
    assert "query_text" not in call_kwargs
    assert call_kwargs["query_vector"] == [0.0] * 4  # embedding_dimension=4


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
    mock_workspace_client.vector_search_indexes.query_index.return_value = QueryVectorIndexResponse(
        manifest=ResultManifest(columns=[
            ColumnInfo(name="memory_id"),
            ColumnInfo(name="hash"),
            ColumnInfo(name="agent_id"),
            ColumnInfo(name="run_id"),
            ColumnInfo(name="user_id"),
            ColumnInfo(name="memory"),
            ColumnInfo(name="metadata"),
            ColumnInfo(name="created_at"),
            ColumnInfo(name="updated_at"),
            ColumnInfo(name="score"),
        ]),
        result=ResultData(
            data_array=[
                [
                    "id-get",
                    "h",
                    "a",
                    "r",
                    "u",
                    "some memory",
                    '{"tag":"x"}',
                    "2024-01-01T00:00:00",
                    "2024-01-01T00:00:00",
                    "0.99",
                ]
            ]
        )
    )
    res = db_instance_delta.list(limit=1)
    assert isinstance(res, list)
    assert len(res[0]) == 1
    assert res[0][0].id == "id-get"
    # DELTA_SYNC should use query_text
    call_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_text" in call_kwargs
    assert "query_vector" not in call_kwargs


def test_list_memories_direct_access(db_instance_direct, mock_workspace_client):
    """list() on a DIRECT_ACCESS index must use query_vector instead of query_text."""
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(
            data_array=[
                [
                    "id-da-list",
                    "h",
                    "a",
                    "r",
                    "u",
                    "direct memory",
                    None,
                    "2024-01-01T00:00:00",
                    "2024-01-01T00:00:00",
                    [0.1, 0.2, 0.3, 0.4],
                ]
            ]
        )
    )
    res = db_instance_direct.list(limit=5)
    assert isinstance(res, list)
    assert len(res[0]) == 1
    assert res[0][0].id == "id-da-list"
    assert res[0][0].payload["data"] == "direct memory"
    # DIRECT_ACCESS should use query_vector
    call_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_vector" in call_kwargs
    assert "query_text" not in call_kwargs
    assert call_kwargs["query_vector"] == [0.0] * 4


def test_get_vector_delta_sync_self_managed(mock_workspace_client):
    """get() on DELTA_SYNC without model endpoint should use query_vector."""
    mock_workspace_client.tables.exists.return_value = SimpleNamespace(table_exists=True)
    inst = Databricks(
        workspace_url="https://test",
        access_token="tok",
        endpoint_name="vs-endpoint",
        catalog="catalog",
        schema="schema",
        table_name="table",
        warehouse_name="test-warehouse",
        index_type=VectorIndexType.DELTA_SYNC,
        embedding_dimension=4,
        # NOTE: no embedding_model_endpoint_name
    )
    mock_workspace_client.vector_search_indexes.query_index.return_value = QueryVectorIndexResponse(
        manifest=ResultManifest(columns=[
            ColumnInfo(name="memory_id"), ColumnInfo(name="hash"),
            ColumnInfo(name="agent_id"), ColumnInfo(name="run_id"),
            ColumnInfo(name="user_id"), ColumnInfo(name="memory"),
            ColumnInfo(name="metadata"), ColumnInfo(name="created_at"),
            ColumnInfo(name="updated_at"),
        ]),
        result=ResultData(data_array=[["id-sm", "h", None, None, None, "self-managed mem", None, None, None]]),
    )
    res = inst.get("id-sm")
    assert res.id == "id-sm"
    call_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_vector" in call_kwargs
    assert "query_text" not in call_kwargs
    assert call_kwargs["query_vector"] == [0.0] * 4


def test_list_memories_delta_sync_self_managed(mock_workspace_client):
    """list() on DELTA_SYNC without model endpoint should use query_vector."""
    mock_workspace_client.tables.exists.return_value = SimpleNamespace(table_exists=True)
    inst = Databricks(
        workspace_url="https://test",
        access_token="tok",
        endpoint_name="vs-endpoint",
        catalog="catalog",
        schema="schema",
        table_name="table",
        warehouse_name="test-warehouse",
        index_type=VectorIndexType.DELTA_SYNC,
        embedding_dimension=4,
        # NOTE: no embedding_model_endpoint_name
    )
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(data_array=[])
    )
    inst.list(limit=5)
    call_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_vector" in call_kwargs
    assert "query_text" not in call_kwargs


def test_list_memories_default_limit(db_instance_delta, mock_workspace_client):
    """list() with no limit should default to 100."""
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(data_array=[])
    )
    db_instance_delta.list(limit=None)
    call_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert call_kwargs["num_results"] == 100


# ---------------------- Table Creation Tests ---------------------- #


def test_ensure_source_table_uses_dynamic_names(mock_workspace_client):
    """Verify _ensure_source_table_exists uses self.fully_qualified_table_name and
    self.table_name for the PK constraint, not hardcoded values."""
    mock_workspace_client.tables.exists.return_value = SimpleNamespace(table_exists=False)
    inst = Databricks(
        workspace_url="https://test",
        access_token="tok",
        endpoint_name="vs-endpoint",
        catalog="my_catalog",
        schema="my_schema",
        table_name="my_memories",
        collection_name="my_index",
        warehouse_name="test-warehouse",
        index_type=VectorIndexType.DELTA_SYNC,
        embedding_model_endpoint_name="embedding-endpoint",
    )
    # _ensure_source_table_exists was called during __init__ via create_col
    constraint_call = mock_workspace_client.table_constraints.create.call_args
    assert constraint_call.kwargs["full_name_arg"] == "my_catalog.my_schema.my_memories"
    pk_name = constraint_call.kwargs["constraint"].primary_key_constraint.name
    assert pk_name == "pk_my_memories"


# ---------------------- Config Validation Tests ---------------------- #


def test_config_rejects_old_doc_params():
    """Config should reject the old documentation parameter names like index_name and source_table_name."""
    from mem0.configs.vector_stores.databricks import DatabricksConfig
    with pytest.raises(ValueError, match="Extra fields not allowed"):
        DatabricksConfig(
            workspace_url="https://test",
            access_token="tok",
            endpoint_name="ep",
            catalog="cat",
            schema="sch",
            table_name="tbl",
            index_name="catalog.schema.index",  # old param from docs
        )


def test_config_rejects_source_table_name():
    """Config should reject source_table_name which was in old docs."""
    from mem0.configs.vector_stores.databricks import DatabricksConfig
    with pytest.raises(ValueError, match="Extra fields not allowed"):
        DatabricksConfig(
            workspace_url="https://test",
            access_token="tok",
            endpoint_name="ep",
            catalog="cat",
            schema="sch",
            table_name="tbl",
            source_table_name="catalog.schema.table",  # old param from docs
        )


def test_config_accepts_correct_params():
    """Config should accept all the correct parameter names."""
    from mem0.configs.vector_stores.databricks import DatabricksConfig
    config = DatabricksConfig(
        workspace_url="https://test",
        access_token="tok",
        endpoint_name="ep",
        catalog="cat",
        schema="sch",
        table_name="tbl",
        collection_name="my_index",
        embedding_dimension=768,
    )
    assert config.collection_name == "my_index"
    assert config.embedding_dimension == 768


# ---------------------- Reset Tests ---------------------- #


def test_reset(db_instance_delta, mock_workspace_client):
    # Make delete raise to exercise fallback path then allow recreation
    mock_workspace_client.vector_search_indexes.delete_index.side_effect = [Exception("fail fq"), None, None]
    with patch.object(db_instance_delta, "create_col", wraps=db_instance_delta.create_col) as create_spy:
        db_instance_delta.reset()
        assert create_spy.called


# ---------------------- End-to-End Config → Factory → CRUD Tests ---------------------- #


def test_e2e_config_to_factory_delta_sync(mock_workspace_client):
    """End-to-end: VectorStoreConfig validates docs-correct params, factory creates Databricks instance."""
    from mem0.vector_stores.configs import VectorStoreConfig
    from mem0.utils.factory import VectorStoreFactory

    # Step 1: Config validation (simulates what Memory.from_config does)
    vs_config = VectorStoreConfig(
        provider="databricks",
        config={
            "workspace_url": "https://my-workspace.databricks.com",
            "access_token": "my-token",
            "endpoint_name": "my-endpoint",
            "catalog": "prod_catalog",
            "schema": "ai_schema",
            "table_name": "memories_table",
            "collection_name": "my_index",
            "embedding_dimension": 768,
            "warehouse_name": "test-warehouse",
        },
    )
    assert vs_config.config.collection_name == "my_index"
    assert vs_config.config.catalog == "prod_catalog"

    # Step 2: Factory instantiation (same as MemoryBase.__init__)
    instance = VectorStoreFactory.create("databricks", vs_config.config)
    assert isinstance(instance, Databricks)
    assert instance.fully_qualified_table_name == "prod_catalog.ai_schema.memories_table"
    assert instance.fully_qualified_index_name == "prod_catalog.ai_schema.my_index"
    assert instance.embedding_dimension == 768


def test_e2e_config_to_factory_direct_access(mock_workspace_client):
    """End-to-end: DIRECT_ACCESS via config → factory creates correct instance."""
    from mem0.vector_stores.configs import VectorStoreConfig
    from mem0.utils.factory import VectorStoreFactory

    mock_workspace_client.tables.exists.return_value = SimpleNamespace(table_exists=True)

    vs_config = VectorStoreConfig(
        provider="databricks",
        config={
            "workspace_url": "https://my-workspace.databricks.com",
            "access_token": "my-token",
            "endpoint_name": "my-endpoint",
            "catalog": "cat",
            "schema": "sch",
            "table_name": "tbl",
            "index_type": "DIRECT_ACCESS",
            "embedding_dimension": 4,
            "warehouse_name": "test-warehouse",
        },
    )
    instance = VectorStoreFactory.create("databricks", vs_config.config)
    assert isinstance(instance, Databricks)
    assert "embedding" in instance.column_names


def test_e2e_old_docs_config_rejected():
    """End-to-end: Config from old docs (with index_name, source_table_name) is rejected at validation."""
    from mem0.vector_stores.configs import VectorStoreConfig

    with pytest.raises(ValueError, match="Extra fields not allowed"):
        VectorStoreConfig(
            provider="databricks",
            config={
                "workspace_url": "https://my-workspace.databricks.com",
                "access_token": "my-token",
                "endpoint_name": "my-endpoint",
                "index_name": "catalog.schema.index_name",
                "source_table_name": "catalog.schema.source_table",
                "embedding_dimension": 1536,
            },
        )


def test_e2e_crud_lifecycle_delta_sync(mock_workspace_client):
    """End-to-end CRUD lifecycle: insert → search → get → list → update → delete."""
    from mem0.vector_stores.configs import VectorStoreConfig
    from mem0.utils.factory import VectorStoreFactory

    vs_config = VectorStoreConfig(
        provider="databricks",
        config={
            "workspace_url": "https://test",
            "access_token": "tok",
            "endpoint_name": "ep",
            "catalog": "cat",
            "schema": "sch",
            "table_name": "tbl",
            "warehouse_name": "test-warehouse",
            "embedding_model_endpoint_name": "emb-ep",
        },
    )
    db = VectorStoreFactory.create("databricks", vs_config.config)

    # INSERT
    db.insert(
        vectors=[[0.1, 0.2]],
        payloads=[{"data": "test memory", "user_id": "u1", "hash": "h1"}],
        ids=["mem-001"],
    )
    insert_sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
    assert "INSERT INTO cat.sch.tbl" in insert_sql
    assert "mem-001" in insert_sql

    # SEARCH
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(
            data_array=[["mem-001", "h1", None, None, "u1", "test memory", None, None, None, 0.95]]
        )
    )
    results = db.search(query="test", vectors=None, limit=5)
    assert len(results) == 1
    assert results[0].id == "mem-001"
    assert results[0].payload["data"] == "test memory"
    search_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert search_kwargs["query_text"] == "test"

    # GET
    mock_workspace_client.vector_search_indexes.query_index.return_value = QueryVectorIndexResponse(
        manifest=ResultManifest(columns=[
            ColumnInfo(name="memory_id"), ColumnInfo(name="hash"),
            ColumnInfo(name="agent_id"), ColumnInfo(name="run_id"),
            ColumnInfo(name="user_id"), ColumnInfo(name="memory"),
            ColumnInfo(name="metadata"), ColumnInfo(name="created_at"),
            ColumnInfo(name="updated_at"),
        ]),
        result=ResultData(data_array=[["mem-001", "h1", None, None, "u1", "test memory", None, None, None]]),
    )
    got = db.get("mem-001")
    assert got.id == "mem-001"
    assert got.payload["data"] == "test memory"
    get_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_text" in get_kwargs
    assert "query_vector" not in get_kwargs

    # LIST
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(
            data_array=[["mem-001", "h1", None, None, "u1", "test memory", None, None, None]]
        )
    )
    listed = db.list(filters={"user_id": "u1"}, limit=10)
    assert len(listed[0]) == 1
    assert listed[0][0].id == "mem-001"
    list_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_text" in list_kwargs
    assert list_kwargs["num_results"] == 10

    # UPDATE
    db.update(vector_id="mem-001", payload={"memory": "updated memory"})
    update_sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
    assert "UPDATE cat.sch.tbl" in update_sql
    assert "mem-001" in update_sql
    assert "updated memory" in update_sql

    # DELETE
    db.delete("mem-001")
    delete_sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
    assert "DELETE FROM cat.sch.tbl" in delete_sql
    assert "mem-001" in delete_sql


def test_e2e_crud_lifecycle_direct_access(mock_workspace_client):
    """End-to-end CRUD lifecycle for DIRECT_ACCESS: insert → search → get → list."""
    from mem0.vector_stores.configs import VectorStoreConfig
    from mem0.utils.factory import VectorStoreFactory

    mock_workspace_client.tables.exists.return_value = SimpleNamespace(table_exists=True)

    vs_config = VectorStoreConfig(
        provider="databricks",
        config={
            "workspace_url": "https://test",
            "access_token": "tok",
            "endpoint_name": "ep",
            "catalog": "cat",
            "schema": "sch",
            "table_name": "tbl",
            "index_type": "DIRECT_ACCESS",
            "embedding_dimension": 4,
            "warehouse_name": "test-warehouse",
            "embedding_model_endpoint_name": "emb-ep",
        },
    )
    db = VectorStoreFactory.create("databricks", vs_config.config)
    assert "embedding" in db.column_names

    # INSERT with vector
    db.insert(
        vectors=[[0.1, 0.2, 0.3, 0.4]],
        payloads=[{"data": "direct memory", "user_id": "u1", "hash": "h1"}],
        ids=["mem-da-001"],
    )
    insert_sql = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs["statement"]
    assert "array(0.1, 0.2, 0.3, 0.4)" in insert_sql

    # SEARCH with vector
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(
            data_array=[["mem-da-001", "h1", None, None, "u1", "direct memory", None, None, None, [0.1, 0.2, 0.3, 0.4], 0.9]]
        )
    )
    results = db.search(query="", vectors=[0.1, 0.2, 0.3, 0.4], limit=5)
    assert len(results) == 1
    search_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_vector" in search_kwargs
    assert "query_text" not in search_kwargs

    # GET — must use query_vector for DIRECT_ACCESS
    mock_workspace_client.vector_search_indexes.query_index.return_value = QueryVectorIndexResponse(
        manifest=ResultManifest(columns=[
            ColumnInfo(name="memory_id"), ColumnInfo(name="hash"),
            ColumnInfo(name="agent_id"), ColumnInfo(name="run_id"),
            ColumnInfo(name="user_id"), ColumnInfo(name="memory"),
            ColumnInfo(name="metadata"), ColumnInfo(name="created_at"),
            ColumnInfo(name="updated_at"), ColumnInfo(name="embedding"),
        ]),
        result=ResultData(data_array=[["mem-da-001", "h1", None, None, "u1", "direct memory", None, None, None, [0.1, 0.2, 0.3, 0.4]]]),
    )
    got = db.get("mem-da-001")
    assert got.id == "mem-da-001"
    get_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_vector" in get_kwargs
    assert get_kwargs["query_vector"] == [0.0] * 4

    # LIST — must use query_vector for DIRECT_ACCESS
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(
            data_array=[["mem-da-001", "h1", None, None, "u1", "direct memory", None, None, None, [0.1, 0.2, 0.3, 0.4]]]
        )
    )
    listed = db.list(limit=5)
    list_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_vector" in list_kwargs
    assert "query_text" not in list_kwargs
