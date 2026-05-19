import json
import uuid
import pytest
from unittest.mock import Mock, patch

from mem0.vector_stores.gaussdb import GaussDB, OutputData


@pytest.fixture(autouse=True)
def mock_jsonb():
    """Mock Jsonb as a passthrough so tests work without the gaussdb driver."""
    with patch("mem0.vector_stores.gaussdb.Jsonb", side_effect=lambda x: x):
        yield


@pytest.fixture
def mock_connection_pool():
    pool = Mock()
    conn = Mock()
    cursor = Mock()

    cursor.fetchall = Mock(return_value=[])
    cursor.fetchone = Mock(return_value=None)
    cursor.execute = Mock()
    cursor.__enter__ = Mock(return_value=cursor)
    cursor.__exit__ = Mock(return_value=False)

    conn.cursor = Mock(return_value=cursor)
    conn.commit = Mock()
    conn.rollback = Mock()
    conn.__enter__ = Mock(return_value=conn)
    conn.__exit__ = Mock(return_value=False)

    pool.connection = Mock(return_value=conn)
    pool.close = Mock()

    return pool, conn, cursor


@pytest.fixture
def gaussdb_instance(mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    with patch("mem0.vector_stores.gaussdb.GAUSSDB_AVAILABLE", True), \
         patch("mem0.vector_stores.gaussdb.ConnectionPool") as MockPool:
        MockPool.return_value = pool
        instance = GaussDB(
            host="localhost",
            port=5432,
            user="test",
            password="test",
            dbname="testdb",
            collection_name="test_col",
            embedding_model_dims=4,
        )
        instance.connection_pool = pool
        return instance


def test_init_creates_pool(mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    with patch("mem0.vector_stores.gaussdb.GAUSSDB_AVAILABLE", True), \
         patch("mem0.vector_stores.gaussdb.ConnectionPool") as MockPool:
        MockPool.return_value = pool
        GaussDB(
            host="localhost", port=5432, user="test", password="test",
            dbname="testdb", collection_name="test_col", embedding_model_dims=4,
        )
        call_kwargs = MockPool.call_args
        conninfo = call_kwargs[0][0]
        assert "localhost" in conninfo
        assert "5432" in conninfo
        assert "test" in conninfo
        assert "testdb" in conninfo


def test_init_with_connection_pool(mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    with patch("mem0.vector_stores.gaussdb.GAUSSDB_AVAILABLE", True), \
         patch("mem0.vector_stores.gaussdb.ConnectionPool") as MockPool:
        GaussDB(
            host="localhost", port=5432, user="test", password="test",
            dbname="testdb", collection_name="test_col", embedding_model_dims=4,
            connection_pool=pool,
        )
        MockPool.assert_not_called()


def test_init_creates_collection_if_not_exists(mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchall.return_value = []
    with patch("mem0.vector_stores.gaussdb.GAUSSDB_AVAILABLE", True), \
         patch("mem0.vector_stores.gaussdb.ConnectionPool") as MockPool:
        MockPool.return_value = pool
        GaussDB(
            host="localhost", port=5432, user="test", password="test",
            dbname="testdb", collection_name="test_col", embedding_model_dims=4,
        )
    sql_calls = " ".join(str(c) for c in cursor.execute.call_args_list)
    assert "CREATE TABLE" in sql_calls


def test_init_skips_create_if_exists(mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchall.return_value = [{"table_name": "test_col"}]
    with patch("mem0.vector_stores.gaussdb.GAUSSDB_AVAILABLE", True), \
         patch("mem0.vector_stores.gaussdb.ConnectionPool") as MockPool:
        MockPool.return_value = pool
        cursor.execute.reset_mock()
        GaussDB(
            host="localhost", port=5432, user="test", password="test",
            dbname="testdb", collection_name="test_col", embedding_model_dims=4,
        )
    sql_calls = " ".join(str(c) for c in cursor.execute.call_args_list)
    assert "CREATE TABLE" not in sql_calls


def test_create_col_without_hnsw(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.execute.reset_mock()
    gaussdb_instance.create_col(name="new_col", vector_size=4)
    sql_calls = " ".join(str(c) for c in cursor.execute.call_args_list)
    assert "CREATE TABLE" in sql_calls
    assert "CREATE INDEX" not in sql_calls


def test_create_col_with_hnsw(mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchall.return_value = [{"table_name": "test_col"}]
    with patch("mem0.vector_stores.gaussdb.GAUSSDB_AVAILABLE", True), \
         patch("mem0.vector_stores.gaussdb.ConnectionPool") as MockPool:
        MockPool.return_value = pool
        instance = GaussDB(
            host="localhost", port=5432, user="test", password="test",
            dbname="testdb", collection_name="test_col", embedding_model_dims=4,
            hnsw=True,
        )
        instance.connection_pool = pool
    cursor.execute.reset_mock()
    instance.create_col(name="new_col", vector_size=4)
    sql_calls = " ".join(str(c) for c in cursor.execute.call_args_list)
    assert "hnsw" in sql_calls.lower()


def test_create_col_with_diskann(mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchall.return_value = [{"table_name": "test_col"}]
    with patch("mem0.vector_stores.gaussdb.GAUSSDB_AVAILABLE", True), \
         patch("mem0.vector_stores.gaussdb.ConnectionPool") as MockPool:
        MockPool.return_value = pool
        instance = GaussDB(
            host="localhost", port=5432, user="test", password="test",
            dbname="testdb", collection_name="test_col", embedding_model_dims=4,
            diskann=True,
        )
        instance.connection_pool = pool
    cursor.execute.reset_mock()
    instance.create_col(name="new_col", vector_size=4)
    sql_calls = " ".join(str(c) for c in cursor.execute.call_args_list)
    assert "diskann" in sql_calls.lower()
    assert "hnsw" not in sql_calls.lower()


def test_create_col_diskann_takes_priority_over_hnsw(mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchall.return_value = [{"table_name": "test_col"}]
    with patch("mem0.vector_stores.gaussdb.GAUSSDB_AVAILABLE", True), \
         patch("mem0.vector_stores.gaussdb.ConnectionPool") as MockPool:
        MockPool.return_value = pool
        instance = GaussDB(
            host="localhost", port=5432, user="test", password="test",
            dbname="testdb", collection_name="test_col", embedding_model_dims=4,
            diskann=True, hnsw=True,
        )
        instance.connection_pool = pool
    cursor.execute.reset_mock()
    instance.create_col(name="new_col", vector_size=4)
    sql_calls = " ".join(str(c) for c in cursor.execute.call_args_list)
    assert "diskann" in sql_calls.lower()
    assert "hnsw" not in sql_calls.lower()


def test_insert_uses_executemany(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.executemany = Mock()
    gaussdb_instance.insert(
        vectors=[[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]],
        payloads=[{"text": "a"}, {"text": "b"}],
        ids=[str(uuid.uuid4()), str(uuid.uuid4())],
    )
    assert cursor.executemany.call_count == 1
    data = cursor.executemany.call_args[0][1]
    assert len(data) == 2


def test_insert_uses_on_duplicate_key_update(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.executemany = Mock()
    gaussdb_instance.insert(vectors=[[0.1, 0.2, 0.3, 0.4]], ids=[str(uuid.uuid4())])
    sql = cursor.executemany.call_args[0][0]
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert "ON CONFLICT" not in sql


def test_insert_generates_ids_if_none(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.executemany = Mock()
    gaussdb_instance.insert(vectors=[[0.1, 0.2, 0.3, 0.4]])
    assert cursor.executemany.call_count == 1
    data = cursor.executemany.call_args[0][1]
    assert data[0][0] is not None  # auto-generated id


def test_search_uses_cosine_operator(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    test_uuid = str(uuid.uuid4())
    cursor.fetchall.return_value = [
        {"id": test_uuid, "distance": 0.1, "payload": json.dumps({"text": "hello"})}
    ]
    results = gaussdb_instance.search(query="test", vectors=[0.1, 0.2, 0.3, 0.4])
    sql = cursor.execute.call_args[0][0]
    assert "<=>" in sql
    assert isinstance(results, list)
    assert isinstance(results[0], OutputData)


def test_search_with_filters(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchall.return_value = []
    gaussdb_instance.search(query="test", vectors=[0.1, 0.2, 0.3, 0.4], filters={"user_id": "alice"})
    sql = cursor.execute.call_args[0][0]
    assert "payload->>" in sql


def test_search_returns_correct_score(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchall.return_value = [
        {"id": str(uuid.uuid4()), "distance": 0.42, "payload": {"text": "hello"}}
    ]
    results = gaussdb_instance.search(query="test", vectors=[0.1, 0.2, 0.3, 0.4])
    assert results[0].score == pytest.approx(0.42)


def test_delete_executes_correct_sql(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.execute.reset_mock()
    test_uuid = str(uuid.uuid4())
    gaussdb_instance.delete(test_uuid)
    sql = cursor.execute.call_args[0][0]
    assert "DELETE FROM" in sql
    assert cursor.execute.call_args[0][1] == (test_uuid,)


def test_update_vector_only(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.execute.reset_mock()
    gaussdb_instance.update(str(uuid.uuid4()), vector=[0.1, 0.2, 0.3, 0.4])
    assert cursor.execute.call_count == 1
    sql = cursor.execute.call_args[0][0]
    assert "vector" in sql
    assert "::vector" in sql


def test_update_payload_only(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.execute.reset_mock()
    gaussdb_instance.update(str(uuid.uuid4()), payload={"text": "updated"})
    assert cursor.execute.call_count == 1
    sql = cursor.execute.call_args[0][0]
    assert "payload" in sql
    assert "vector" not in sql


def test_get_returns_output_data(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    test_uuid = str(uuid.uuid4())
    cursor.fetchone.return_value = {"id": test_uuid, "payload": json.dumps({"text": "hello"})}
    result = gaussdb_instance.get(test_uuid)
    assert isinstance(result, OutputData)
    assert result.id == test_uuid
    assert result.score is None


def test_get_returns_none_if_not_found(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchone.return_value = None
    result = gaussdb_instance.get(str(uuid.uuid4()))
    assert result is None


def test_list_cols_queries_information_schema(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchall.return_value = [{"table_name": "test_col"}]
    cols = gaussdb_instance.list_cols()
    sql = cursor.execute.call_args[0][0]
    assert "information_schema" in sql
    assert "public" in sql
    assert cols == ["test_col"]


def test_delete_col_drops_table(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.execute.reset_mock()
    gaussdb_instance.delete_col()
    sql = cursor.execute.call_args[0][0]
    assert "DROP TABLE IF EXISTS" in sql
    assert "test_col" in sql


def test_col_info_returns_dict(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchone.return_value = {"table_name": "test_col", "row_count": 10, "total_size": "16 kB"}
    info = gaussdb_instance.col_info()
    assert info["name"] == "test_col"
    assert info["count"] == 10
    assert "size" in info


def test_col_info_returns_empty_if_not_found(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchone.return_value = None
    info = gaussdb_instance.col_info()
    assert info == {}


def test_list_with_filters(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.fetchall.return_value = []
    gaussdb_instance.list(filters={"user_id": "alice"})
    sql = cursor.execute.call_args[0][0]
    assert "payload->>" in sql


def test_reset_deletes_and_recreates(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    cursor.execute.reset_mock()
    gaussdb_instance.reset()
    sql_calls = " ".join(str(c) for c in cursor.execute.call_args_list)
    assert "DROP TABLE" in sql_calls
    assert "CREATE TABLE" in sql_calls


def test_del_closes_pool(gaussdb_instance, mock_connection_pool):
    pool, conn, cursor = mock_connection_pool
    gaussdb_instance.__del__()
    pool.close.assert_called_once()


def test_output_data_model():
    test_uuid = str(uuid.uuid4())
    data = OutputData(id=test_uuid, score=0.95, payload={"text": "hello"})
    assert data.id == test_uuid
    assert data.score == 0.95
    assert data.payload == {"text": "hello"}

    empty = OutputData(id=None, score=None, payload=None)
    assert empty.id is None


def test_search_returns_multiple_results_with_correct_fields(gaussdb_instance, mock_connection_pool):
    """Test search returns multiple results with correct id, score, payload."""
    pool, conn, cursor = mock_connection_pool
    uid1, uid2 = str(uuid.uuid4()), str(uuid.uuid4())
    cursor.fetchall.return_value = [
        {"id": uid1, "distance": 0.1, "payload": {"user_id": "alice", "text": "hello"}},
        {"id": uid2, "distance": 0.2, "payload": {"user_id": "alice", "text": "world"}},
    ]
    results = gaussdb_instance.search(query="test", vectors=[0.1, 0.2, 0.3, 0.4], limit=2)
    assert len(results) == 2
    assert results[0].id == uid1
    assert results[0].score == pytest.approx(0.1)
    assert results[0].payload["text"] == "hello"
    assert results[1].id == uid2
    assert results[1].score == pytest.approx(0.2)
    assert results[1].payload["text"] == "world"


def test_search_with_multiple_filters(gaussdb_instance, mock_connection_pool):
    """Test search with multiple filters verifies WHERE clause and payload content."""
    pool, conn, cursor = mock_connection_pool
    uid = str(uuid.uuid4())
    cursor.fetchall.return_value = [
        {"id": uid, "distance": 0.1, "payload": {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}},
    ]
    filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
    results = gaussdb_instance.search(query="test", vectors=[0.1, 0.2, 0.3, 0.4], filters=filters)
    sql = cursor.execute.call_args[0][0]
    assert "WHERE" in sql
    assert sql.count("payload->>") == 3
    assert len(results) == 1
    assert results[0].payload["user_id"] == "alice"
    assert results[0].payload["agent_id"] == "agent1"
    assert results[0].payload["run_id"] == "run1"


def test_search_without_filters_has_no_where(gaussdb_instance, mock_connection_pool):
    """Test search without filters does not include WHERE clause."""
    pool, conn, cursor = mock_connection_pool
    cursor.fetchall.return_value = []
    gaussdb_instance.search(query="test", vectors=[0.1, 0.2, 0.3, 0.4])
    sql = cursor.execute.call_args[0][0]
    assert "WHERE" not in sql


def test_list_without_filters_has_no_where(gaussdb_instance, mock_connection_pool):
    """Test list without filters does not include WHERE clause."""
    pool, conn, cursor = mock_connection_pool
    cursor.fetchall.return_value = []
    gaussdb_instance.list()
    sql = cursor.execute.call_args[0][0]
    assert "WHERE" not in sql


def test_update_both_vector_and_payload(gaussdb_instance, mock_connection_pool):
    """Test updating both vector and payload in a single call."""
    pool, conn, cursor = mock_connection_pool
    cursor.execute.reset_mock()
    gaussdb_instance.update(str(uuid.uuid4()), vector=[0.1, 0.2, 0.3, 0.4], payload={"text": "updated"})
    assert cursor.execute.call_count == 2
    sql_calls = [str(c) for c in cursor.execute.call_args_list]
    assert any("vector" in s and "::vector" in s for s in sql_calls)
    assert any("payload" in s for s in sql_calls)


def test_update_payload_uses_jsonb(gaussdb_instance, mock_connection_pool):
    """Test that update uses Jsonb wrapper for payload serialization."""
    pool, conn, cursor = mock_connection_pool
    cursor.execute.reset_mock()
    test_payload = {"text": "data", "number": 42}
    with patch("mem0.vector_stores.gaussdb.Jsonb") as mock_jsonb_cls:
        mock_jsonb_cls.return_value = "jsonb_wrapped"
        gaussdb_instance.update(str(uuid.uuid4()), payload=test_payload)
        mock_jsonb_cls.assert_called_once_with(test_payload)


def test_insert_payload_uses_jsonb(gaussdb_instance, mock_connection_pool):
    """Test that insert uses Jsonb wrapper for payload serialization."""
    pool, conn, cursor = mock_connection_pool
    cursor.executemany = Mock()
    test_payload = {"text": "hello"}
    with patch("mem0.vector_stores.gaussdb.Jsonb") as mock_jsonb_cls:
        mock_jsonb_cls.return_value = "jsonb_wrapped"
        gaussdb_instance.insert(
            vectors=[[0.1, 0.2, 0.3, 0.4]],
            payloads=[test_payload],
            ids=[str(uuid.uuid4())],
        )
        mock_jsonb_cls.assert_called_once_with(test_payload)


def test_transaction_rollback_on_error(gaussdb_instance, mock_connection_pool):
    """Test that transaction is rolled back when an operation raises an error."""
    pool, conn, cursor = mock_connection_pool
    cursor.execute.side_effect = Exception("Database error")
    with pytest.raises(Exception, match="Database error"):
        gaussdb_instance.delete(str(uuid.uuid4()))
    conn.rollback.assert_called()


def test_transaction_commit_on_success(gaussdb_instance, mock_connection_pool):
    """Test that transaction is committed on successful operation."""
    pool, conn, cursor = mock_connection_pool
    cursor.execute.reset_mock()
    gaussdb_instance.delete(str(uuid.uuid4()))
    conn.commit.assert_called()


def test_init_with_connection_string_and_sslmode(mock_connection_pool):
    """Test initialization with connection_string and sslmode."""
    pool, conn, cursor = mock_connection_pool
    with patch("mem0.vector_stores.gaussdb.GAUSSDB_AVAILABLE", True), \
         patch("mem0.vector_stores.gaussdb.ConnectionPool") as MockPool:
        MockPool.return_value = pool
        GaussDB(
            host="localhost", port=5432, user="test", password="test",
            dbname="testdb", collection_name="test_col", embedding_model_dims=4,
            connection_string="host=myhost port=5432 user=u password=p dbname=d",
            sslmode="require",
        )
        conninfo = MockPool.call_args[0][0]
        assert "myhost" in conninfo
        assert "sslmode=require" in conninfo


def test_config_requires_password_without_dsn():
    from mem0.configs.vector_stores.gaussdb import GaussDBConfig
    with pytest.raises(ValueError):
        GaussDBConfig(host="h", user="u", dbname="d")


def test_config_accepts_connection_string():
    from mem0.configs.vector_stores.gaussdb import GaussDBConfig
    cfg = GaussDBConfig(connection_string="host=h user=u dbname=d password=p")
    assert cfg.connection_string is not None


def test_config_rejects_extra_fields():
    from mem0.configs.vector_stores.gaussdb import GaussDBConfig
    with pytest.raises(ValueError, match="Extra fields"):
        GaussDBConfig(host="h", user="u", dbname="d", password="p", unknown_field="x")
