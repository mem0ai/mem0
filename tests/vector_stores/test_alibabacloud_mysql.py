import pytest
import struct
from unittest.mock import Mock, patch

# Create mock modules for mysql and mysql.connector
mock_mysql_connector = Mock()
mock_mysql_connector.connect = Mock()

mock_mysql = Mock()
mock_mysql.connector = mock_mysql_connector

# Patch sys.modules before importing
with patch.dict('sys.modules', {
    'mysql': mock_mysql,
    'mysql.connector': mock_mysql_connector
}):
    from mem0.vector_stores.alibabacloud_mysql import MySQLVector, OutputData


class TestMySQLVector:
    @pytest.fixture
    def mock_mysql_connection(self):
        """Mock MySQL connection and cursor"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        
        with patch.object(mock_mysql_connector, 'connect', return_value=mock_conn):
            yield mock_conn, mock_cursor

    @pytest.fixture
    def mysql_store(self, mock_mysql_connection):
        """Create MySQL vector store instance with mocked connection"""
        mock_conn, mock_cursor = mock_mysql_connection
        
        # Mock list_cols to return empty list initially
        mock_cursor.fetchall.return_value = []
        
        store = MySQLVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_password",
            host="localhost",
            port=3306,
        )
        return store

    def test_init(self, mysql_store):
        """Test MySQL initialization"""
        assert mysql_store.collection_name == "test_collection"
        assert mysql_store.embedding_model_dims == 3
        assert mysql_store.distance_function == "euclidean"
        assert mysql_store.m_value == 16

    def test_init_with_connection_string(self, mock_mysql_connection):
        """Test initialization with connection string"""
        mock_conn, mock_cursor = mock_mysql_connection
        mock_cursor.fetchall.return_value = []
        
        store = MySQLVector(
            dbname="test_db",
            collection_name="test_collection", 
            embedding_model_dims=3,
            user=None,
            password=None,
            host=None,
            port=None,
            connection_string="mysql://user:pass@localhost:3306/testdb"
        )
        
        assert store.connection_params['user'] == 'user'
        assert store.connection_params['password'] == 'pass'
        assert store.connection_params['host'] == 'localhost'
        assert store.connection_params['port'] == 3306


    def test_create_col(self, mysql_store, mock_mysql_connection):
        """Test collection creation"""
        mock_conn, mock_cursor = mock_mysql_connection
        
        mysql_store.create_col()
        
        # Verify SQL execution
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    def test_insert(self, mysql_store, mock_mysql_connection):
        """Test vector insertion"""
        mock_conn, mock_cursor = mock_mysql_connection
        
        vectors = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        payloads = [{"key": "value1"}, {"key": "value2"}]
        ids = ["id1", "id2"]
        
        mysql_store.insert(vectors, payloads, ids)
        
        # Verify execute was called for each vector
        assert mock_cursor.execute.call_count >= 2
        mock_conn.commit.assert_called()

    def test_search(self, mysql_store, mock_mysql_connection):
        """Test vector search"""
        mock_conn, mock_cursor = mock_mysql_connection
        
        # Mock search results
        mock_cursor.fetchall.return_value = [
            ("id1", 0.1, '{"key": "value1"}'),
            ("id2", 0.2, '{"key": "value2"}')
        ]
        
        query_vector = [1.0, 2.0, 3.0]
        results = mysql_store.search("test query", query_vector, limit=2)
        
        assert len(results) == 2
        assert isinstance(results[0], OutputData)
        assert results[0].id == "id1"
        assert results[0].score == 0.1
        assert results[0].payload == {"key": "value1"}

    def test_search_with_filters(self, mysql_store, mock_mysql_connection):
        """Test vector search with filters"""
        mock_conn, mock_cursor = mock_mysql_connection
        mock_cursor.fetchall.return_value = [("id1", 0.1, '{"key": "value1"}')]
        
        query_vector = [1.0, 2.0, 3.0]
        filters = {"category": "test"}
        
        results = mysql_store.search("test query", query_vector, limit=1, filters=filters)
        
        # Verify filter was applied in SQL
        mock_cursor.execute.assert_called()
        call_args = mock_cursor.execute.call_args
        assert "JSON_EXTRACT" in call_args[0][0]

    def test_delete(self, mysql_store, mock_mysql_connection):
        """Test vector deletion"""
        mock_conn, mock_cursor = mock_mysql_connection
        
        mysql_store.delete("test_id")
        
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    def test_update(self, mysql_store, mock_mysql_connection):
        """Test vector update"""
        mock_conn, mock_cursor = mock_mysql_connection
        
        new_vector = [7.0, 8.0, 9.0]
        new_payload = {"updated": "data"}
        
        mysql_store.update("test_id", vector=new_vector, payload=new_payload)
        
        # Should be called twice - once for vector, once for payload
        assert mock_cursor.execute.call_count >= 2
        mock_conn.commit.assert_called()

    def test_get(self, mysql_store, mock_mysql_connection):
        """Test vector retrieval"""
        mock_conn, mock_cursor = mock_mysql_connection
        mock_cursor.fetchone.return_value = ("test_id", b"vector_data", '{"key": "value"}')
        
        result = mysql_store.get("test_id")
        
        assert isinstance(result, OutputData)
        assert result.id == "test_id"
        assert result.payload == {"key": "value"}

    def test_get_not_found(self, mysql_store, mock_mysql_connection):
        """Test vector retrieval when not found"""
        mock_conn, mock_cursor = mock_mysql_connection
        mock_cursor.fetchone.return_value = None
        
        result = mysql_store.get("nonexistent_id")
        
        assert result is None

    def test_list_cols(self, mysql_store, mock_mysql_connection):
        """Test listing collections"""
        mock_conn, mock_cursor = mock_mysql_connection
        mock_cursor.fetchall.return_value = [("table1",), ("table2",)]
        
        collections = mysql_store.list_cols()
        
        assert collections == ["table1", "table2"]

    def test_delete_col(self, mysql_store, mock_mysql_connection):
        """Test collection deletion"""
        mock_conn, mock_cursor = mock_mysql_connection
        
        mysql_store.delete_col()
        
        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called()

    def test_col_info(self, mysql_store, mock_mysql_connection):
        """Test collection info retrieval"""
        mock_conn, mock_cursor = mock_mysql_connection
        mock_cursor.fetchone.side_effect = [
            (100,),  # row count
            ("test_collection", 5.5)  # table info
        ]
        
        info = mysql_store.col_info()
        
        assert info["name"] == "test_collection"
        assert info["count"] == 100
        assert "MB" in info["size"]

    def test_list(self, mysql_store, mock_mysql_connection):
        """Test listing vectors"""
        mock_conn, mock_cursor = mock_mysql_connection
        mock_cursor.fetchall.return_value = [
            ("id1", b"vector1", '{"key": "value1"}'),
            ("id2", b"vector2", '{"key": "value2"}')
        ]
        
        results = mysql_store.list(limit=10)
        
        assert len(results) == 2
        assert all(isinstance(r, OutputData) for r in results)

    def test_reset(self, mysql_store, mock_mysql_connection):
        """Test collection reset"""
        mock_conn, mock_cursor = mock_mysql_connection
        
        mysql_store.reset()
        
        # Should call delete_col and create_col
        assert mock_cursor.execute.call_count >= 2

    def test_import_error(self):
        """Test behavior when mysql.connector is not available"""
        # Test that ImportError is raised during module import when mysql.connector is not available
        with patch.dict('sys.modules', {'mysql.connector': None}):
            with pytest.raises(ImportError, match="mysql.connector is not available"):
                # Force reimport of the module to trigger the ImportError
                import importlib
                import sys
                if 'mem0.vector_stores.alibabacloud_mysql' in sys.modules:
                    del sys.modules['mem0.vector_stores.alibabacloud_mysql']
                importlib.import_module('mem0.vector_stores.alibabacloud_mysql')
