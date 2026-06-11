from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("databricks", reason="databricks-sdk package not installed")

from databricks.sdk.service.vectorsearch import (
    ColumnInfo,
    QueryVectorIndexResponse,
    ResultData,
    ResultManifest,
    VectorIndexType,
)

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
    # Embedding list rendered inline (ARRAY type not supported by parameterized queries)
    assert "array(0.1, 0.2, 0.3, 0.4)" in sql
    # User-supplied values should use parameterized queries, not inline values
    assert ":memory_id_0" in sql
    assert "id1" not in sql  # id should be in params, not in SQL
    params = kwargs["parameters"]
    param_names = {p.name for p in params}
    assert "memory_id_0" in param_names
    id_param = next(p for p in params if p.name == "memory_id_0")
    assert id_param.value == "id1"


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
    results = db_instance_delta.search(query="hello", vectors=None, top_k=1)
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
    results = db_instance_direct.search(query="", vectors=[0.1, 0.2, 0.3, 0.4], top_k=1)
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
    inst.search(query="ignored", vectors=[0.1, 0.2, 0.3, 0.4], top_k=5)
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
    assert "DELETE FROM" in sql
    assert ":vector_id" in sql
    assert "id-delete" not in sql  # value should be in params, not in SQL
    params = kwargs["parameters"]
    assert len(params) == 1
    assert params[0].name == "vector_id"
    assert params[0].value == "id-delete"


# ---------------------- Update Tests ---------------------- #


def test_update_vector(db_instance_direct, mock_workspace_client):
    db_instance_direct.update(
        vector_id="id-upd",
        vector=[0.4, 0.5, 0.6, 0.7],
        payload={"custom": "val", "user_id": "skip"},  # user_id should be excluded
    )
    args, kwargs = mock_workspace_client.statement_execution.execute_statement.call_args
    sql = kwargs.get("statement") or args[0]
    assert "UPDATE" in sql
    assert "embedding = array(0.4, 0.5, 0.6, 0.7)" in sql
    assert "custom = :payload_custom" in sql
    assert ":vector_id" in sql
    assert "id-upd" not in sql  # value should be in params, not in SQL
    assert "'val'" not in sql  # value should be in params, not in SQL
    assert "user_id" not in sql  # excluded
    params = kwargs["parameters"]
    param_map = {p.name: p.value for p in params}
    assert param_map["payload_custom"] == "val"
    assert param_map["vector_id"] == "id-upd"


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
    res = db_instance_delta.list(top_k=1)
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
    res = db_instance_direct.list(top_k=5)
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
    inst.list(top_k=5)
    call_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_vector" in call_kwargs
    assert "query_text" not in call_kwargs


def test_list_memories_default_limit(db_instance_delta, mock_workspace_client):
    """list() with no limit should default to 100."""
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(data_array=[])
    )
    db_instance_delta.list(top_k=None)
    call_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert call_kwargs["num_results"] == 100


# ---------------------- Table Creation Tests ---------------------- #


def test_ensure_source_table_uses_dynamic_names(mock_workspace_client):
    """Verify _ensure_source_table_exists uses self.fully_qualified_table_name and
    self.table_name for the PK constraint, not hardcoded values."""
    mock_workspace_client.tables.exists.return_value = SimpleNamespace(table_exists=False)
    Databricks(
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
    from mem0.utils.factory import VectorStoreFactory
    from mem0.vector_stores.configs import VectorStoreConfig

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
    from mem0.utils.factory import VectorStoreFactory
    from mem0.vector_stores.configs import VectorStoreConfig

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
    from mem0.utils.factory import VectorStoreFactory
    from mem0.vector_stores.configs import VectorStoreConfig

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
    insert_call = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    insert_sql = insert_call["statement"]
    assert "INSERT INTO cat.sch.tbl" in insert_sql
    assert ":memory_id_0" in insert_sql  # parameterized, not inline
    insert_params = {p.name: p.value for p in insert_call["parameters"]}
    assert insert_params["memory_id_0"] == "mem-001"

    # SEARCH
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(
            data_array=[["mem-001", "h1", None, None, "u1", "test memory", None, None, None, 0.95]]
        )
    )
    results = db.search(query="test", vectors=None, top_k=5)
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
    listed = db.list(filters={"user_id": "u1"}, top_k=10)
    assert len(listed[0]) == 1
    assert listed[0][0].id == "mem-001"
    list_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_text" in list_kwargs
    assert list_kwargs["num_results"] == 10

    # UPDATE
    db.update(vector_id="mem-001", payload={"memory": "updated memory"})
    update_call = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    update_sql = update_call["statement"]
    assert "UPDATE cat.sch.tbl" in update_sql
    assert ":vector_id" in update_sql
    assert ":payload_memory" in update_sql
    update_params = {p.name: p.value for p in update_call["parameters"]}
    assert update_params["vector_id"] == "mem-001"
    assert update_params["payload_memory"] == "updated memory"

    # DELETE
    db.delete("mem-001")
    delete_call = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    delete_sql = delete_call["statement"]
    assert "DELETE FROM cat.sch.tbl" in delete_sql
    assert ":vector_id" in delete_sql
    delete_params = {p.name: p.value for p in delete_call["parameters"]}
    assert delete_params["vector_id"] == "mem-001"


def test_e2e_crud_lifecycle_direct_access(mock_workspace_client):
    """End-to-end CRUD lifecycle for DIRECT_ACCESS: insert → search → get → list."""
    from mem0.utils.factory import VectorStoreFactory
    from mem0.vector_stores.configs import VectorStoreConfig

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
    insert_call = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    insert_sql = insert_call["statement"]
    assert "array(0.1, 0.2, 0.3, 0.4)" in insert_sql
    insert_params = {p.name: p.value for p in insert_call["parameters"]}
    assert insert_params["memory_id_0"] == "mem-da-001"

    # SEARCH with vector
    mock_workspace_client.vector_search_indexes.query_index.return_value = SimpleNamespace(
        result=SimpleNamespace(
            data_array=[["mem-da-001", "h1", None, None, "u1", "direct memory", None, None, None, [0.1, 0.2, 0.3, 0.4], 0.9]]
        )
    )
    results = db.search(query="", vectors=[0.1, 0.2, 0.3, 0.4], top_k=5)
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
    db.list(top_k=5)
    list_kwargs = mock_workspace_client.vector_search_indexes.query_index.call_args.kwargs
    assert "query_vector" in list_kwargs
    assert "query_text" not in list_kwargs


# ---------------------- SQL Injection Prevention Tests (Issue #4073) ---------------------- #


SQLI_PAYLOADS = [
    "'; DELETE FROM table; --",
    "' OR '1'='1",
    "'; DROP TABLE memories; --",
    "1' UNION SELECT * FROM secrets --",
]


@pytest.mark.parametrize("malicious_id", SQLI_PAYLOADS)
def test_delete_prevents_sql_injection(db_instance_delta, mock_workspace_client, malicious_id):
    """Verify delete() uses parameterized queries so SQL injection payloads are never in the SQL string."""
    db_instance_delta.delete(malicious_id)
    kwargs = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    sql = kwargs["statement"]
    # The malicious payload must NOT appear in the SQL statement itself
    assert malicious_id not in sql
    assert ":vector_id" in sql
    # It should be safely passed as a parameter
    assert kwargs["parameters"][0].value == malicious_id


@pytest.mark.parametrize("malicious_id", SQLI_PAYLOADS)
def test_update_prevents_sql_injection_in_vector_id(db_instance_delta, mock_workspace_client, malicious_id):
    """Verify update() parameterizes vector_id."""
    db_instance_delta.update(vector_id=malicious_id, payload={"memory": "safe value"})
    kwargs = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    sql = kwargs["statement"]
    assert malicious_id not in sql
    assert ":vector_id" in sql
    param_map = {p.name: p.value for p in kwargs["parameters"]}
    assert param_map["vector_id"] == malicious_id


@pytest.mark.parametrize("malicious_value", SQLI_PAYLOADS)
def test_update_prevents_sql_injection_in_payload(db_instance_delta, mock_workspace_client, malicious_value):
    """Verify update() parameterizes payload values."""
    db_instance_delta.update(vector_id="safe-id", payload={"memory": malicious_value})
    kwargs = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    sql = kwargs["statement"]
    assert malicious_value not in sql
    assert ":payload_memory" in sql
    param_map = {p.name: p.value for p in kwargs["parameters"]}
    assert param_map["payload_memory"] == malicious_value


@pytest.mark.parametrize("malicious_id", SQLI_PAYLOADS)
def test_insert_prevents_sql_injection_in_ids(db_instance_delta, mock_workspace_client, malicious_id):
    """Verify insert() parameterizes memory IDs."""
    db_instance_delta.insert(
        vectors=[[0.1, 0.2]],
        payloads=[{"data": "test", "hash": "h1"}],
        ids=[malicious_id],
    )
    kwargs = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    sql = kwargs["statement"]
    assert malicious_id not in sql
    assert ":memory_id_0" in sql
    param_map = {p.name: p.value for p in kwargs["parameters"]}
    assert param_map["memory_id_0"] == malicious_id


@pytest.mark.parametrize("malicious_data", SQLI_PAYLOADS)
def test_insert_prevents_sql_injection_in_payload_data(db_instance_delta, mock_workspace_client, malicious_data):
    """Verify insert() parameterizes payload data values."""
    db_instance_delta.insert(
        vectors=[[0.1, 0.2]],
        payloads=[{"data": malicious_data, "hash": "h1"}],
        ids=["safe-id"],
    )
    kwargs = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    sql = kwargs["statement"]
    assert malicious_data not in sql
    param_map = {p.name: p.value for p in kwargs["parameters"]}
    assert param_map["memory_0"] == malicious_data


@pytest.mark.parametrize("malicious_key", [
    "memory; DROP TABLE x--",
    "col' OR '1'='1",
    "valid_col; DELETE FROM t",
    "col\nname",
])
def test_update_rejects_malicious_column_names(db_instance_delta, mock_workspace_client, malicious_key):
    """Verify update() skips payload keys that are not valid SQL identifiers."""
    db_instance_delta.update(
        vector_id="safe-id",
        payload={malicious_key: "some value", "memory": "legit"},
    )
    kwargs = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    sql = kwargs["statement"]
    # The malicious key must NOT appear as a column name in the SQL
    assert malicious_key not in sql
    # The legitimate key should still be present
    assert ":payload_memory" in sql


def test_insert_multi_row(db_instance_delta, mock_workspace_client):
    """Verify multi-row insert generates unique parameter names per row."""
    db_instance_delta.insert(
        vectors=[[0.1, 0.2], [0.3, 0.4]],
        payloads=[
            {"data": "first memory", "hash": "h1"},
            {"data": "second memory", "hash": "h2"},
        ],
        ids=["id-1", "id-2"],
    )
    kwargs = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    sql = kwargs["statement"]
    params = kwargs["parameters"]
    param_map = {p.name: p.value for p in params}
    # Each row should have distinct parameter names
    assert ":memory_id_0" in sql
    assert ":memory_id_1" in sql
    assert param_map["memory_id_0"] == "id-1"
    assert param_map["memory_id_1"] == "id-2"
    assert param_map["memory_0"] == "first memory"
    assert param_map["memory_1"] == "second memory"


def test_insert_with_none_values(db_instance_delta, mock_workspace_client):
    """Verify insert() uses NULL literal for None values, not parameters."""
    db_instance_delta.insert(
        vectors=[[0.1, 0.2]],
        payloads=[{"data": "test", "hash": "h1"}],  # agent_id, run_id etc will be None
        ids=["id-1"],
    )
    kwargs = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    sql = kwargs["statement"]
    assert "NULL" in sql  # None values should be literal NULL
    # Only non-None values should have parameters
    param_names = {p.name for p in kwargs["parameters"]}
    assert "memory_id_0" in param_names
    assert "memory_0" in param_names
    assert "hash_0" in param_names


def test_update_payload_only(db_instance_delta, mock_workspace_client):
    """Verify update() works with payload only (no vector)."""
    db_instance_delta.update(vector_id="id-1", payload={"memory": "new text"})
    kwargs = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    sql = kwargs["statement"]
    assert "UPDATE" in sql
    assert "embedding" not in sql
    assert ":payload_memory" in sql
    assert ":vector_id" in sql


def test_update_vector_only(db_instance_direct, mock_workspace_client):
    """Verify update() works with vector only (no payload)."""
    db_instance_direct.update(vector_id="id-1", vector=[0.1, 0.2, 0.3, 0.4])
    kwargs = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    sql = kwargs["statement"]
    assert "UPDATE" in sql
    assert "embedding = array(0.1, 0.2, 0.3, 0.4)" in sql
    assert ":vector_id" in sql
    param_map = {p.name: p.value for p in kwargs["parameters"]}
    assert param_map["vector_id"] == "id-1"
    assert len(kwargs["parameters"]) == 1  # only vector_id param


def test_insert_timestamp_params_have_explicit_type(db_instance_delta, mock_workspace_client):
    """Verify insert() sets type='TIMESTAMP' on created_at/updated_at parameters
    so Databricks doesn't rely on implicit STRING->TIMESTAMP casting."""
    db_instance_delta.insert(
        vectors=[[0.1, 0.2]],
        payloads=[{
            "data": "test",
            "hash": "h1",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-02T00:00:00+00:00",
        }],
        ids=["id-1"],
    )
    kwargs = mock_workspace_client.statement_execution.execute_statement.call_args.kwargs
    params = kwargs["parameters"]
    ts_params = [p for p in params if "created_at" in p.name or "updated_at" in p.name]
    assert len(ts_params) == 2
    for p in ts_params:
        assert p.type == "TIMESTAMP", f"Parameter {p.name} should have type=TIMESTAMP, got {p.type}"
    # Non-timestamp params should not have a type set (defaults to STRING)
    non_ts_params = [p for p in params if "created_at" not in p.name and "updated_at" not in p.name]
    for p in non_ts_params:
        assert p.type is None, f"Parameter {p.name} should not have explicit type, got {p.type}"
