from unittest.mock import Mock, patch

import pytest

from mem0.vector_stores.tidb import OutputData, TiDB


@pytest.fixture
def mock_connection():
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value = cursor
    return conn, cursor


@pytest.fixture
def tidb_store(mock_connection):
    conn, cursor = mock_connection
    cursor.fetchall.return_value = []  # Empty collections list

    with patch("pymysql.connect", return_value=conn):
        store = TiDB(
            host="localhost",
            port=4000,
            user="testuser",
            password="testpass",
            database="testdb",
            collection_name="test_collection",
            embedding_model_dims=384,
        )
        return store, cursor


class TestTiDB:
    def test_init_creates_collection(self, mock_connection):
        conn, cursor = mock_connection
        cursor.fetchall.return_value = []

        with patch("pymysql.connect", return_value=conn):
            _ = TiDB(
                host="localhost",
                port=4000,
                user="testuser",
                password="testpass",
                database="testdb",
                collection_name="test_collection",
                embedding_model_dims=384,
            )

        assert any("`test_collection`" in str(call) for call in cursor.execute.call_args_list)

    def test_create_col(self, tidb_store):
        store, cursor = tidb_store
        cursor.execute.reset_mock()

        store.create_col(768)

        cursor.execute.assert_called_once()
        call_args = cursor.execute.call_args[0][0]
        assert "`test_collection`" in call_args
        assert "VECTOR(768)" in call_args

    def test_search(self, tidb_store):
        store, cursor = tidb_store
        cursor.execute.reset_mock()
        cursor.fetchall.return_value = [("id1", 0.1, '{"key": "value1"}'), ("id2", 0.2, '{"key": "value2"}')]

        results = store.search([1.0, 2.0, 3.0], limit=2)

        assert len(results) == 2
        assert isinstance(results[0], OutputData)
        assert results[0].id == "id1"
        assert results[0].score == 0.1
        assert results[0].payload == {"key": "value1"}

    def test_delete(self, tidb_store):
        store, cursor = tidb_store
        cursor.execute.reset_mock()

        store.delete("test-id")

        cursor.execute.assert_called_with("DELETE FROM test_collection WHERE id = %s", ("test-id",))

    def test_get(self, tidb_store):
        store, cursor = tidb_store
        cursor.execute.reset_mock()
        cursor.fetchone.return_value = ("test-id", "[1.0,2.0,3.0]", '{"key": "value"}')

        result = store.get("test-id")

        assert isinstance(result, OutputData)
        assert result.id == "test-id"
        assert result.score is None
        assert result.payload == {"key": "value"}

    def test_list_cols(self, tidb_store):
        store, cursor = tidb_store
        cursor.execute.reset_mock()
        cursor.fetchall.return_value = [("collection1",), ("collection2",)]

        cols = store.list_cols()

        assert cols == ["collection1", "collection2"]

    def test_delete_col(self, tidb_store):
        store, cursor = tidb_store
        cursor.execute.reset_mock()

        store.delete_col()

        cursor.execute.assert_called_with("DROP TABLE IF EXISTS test_collection")

    def test_col_info(self, tidb_store):
        store, cursor = tidb_store
        cursor.execute.reset_mock()
        cursor.fetchone.return_value = ("test_collection", 100, 4096)

        info = store.col_info()

        assert info == {"name": "test_collection", "count": 100, "size": 4096}

    def test_list(self, tidb_store):
        store, cursor = tidb_store
        cursor.execute.reset_mock()
        cursor.fetchall.return_value = [
            ("id1", "[1.0,2.0,3.0]", '{"key": "value1"}'),
            ("id2", "[4.0,5.0,6.0]", '{"key": "value2"}'),
        ]

        results = store.list(limit=10)

        assert len(results) == 2
        assert isinstance(results[0], OutputData)
        assert results[0].id == "id1"
        assert results[0].payload == {"key": "value1"}
