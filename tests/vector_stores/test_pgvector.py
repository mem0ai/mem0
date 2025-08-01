import unittest
import uuid
from unittest.mock import MagicMock, patch

from mem0.vector_stores.pgvector import OutputData, PGVector


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

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_init_with_individual_params(self, mock_connect):
        """Test initialization with individual parameters."""
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

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_create_col(self, mock_connect):
        """Test collection creation."""
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

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    @patch('mem0.vector_stores.pgvector.execute_values')
    def test_insert(self, mock_execute_values, mock_connect):
        """Test vector insertion."""
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
        
        pgvector.insert(
            vectors=self.test_vectors,
            payloads=self.test_payloads,
            ids=self.test_ids
        )
        
        # Verify execute_values was called
        mock_execute_values.assert_called_once()
        self.mock_conn.commit.assert_called()

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_search(self, mock_connect):
        """Test vector search."""
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
        
        # Mock search results with parsed JSON payloads
        mock_results = [
            (self.test_ids[0], 0.1, self.test_payloads[0]),
            (self.test_ids[1], 0.2, self.test_payloads[1])
        ]
        self.mock_cursor.fetchall.return_value = mock_results
        
        results = pgvector.search(
            query="test query",
            vectors=[0.1, 0.2, 0.3],
            limit=2
        )
        
        # Verify search query was called
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=> %s::vector AS distance, payload" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], OutputData)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].score, 0.1)

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_delete(self, mock_connect):
        """Test vector deletion."""
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
        
        vector_id = str(uuid.uuid4())
        pgvector.delete(vector_id)
        
        self.mock_cursor.execute.assert_called_with(
            "DELETE FROM test_collection WHERE id = %s",
            (vector_id,)
        )
        self.mock_conn.commit.assert_called()

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_update(self, mock_connect):
        """Test vector and payload update."""
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
        
        vector_id = str(uuid.uuid4())
        updated_vector = [0.5, 0.6, 0.7]
        updated_payload = {"key": "updated_value"}
        
        pgvector.update(vector_id, vector=updated_vector, payload=updated_payload)
        
        # Check that update was called with vector and payload
        update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "UPDATE test_collection SET vector = %s WHERE id = %s" in str(call) or
                          "UPDATE test_collection SET payload = %s WHERE id = %s" in str(call)]
        self.assertTrue(len(update_calls) > 0)
        self.mock_conn.commit.assert_called()

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_get(self, mock_connect):
        """Test vector retrieval."""
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
        
        vector_id = str(uuid.uuid4())
        mock_result = (vector_id, [0.1, 0.2, 0.3], self.test_payloads[0])
        self.mock_cursor.fetchone.return_value = mock_result
        
        result = pgvector.get(vector_id)
        
        self.mock_cursor.execute.assert_called_with(
            "SELECT id, vector, payload FROM test_collection WHERE id = %s",
            (vector_id,)
        )
        
        self.assertIsInstance(result, OutputData)
        self.assertEqual(result.id, vector_id)
        self.assertEqual(result.payload, self.test_payloads[0])

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list_cols(self, mock_connect):
        """Test listing collections."""
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
        
        mock_collections = [("collection1",), ("collection2",)]
        self.mock_cursor.fetchall.return_value = mock_collections
        
        collections = pgvector.list_cols()
        
        self.mock_cursor.execute.assert_called_with(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        )
        self.assertEqual(collections, ["collection1", "collection2"])

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_delete_col(self, mock_connect):
        """Test collection deletion."""
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
        
        pgvector.delete_col()
        
        self.mock_cursor.execute.assert_called_with(
            "DROP TABLE IF EXISTS test_collection"
        )
        self.mock_conn.commit.assert_called()

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_col_info(self, mock_connect):
        """Test collection information retrieval."""
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
        
        mock_info = ("test_collection", 10, "1 MB")
        self.mock_cursor.fetchone.return_value = mock_info
        
        info = pgvector.col_info()
        
        # Check that the query was called (don't check exact string due to formatting)
        info_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT" in str(call) and "table_name" in str(call)]
        self.assertTrue(len(info_calls) > 0)
        
        self.assertEqual(info["name"], "test_collection")
        self.assertEqual(info["count"], 10)
        self.assertEqual(info["size"], "1 MB")

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_list(self, mock_connect):
        """Test listing vectors."""
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
        
        mock_results = [
            (self.test_ids[0], [0.1, 0.2, 0.3], self.test_payloads[0]),
            (self.test_ids[1], [0.4, 0.5, 0.6], self.test_payloads[1])
        ]
        self.mock_cursor.fetchall.return_value = mock_results
        
        results = pgvector.list(limit=2)
        
        # Check that the query was called
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        self.assertEqual(len(results), 1)  # Returns list of lists
        self.assertEqual(len(results[0]), 2)
        self.assertIsInstance(results[0][0], OutputData)

    @patch('mem0.vector_stores.pgvector.psycopg2.connect')
    def test_reset(self, mock_connect):
        """Test collection reset."""
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
        
        # Should call delete_col and create_col
        self.mock_cursor.execute.assert_any_call(
            "DROP TABLE IF EXISTS test_collection"
        )
        self.mock_cursor.execute.assert_any_call("CREATE EXTENSION IF NOT EXISTS vector")

    def tearDown(self):
        """Clean up after tests."""
        del self.mock_conn
        del self.mock_cursor
        del self.mock_pool
