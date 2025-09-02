import importlib
import sys
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
        self.mock_pool_psycopg2 = MagicMock()
        self.mock_pool_psycopg2.getconn.return_value = self.mock_conn

        self.mock_pool_psycopg = MagicMock()
        self.mock_pool_psycopg.connection.return_value = self.mock_conn
        
        self.mock_get_cursor = MagicMock()
        self.mock_get_cursor.return_value = self.mock_cursor

        # Mock connection string
        self.connection_string = "postgresql://user:pass@host:5432/db"
        
        # Test data
        self.test_vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        self.test_payloads = [{"key": "value1"}, {"key": "value2"}]
        self.test_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    def test_init_with_individual_params_psycopg3(self, mock_psycopg_pool):
        """Test initialization with individual parameters using psycopg3."""
        # Mock psycopg3 to be available
        mock_psycopg_pool.return_value = self.mock_pool_psycopg
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
            hnsw=False,
            minconn=1,
            maxconn=4,
        )

        mock_psycopg_pool.assert_called_once_with(
            conninfo="postgresql://test_user:test_pass@localhost:5432/test_db",
            min_size=1,
            max_size=4,
            open=True,
        )
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    def test_init_with_individual_params_psycopg2(self, mock_pcycopg2_pool):
        """Test initialization with individual parameters using psycopg2."""
        mock_pcycopg2_pool.return_value = self.mock_pool_psycopg2
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
            hnsw=False,
            minconn=1,
            maxconn=4,
        )
        
        mock_pcycopg2_pool.assert_called_once_with(
            minconn=1,
            maxconn=4,
            dsn="postgresql://test_user:test_pass@localhost:5432/test_db",
        )

        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_create_col_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test collection creation with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()

        # Verify vector extension and table creation
        self.mock_cursor.execute.assert_any_call("CREATE EXTENSION IF NOT EXISTS vector")
        table_creation_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "CREATE TABLE IF NOT EXISTS test_collection" in str(call)]
        self.assertTrue(len(table_creation_calls) > 0)
        
        # Verify pgvector instance properties
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_create_col_psycopg3_with_explicit_pool(self, mock_get_cursor, mock_connection_pool):
        """
        Test collection creation with psycopg3 when an explicit psycopg_pool.ConnectionPool is provided.
        This ensures that PGVector uses the provided pool and still performs collection creation logic.
        """
        # Set up a real (mocked) psycopg_pool.ConnectionPool instance
        explicit_pool = MagicMock(name="ExplicitPsycopgPool")
        # The patch for ConnectionPool should not be used in this case, but we patch it for isolation
        mock_connection_pool.return_value = MagicMock(name="ShouldNotBeUsed")

        # Configure the _get_cursor mock to return our mock cursor as a context manager
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None

        # Simulate no existing collections in the database
        self.mock_cursor.fetchall.return_value = []

        # Pass the explicit pool to PGVector
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            connection_pool=explicit_pool
        )

        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()

        mock_connection_pool.assert_not_called()


        # Verify vector extension and table creation
        self.mock_cursor.execute.assert_any_call("CREATE EXTENSION IF NOT EXISTS vector")
        table_creation_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "CREATE TABLE IF NOT EXISTS test_collection" in str(call)]
        self.assertTrue(len(table_creation_calls) > 0)

        # Verify pgvector instance properties
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)
        # Ensure the pool used is the explicit one
        self.assertIs(pgvector.connection_pool, explicit_pool)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_create_col_psycopg2_with_explicit_pool(self, mock_get_cursor, mock_connection_pool):
        """
        Test collection creation with psycopg2 when an explicit psycopg2 ThreadedConnectionPool is provided.
        This ensures that PGVector uses the provided pool and still performs collection creation logic.
        """
        # Set up a real (mocked) psycopg2 ThreadedConnectionPool instance
        explicit_pool = MagicMock(name="ExplicitPsycopg2Pool")
        # The patch for ConnectionPool should not be used in this case, but we patch it for isolation
        mock_connection_pool.return_value = MagicMock(name="ShouldNotBeUsed")

        # Configure the _get_cursor mock to return our mock cursor as a context manager
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None

        # Simulate no existing collections in the database
        self.mock_cursor.fetchall.return_value = []

        # Pass the explicit pool to PGVector
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            connection_pool=explicit_pool
        )

        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()

        mock_connection_pool.assert_not_called()

        # Verify vector extension and table creation
        self.mock_cursor.execute.assert_any_call("CREATE EXTENSION IF NOT EXISTS vector")
        table_creation_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "CREATE TABLE IF NOT EXISTS test_collection" in str(call)]
        self.assertTrue(len(table_creation_calls) > 0)

        # Verify pgvector instance properties
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)
        # Ensure the pool used is the explicit one
        self.assertIs(pgvector.connection_pool, explicit_pool)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_create_col_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test collection creation with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify vector extension and table creation
        self.mock_cursor.execute.assert_any_call("CREATE EXTENSION IF NOT EXISTS vector")
        table_creation_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "CREATE TABLE IF NOT EXISTS test_collection" in str(call)]
        self.assertTrue(len(table_creation_calls) > 0)
        
        # Verify pgvector instance properties
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_insert_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test vector insertion with psycopg3."""
        # Set up mock pool and cursor
        mock_connection_pool.return_value = self.mock_pool_psycopg
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.insert(self.test_vectors, self.test_payloads, self.test_ids)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify insert query was executed (psycopg3 uses executemany)
        insert_calls = [call for call in self.mock_cursor.executemany.call_args_list 
                       if "INSERT INTO test_collection" in str(call)]
        self.assertTrue(len(insert_calls) > 0)
        
        # Verify data format
        call_args = self.mock_cursor.executemany.call_args
        data_arg = call_args[0][1]
        self.assertEqual(len(data_arg), 2)
        self.assertEqual(data_arg[0][0], self.test_ids[0])
        self.assertEqual(data_arg[1][0], self.test_ids[1])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_insert_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """
        Test vector insertion with psycopg2.
        This test ensures that PGVector.insert uses psycopg2.extras.execute_values for batch inserts
        and that the data passed to execute_values is correctly formatted.
        """
        # --- Setup mocks for psycopg2 and its submodules ---
        mock_execute_values = MagicMock()
        mock_pool = MagicMock()

        # Mock psycopg2.extras with execute_values
        mock_psycopg2_extras = MagicMock()
        mock_psycopg2_extras.execute_values = mock_execute_values

        mock_psycopg2_pool = MagicMock()
        mock_psycopg2_pool.ThreadedConnectionPool = mock_pool

        # Mock psycopg2 root module
        mock_psycopg2 = MagicMock()
        mock_psycopg2.extras = mock_psycopg2_extras
        mock_psycopg2.pool = mock_psycopg2_pool

        # Patch sys.modules so that imports in PGVector use our mocks
        with patch.dict('sys.modules', {
            'psycopg': None,  # Ensure psycopg3 is not available
            'psycopg_pool': None,
            'psycopg.types.json': None,
            'psycopg2': mock_psycopg2,
            'psycopg2.extras': mock_psycopg2_extras,
            'psycopg2.pool': mock_psycopg2_pool
        }):
            # Force reload of PGVector to pick up the mocked modules
            if 'mem0.vector_stores.pgvector' in sys.modules:
                importlib.reload(sys.modules['mem0.vector_stores.pgvector'])

            mock_connection_pool.return_value = self.mock_pool_psycopg
            mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
            mock_get_cursor.return_value.__exit__.return_value = None
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
                hnsw=False,
                minconn=1,
                maxconn=4
            )

            pgvector.insert(self.test_vectors, self.test_payloads, self.test_ids)

            mock_get_cursor.assert_called()
            mock_execute_values.assert_called_once()
            call_args = mock_execute_values.call_args

            self.assertIn("INSERT INTO test_collection", call_args[0][1])

            # The data argument should be a list of tuples, one per vector
            data_arg = call_args[0][2]
            self.assertEqual(len(data_arg), 2)
            self.assertEqual(data_arg[0][0], self.test_ids[0])
            self.assertEqual(data_arg[1][0], self.test_ids[1])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_search_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test search with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_search_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test search with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_delete_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test delete with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.delete(self.test_ids[0])
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify delete query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DELETE FROM test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_delete_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test delete with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.delete(self.test_ids[0])
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify delete query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DELETE FROM test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_update_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test update with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        updated_vector = [0.5, 0.6, 0.7]
        updated_payload = {"updated": "value"}
        
        pgvector.update(self.test_ids[0], vector=updated_vector, payload=updated_payload)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify update queries were executed
        update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "UPDATE test_collection" in str(call)]
        self.assertTrue(len(update_calls) > 0)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_update_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test update with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        updated_vector = [0.5, 0.6, 0.7]
        updated_payload = {"updated": "value"}
        
        pgvector.update(self.test_ids[0], vector=updated_vector, payload=updated_payload)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify update queries were executed
        update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "UPDATE test_collection" in str(call)]
        self.assertTrue(len(update_calls) > 0)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_get_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test get with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        result = pgvector.get(self.test_ids[0])
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify get query was executed
        get_calls = [call for call in self.mock_cursor.execute.call_args_list 
                    if "SELECT id, vector, payload" in str(call)]
        self.assertTrue(len(get_calls) > 0)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.test_ids[0])
        self.assertEqual(result.payload, {"key": "value1"})

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_get_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test get with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        result = pgvector.get(self.test_ids[0])
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify get query was executed
        get_calls = [call for call in self.mock_cursor.execute.call_args_list 
                    if "SELECT id, vector, payload" in str(call)]
        self.assertTrue(len(get_calls) > 0)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.test_ids[0])
        self.assertEqual(result.payload, {"key": "value1"})

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_list_cols_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test list_cols with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        collections = pgvector.list_cols()
        
        # Verify list_cols query was executed
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name FROM information_schema.tables" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify result
        self.assertEqual(collections, ["test_collection", "other_table"])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_list_cols_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test list_cols with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        collections = pgvector.list_cols()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify list_cols query was executed
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name FROM information_schema.tables" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify result
        self.assertEqual(collections, ["test_collection", "other_table"])

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_delete_col_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test delete_col with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.delete_col()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify delete_col query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DROP TABLE IF EXISTS test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_delete_col_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test delete_col with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.delete_col()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify delete_col query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DROP TABLE IF EXISTS test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_col_info_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test col_info with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        info = pgvector.col_info()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify col_info query was executed
        info_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name" in str(call)]
        self.assertTrue(len(info_calls) > 0)
        
        # Verify result
        self.assertEqual(info["name"], "test_collection")
        self.assertEqual(info["count"], 100)
        self.assertEqual(info["size"], "1 MB")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_col_info_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test col_info with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        info = pgvector.col_info()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify col_info query was executed
        info_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name" in str(call)]
        self.assertTrue(len(info_calls) > 0)
        
        # Verify result
        self.assertEqual(info["name"], "test_collection")
        self.assertEqual(info["count"], 100)
        self.assertEqual(info["size"], "1 MB")

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_list_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test list with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.list(limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_list_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test list with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.list(limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_search_with_filters_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test search with filters using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_search_with_filters_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test search with filters using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_search_with_single_filter_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test search with single filter using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_search_with_single_filter_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test search with single filter using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_search_with_no_filters_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test search with no filters using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=None)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_search_with_no_filters_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test search with no filters using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=None)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_list_with_filters_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test list with filters using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_list_with_filters_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test list with filters using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_list_with_single_filter_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test list with single filter using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_list_with_single_filter_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test list with single filter using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_list_with_no_filters_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test list with no filters using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.list(filters=None, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_list_with_no_filters_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test list with no filters using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.list(filters=None, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
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
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_reset_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test reset with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.reset()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify reset operations were executed
        drop_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "DROP TABLE IF EXISTS" in str(call)]
        create_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "CREATE TABLE IF NOT EXISTS" in str(call)]
        self.assertTrue(len(drop_calls) > 0)
        self.assertTrue(len(create_calls) > 0)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_reset_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test reset with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.reset()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify reset operations were executed
        drop_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "DROP TABLE IF EXISTS" in str(call)]
        create_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "CREATE TABLE IF NOT EXISTS" in str(call)]
        self.assertTrue(len(drop_calls) > 0)
        self.assertTrue(len(create_calls) > 0)

    # Enhanced Tests for JSON Serialization
    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    @patch('mem0.vector_stores.pgvector.Json')
    def test_update_payload_psycopg3_json_handling(self, mock_json, mock_get_cursor, mock_connection_pool):
        """Test that psycopg3 update uses Json() wrapper for payload serialization."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        test_payload = {"test": "data", "number": 42}
        pgvector.update("test-id-123", payload=test_payload)
        
        # Verify Json() wrapper was used for psycopg3
        mock_json.assert_called_once_with(test_payload)
        
        # Verify the update query was executed
        update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "UPDATE test_collection SET payload" in str(call)]
        self.assertTrue(len(update_calls) > 0)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    @patch('mem0.vector_stores.pgvector.Json')
    def test_update_payload_psycopg2_json_handling(self, mock_json, mock_get_cursor, mock_connection_pool):
        """Test that psycopg2 update uses psycopg2.extras.Json() wrapper for payload serialization."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        test_payload = {"test": "data", "number": 42}
        pgvector.update("test-id-123", payload=test_payload)
        
        # Verify psycopg2.extras.Json() wrapper was used
        mock_json.assert_called_once_with(test_payload)
        
        # Verify the update query was executed
        update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "UPDATE test_collection SET payload" in str(call)]
        self.assertTrue(len(update_calls) > 0)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    def test_transaction_rollback_on_error_psycopg2(self, mock_connection_pool):
        """Test that psycopg2 properly rolls back transactions on errors."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool

        # Set up mock connection that will raise an error only on delete
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn

        # Only raise exception on the delete operation, not during setup
        def execute_side_effect(*args, **kwargs):
            if args and "DELETE FROM" in str(args[0]):
                raise Exception("Database error")
            return MagicMock()
        mock_cursor.execute.side_effect = execute_side_effect
        self.mock_cursor.fetchall.return_value = []  # No existing collections initially

        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )

        # Attempt an operation that will fail
        with self.assertRaises(Exception) as context:
            pgvector.delete("test-id")

        self.assertIn("Database error", str(context.exception))
        # Verify rollback was called
        mock_conn.rollback.assert_called()
        # Verify connection was returned to pool
        mock_pool.putconn.assert_called_with(mock_conn)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    def test_commit_on_success_psycopg2(self, mock_connection_pool):
        """Test that psycopg2 properly commits transactions on success."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Set up mock connection for successful operation
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections initially
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        # Perform an operation that requires commit
        pgvector.delete("test-id")
        
        # Verify commit was called
        mock_conn.commit.assert_called()
        # Verify connection was returned to pool
        mock_pool.putconn.assert_called_with(mock_conn)

    # Enhanced Tests for Error Handling
    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_pool_connection_error_handling(self, mock_get_cursor, mock_connection_pool):
        """Test handling of connection pool errors."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool

        # Use a flag to only raise the exception after PGVector is initialized
        raise_on_search = {'active': False}
        def get_cursor_side_effect(*args, **kwargs):
            if raise_on_search['active']:
                raise Exception("Connection pool exhausted")
            return self.mock_cursor

        mock_get_cursor.side_effect = get_cursor_side_effect
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )

        # Activate the exception for search only
        raise_on_search['active'] = True
        with self.assertRaises(Exception) as context:
            pgvector.search("test query", [0.1, 0.2, 0.3])

        self.assertIn("Connection pool exhausted", str(context.exception))

    # Enhanced Tests for Vector and Payload Update Combinations
    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_update_vector_only_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test updating only vector without payload."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        test_vector = [0.1, 0.2, 0.3]
        pgvector.update("test-id", vector=test_vector)
        
        # Verify only vector update query was executed (not payload)
        vector_update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "UPDATE test_collection SET vector" in str(call) and "payload" not in str(call)]
        payload_update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                               if "UPDATE test_collection SET payload" in str(call)]
        
        self.assertTrue(len(vector_update_calls) > 0)
        self.assertEqual(len(payload_update_calls), 0)

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_update_both_vector_and_payload_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test updating both vector and payload."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        test_vector = [0.1, 0.2, 0.3]
        test_payload = {"updated": True}
        pgvector.update("test-id", vector=test_vector, payload=test_payload)
        
        # Verify both vector and payload update queries were executed
        vector_update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "UPDATE test_collection SET vector" in str(call)]
        payload_update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                               if "UPDATE test_collection SET payload" in str(call)]
        
        self.assertTrue(len(vector_update_calls) > 0)
        self.assertTrue(len(payload_update_calls) > 0)

    # Enhanced Tests for Connection String Handling
    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    def test_connection_string_with_sslmode_psycopg3(self, mock_connection_pool):
        """Test connection string handling with SSL mode."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        connection_string = "postgresql://user:pass@localhost:5432/db"
        
        pgvector = PGVector(
            dbname="test_db",  # Will be overridden by connection_string
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            sslmode="require",
            connection_string=connection_string
        )
        
        # Verify ConnectionPool was called with the connection string including sslmode
        expected_conn_string = f"{connection_string} sslmode=require"
        mock_connection_pool.assert_called_with(
            conninfo=expected_conn_string,
            min_size=1,
            max_size=4,
            open=True
        )
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    # Enhanced Test for Index Creation with DiskANN
    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_create_col_with_diskann_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test collection creation with DiskANN index."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        # Mock vectorscale extension as available
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        self.mock_cursor.fetchone.return_value = ("vectorscale",)  # Extension exists
        
        pgvector = PGVector(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=True,  # Enable DiskANN
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        # Verify DiskANN index creation query was executed
        diskann_calls = [call for call in self.mock_cursor.execute.call_args_list 
                        if "USING diskann" in str(call)]
        self.assertTrue(len(diskann_calls) > 0)
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)
        

    @patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3)
    @patch('mem0.vector_stores.pgvector.ConnectionPool')
    @patch.object(PGVector, '_get_cursor')
    def test_create_col_with_hnsw_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test collection creation with HNSW index."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
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
            hnsw=True,  # Enable HNSW
            minconn=1,
            maxconn=4
        )
        
        # Verify HNSW index creation query was executed
        hnsw_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "USING hnsw" in str(call)]
        self.assertTrue(len(hnsw_calls) > 0)
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    # Enhanced Test for Pool Cleanup
    def test_pool_cleanup_psycopg3(self):
        """Test that psycopg3 pool is properly closed on object deletion."""
        with patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 3), \
             patch('mem0.vector_stores.pgvector.ConnectionPool') as mock_connection_pool:
            
            mock_pool = MagicMock()
            mock_connection_pool.return_value = mock_pool
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
                hnsw=False,
                minconn=1,
                maxconn=4
            )
            
            # Trigger __del__ method
            del pgvector
            
            # Verify pool.close() was called
            mock_pool.close.assert_called()

    def test_pool_cleanup_psycopg2(self):
        """Test that psycopg2 pool is properly closed on object deletion."""
        with patch('mem0.vector_stores.pgvector.PSYCOPG_VERSION', 2), \
             patch('mem0.vector_stores.pgvector.ConnectionPool') as mock_connection_pool:
            
            mock_pool = MagicMock()
            mock_connection_pool.return_value = mock_pool
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
                hnsw=False,
                minconn=1,
                maxconn=4
            )
            
            # Trigger __del__ method
            del pgvector
            
            # Verify pool.closeall() was called
            mock_pool.closeall.assert_called()

    def tearDown(self):
        """Clean up after each test."""
        pass
