import unittest
import uuid
from unittest.mock import MagicMock, patch

from mem0.vector_stores.pgvector import PGVector


class TestPGVector(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        
        # Mock connection pool
        self.mock_pool = MagicMock()
        self.mock_pool.getconn.return_value = self.mock_conn
        
        # Mock connection string
        self.connection_string = "postgresql://user:pass@host:5432/db"
        
        # Test data
        self.test_vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        self.test_payloads = [{"key": "value1"}, {"key": "value2"}]
        self.test_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_init_with_individual_params_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test initialization with individual parameters using psycopg3."""
        # Mock psycopg3 to be available
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        mock_psycopg_connect.assert_called_once_with(
            dbname="test_db",
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432
        )
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_init_with_individual_params_psycopg2(self, mock_connect):
        """Test initialization with individual parameters using psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        mock_connect.assert_called_once_with(
            dbname="test_db",
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432
        )
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_create_col_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test collection creation with psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        # Verify vector extension and table creation
        self.mock_cursor.execute.assert_any_call("CREATE EXTENSION IF NOT EXISTS vector")
        table_creation_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "CREATE TABLE IF NOT EXISTS test_collection" in str(call)]
        self.assertTrue(len(table_creation_calls) > 0)
        self.mock_conn.commit.assert_called()
        
        # Verify pgvector instance properties
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_create_col_psycopg2(self, mock_connect):
        """Test collection creation with psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        # Verify vector extension and table creation
        self.mock_cursor.execute.assert_any_call("CREATE EXTENSION IF NOT EXISTS vector")
        table_creation_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "CREATE TABLE IF NOT EXISTS test_collection" in str(call)]
        self.assertTrue(len(table_creation_calls) > 0)
        self.mock_conn.commit.assert_called()
        
        # Verify pgvector instance properties
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    @patch('mem0.vector_stores.pgvector.execute_values')
    def test_insert_psycopg3(self, mock_execute_values, mock_psycopg2_connect, mock_psycopg_connect):
        """Test vector insertion with psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        pgvector.insert(self.test_vectors, self.test_payloads, self.test_ids)
        
        # Verify execute_values was called
        mock_execute_values.assert_called_once()
        call_args = mock_execute_values.call_args
        self.assertIn("INSERT INTO test_collection", call_args[0][1])
        
        # Verify data format
        data_arg = call_args[0][2]
        self.assertEqual(len(data_arg), 2)
        self.assertEqual(data_arg[0][0], self.test_ids[0])
        self.assertEqual(data_arg[1][0], self.test_ids[1])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    @patch('mem0.vector_stores.pgvector.execute_values')
    def test_insert_psycopg2(self, mock_execute_values, mock_connect):
        """Test vector insertion with psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        pgvector.insert(self.test_vectors, self.test_payloads, self.test_ids)
        
        # Verify execute_values was called
        mock_execute_values.assert_called_once()
        call_args = mock_execute_values.call_args
        self.assertIn("INSERT INTO test_collection", call_args[0][1])
        
        # Verify data format
        data_arg = call_args[0][2]
        self.assertEqual(len(data_arg), 2)
        self.assertEqual(data_arg[0][0], self.test_ids[0])
        self.assertEqual(data_arg[1][0], self.test_ids[1])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_search_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test search with psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"key": "value1"}),
            (self.test_ids[1], 0.2, {"key": "value2"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2)
        
        # Verify search query was executed
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].score, 0.1)
        self.assertEqual(results[1].id, self.test_ids[1])
        self.assertEqual(results[1].score, 0.2)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_search_psycopg2(self, mock_connect):
        """Test search with psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"key": "value1"}),
            (self.test_ids[1], 0.2, {"key": "value2"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2)
        
        # Verify search query was executed
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].score, 0.1)
        self.assertEqual(results[1].id, self.test_ids[1])
        self.assertEqual(results[1].score, 0.2)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_delete_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test delete with psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        pgvector.delete(self.test_ids[0])
        
        # Verify delete query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DELETE FROM test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)
        self.mock_conn.commit.assert_called()

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_delete_psycopg2(self, mock_connect):
        """Test delete with psycopg2."""
        mock_connect.return_value = self.mock_conn
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        pgvector.delete(self.test_ids[0])
        
        # Verify delete query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DELETE FROM test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)
        self.mock_conn.commit.assert_called()

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_update_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test update with psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        updated_vector = [0.5, 0.6, 0.7]
        updated_payload = {"updated": "value"}
        
        pgvector.update(self.test_ids[0], vector=updated_vector, payload=updated_payload)
        
        # Verify update queries were executed
        update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "UPDATE test_collection" in str(call)]
        self.assertTrue(len(update_calls) > 0)
        self.mock_conn.commit.assert_called()

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_update_psycopg2(self, mock_connect):
        """Test update with psycopg2."""
        mock_connect.return_value = self.mock_conn
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        updated_vector = [0.5, 0.6, 0.7]
        updated_payload = {"updated": "value"}
        
        pgvector.update(self.test_ids[0], vector=updated_vector, payload=updated_payload)
        
        # Verify update queries were executed
        update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "UPDATE test_collection" in str(call)]
        self.assertTrue(len(update_calls) > 0)
        self.mock_conn.commit.assert_called()

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_get_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test get with psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchone.return_value = (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"})
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        result = pgvector.get(self.test_ids[0])
        
        # Verify get query was executed
        get_calls = [call for call in self.mock_cursor.execute.call_args_list 
                    if "SELECT id, vector, payload" in str(call)]
        self.assertTrue(len(get_calls) > 0)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.test_ids[0])
        self.assertEqual(result.payload, {"key": "value1"})

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_get_psycopg2(self, mock_connect):
        """Test get with psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchone.return_value = (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"})
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        result = pgvector.get(self.test_ids[0])
        
        # Verify get query was executed
        get_calls = [call for call in self.mock_cursor.execute.call_args_list 
                    if "SELECT id, vector, payload" in str(call)]
        self.assertTrue(len(get_calls) > 0)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.test_ids[0])
        self.assertEqual(result.payload, {"key": "value1"})

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list_cols_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test list_cols with psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",), ("other_table",)]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        collections = pgvector.list_cols()
        
        # Verify list_cols query was executed
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name FROM information_schema.tables" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify result
        self.assertEqual(collections, ["test_collection", "other_table"])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list_cols_psycopg2(self, mock_connect):
        """Test list_cols with psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",), ("other_table",)]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        collections = pgvector.list_cols()
        
        # Verify list_cols query was executed
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name FROM information_schema.tables" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify result
        self.assertEqual(collections, ["test_collection", "other_table"])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_delete_col_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test delete_col with psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        pgvector.delete_col()
        
        # Verify delete_col query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DROP TABLE IF EXISTS test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)
        self.mock_conn.commit.assert_called()

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_delete_col_psycopg2(self, mock_connect):
        """Test delete_col with psycopg2."""
        mock_connect.return_value = self.mock_conn
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        pgvector.delete_col()
        
        # Verify delete_col query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DROP TABLE IF EXISTS test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)
        self.mock_conn.commit.assert_called()

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_col_info_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test col_info with psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchone.return_value = ("test_collection", 100, "1 MB")
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        info = pgvector.col_info()
        
        # Verify col_info query was executed
        info_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name" in str(call)]
        self.assertTrue(len(info_calls) > 0)
        
        # Verify result
        self.assertEqual(info["name"], "test_collection")
        self.assertEqual(info["count"], 100)
        self.assertEqual(info["size"], "1 MB")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_col_info_psycopg2(self, mock_connect):
        """Test col_info with psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchone.return_value = ("test_collection", 100, "1 MB")
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        info = pgvector.col_info()
        
        # Verify col_info query was executed
        info_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name" in str(call)]
        self.assertTrue(len(info_calls) > 0)
        
        # Verify result
        self.assertEqual(info["name"], "test_collection")
        self.assertEqual(info["count"], 100)
        self.assertEqual(info["size"], "1 MB")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test list with psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"}),
            (self.test_ids[1], [0.4, 0.5, 0.6], {"key": "value2"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        results = pgvector.list(limit=2)
        
        # Verify list query was executed
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify result
        self.assertEqual(len(results), 1)  # Returns list of lists
        self.assertEqual(len(results[0]), 2)
        self.assertEqual(results[0][0].id, self.test_ids[0])
        self.assertEqual(results[0][1].id, self.test_ids[1])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list_psycopg2(self, mock_connect):
        """Test list with psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"}),
            (self.test_ids[1], [0.4, 0.5, 0.6], {"key": "value2"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        results = pgvector.list(limit=2)
        
        # Verify list query was executed
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify result
        self.assertEqual(len(results), 1)  # Returns list of lists
        self.assertEqual(len(results[0]), 2)
        self.assertEqual(results[0][0].id, self.test_ids[0])
        self.assertEqual(results[0][1].id, self.test_ids[1])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_search_with_filters_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test search with filters using psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify search query was executed with filters
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].score, 0.1)
        self.assertEqual(results[0].payload["user_id"], "alice")
        self.assertEqual(results[0].payload["agent_id"], "agent1")
        self.assertEqual(results[0].payload["run_id"], "run1")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_search_with_filters_psycopg2(self, mock_connect):
        """Test search with filters using psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify search query was executed with filters
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].score, 0.1)
        self.assertEqual(results[0].payload["user_id"], "alice")
        self.assertEqual(results[0].payload["agent_id"], "agent1")
        self.assertEqual(results[0].payload["run_id"], "run1")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_search_with_single_filter_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test search with single filter using psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"user_id": "alice"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify search query was executed with single filter
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].score, 0.1)
        self.assertEqual(results[0].payload["user_id"], "alice")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_search_with_single_filter_psycopg2(self, mock_connect):
        """Test search with single filter using psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"user_id": "alice"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify search query was executed with single filter
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].score, 0.1)
        self.assertEqual(results[0].payload["user_id"], "alice")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_search_with_no_filters_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test search with no filters using psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"key": "value1"}),
            (self.test_ids[1], 0.2, {"key": "value2"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=None)
        
        # Verify search query was executed without WHERE clause
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" not in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].score, 0.1)
        self.assertEqual(results[1].id, self.test_ids[1])
        self.assertEqual(results[1].score, 0.2)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_search_with_no_filters_psycopg2(self, mock_connect):
        """Test search with no filters using psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"key": "value1"}),
            (self.test_ids[1], 0.2, {"key": "value2"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=None)
        
        # Verify search query was executed without WHERE clause
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" not in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].score, 0.1)
        self.assertEqual(results[1].id, self.test_ids[1])
        self.assertEqual(results[1].score, 0.2)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list_with_filters_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test list with filters using psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"user_id": "alice", "agent_id": "agent1"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify list query was executed with filters
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)  # Returns list of lists
        self.assertEqual(len(results[0]), 1)
        self.assertEqual(results[0][0].id, self.test_ids[0])
        self.assertEqual(results[0][0].payload["user_id"], "alice")
        self.assertEqual(results[0][0].payload["agent_id"], "agent1")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list_with_filters_psycopg2(self, mock_connect):
        """Test list with filters using psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"user_id": "alice", "agent_id": "agent1"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify list query was executed with filters
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)  # Returns list of lists
        self.assertEqual(len(results[0]), 1)
        self.assertEqual(results[0][0].id, self.test_ids[0])
        self.assertEqual(results[0][0].payload["user_id"], "alice")
        self.assertEqual(results[0][0].payload["agent_id"], "agent1")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list_with_single_filter_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test list with single filter using psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"user_id": "alice"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify list query was executed with single filter
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)  # Returns list of lists
        self.assertEqual(len(results[0]), 1)
        self.assertEqual(results[0][0].id, self.test_ids[0])
        self.assertEqual(results[0][0].payload["user_id"], "alice")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list_with_single_filter_psycopg2(self, mock_connect):
        """Test list with single filter using psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"user_id": "alice"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify list query was executed with single filter
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)  # Returns list of lists
        self.assertEqual(len(results[0]), 1)
        self.assertEqual(results[0][0].id, self.test_ids[0])
        self.assertEqual(results[0][0].payload["user_id"], "alice")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list_with_no_filters_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test list with no filters using psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"}),
            (self.test_ids[1], [0.4, 0.5, 0.6], {"key": "value2"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        results = pgvector.list(filters=None, limit=2)
        
        # Verify list query was executed without WHERE clause
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" not in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)  # Returns list of lists
        self.assertEqual(len(results[0]), 2)
        self.assertEqual(results[0][0].id, self.test_ids[0])
        self.assertEqual(results[0][1].id, self.test_ids[1])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list_with_no_filters_psycopg2(self, mock_connect):
        """Test list with no filters using psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"}),
            (self.test_ids[1], [0.4, 0.5, 0.6], {"key": "value2"}),
        ]
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        results = pgvector.list(filters=None, limit=2)
        
        # Verify list query was executed without WHERE clause
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" not in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)  # Returns list of lists
        self.assertEqual(len(results[0]), 2)
        self.assertEqual(results[0][0].id, self.test_ids[0])
        self.assertEqual(results[0][1].id, self.test_ids[1])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.psycopg.connect')
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_reset_psycopg3(self, mock_psycopg2_connect, mock_psycopg_connect):
        """Test reset with psycopg3."""
        mock_psycopg_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        pgvector.reset()
        
        # Verify reset operations were executed
        drop_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "DROP TABLE IF EXISTS" in str(call)]
        create_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "CREATE TABLE IF NOT EXISTS" in str(call)]
        self.assertTrue(len(drop_calls) > 0)
        self.assertTrue(len(create_calls) > 0)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_reset_psycopg2(self, mock_connect):
        """Test reset with psycopg2."""
        mock_connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False
        )
        
        pgvector.reset()
        
        # Verify reset operations were executed
        drop_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "DROP TABLE IF EXISTS" in str(call)]
        create_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "CREATE TABLE IF NOT EXISTS" in str(call)]
        self.assertTrue(len(drop_calls) > 0)
        self.assertTrue(len(create_calls) > 0)

    def tearDown(self):
        """Clean up after each test."""
        pass
