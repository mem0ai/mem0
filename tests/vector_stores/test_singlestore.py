import json
import unittest
import uuid
from unittest.mock import MagicMock, patch

from mem0.vector_stores.singlestore import SingleStore


class TestSingleStore(unittest.TestCase):
    def setUp(self):
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.mock_conn.is_connected.return_value = True

        self.test_vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        self.test_payloads = [
            {"data": "memory1", "user_id": "alice", "text_lemmatized": "memory one"},
            {"data": "memory2", "user_id": "alice", "text_lemmatized": "memory two"},
        ]
        self.test_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    def _create_instance(self, **kwargs):
        """Helper to create a SingleStore instance with mocked connection."""
        defaults = {
            "host": "localhost",
            "port": 3306,
            "user": "root",
            "password": "pass",
            "database": "testdb",
            "collection_name": "test_collection",
            "embedding_model_dims": 3,
        }
        defaults.update(kwargs)
        return SingleStore(**defaults)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_init_creates_table_if_not_exists(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []  # No existing tables

        store = self._create_instance()

        self.assertEqual(store.collection_name, "test_collection")
        self.assertEqual(store.embedding_model_dims, 3)
        # Verify CREATE TABLE was called
        create_calls = [c for c in self.mock_cursor.execute.call_args_list if "CREATE TABLE" in str(c)]
        self.assertTrue(len(create_calls) > 0)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_init_skips_create_if_table_exists(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]

        store = self._create_instance()

        # CREATE TABLE should NOT be called (only SHOW TABLES)
        create_calls = [c for c in self.mock_cursor.execute.call_args_list if "CREATE TABLE" in str(c)]
        self.assertEqual(len(create_calls), 0)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_create_col_with_vector_index(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []

        store = self._create_instance(use_vector_index=True, use_fulltext_index=True)

        create_calls = [c for c in self.mock_cursor.execute.call_args_list if "CREATE TABLE" in str(c)]
        self.assertTrue(len(create_calls) > 0)
        sql = str(create_calls[0])
        self.assertIn("VECTOR INDEX", sql)
        self.assertIn("HNSW_FLAT", sql)
        self.assertIn("FULLTEXT", sql)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_create_col_without_indexes(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = []

        store = self._create_instance(use_vector_index=False, use_fulltext_index=False)

        create_calls = [c for c in self.mock_cursor.execute.call_args_list if "CREATE TABLE" in str(c)]
        sql = str(create_calls[0])
        self.assertNotIn("VECTOR INDEX", sql)
        self.assertNotIn("FULLTEXT", sql)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_insert_batch(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]

        store = self._create_instance()
        store.insert(self.test_vectors, self.test_payloads, self.test_ids)

        # Verify executemany was called with correct data
        self.mock_cursor.executemany.assert_called_once()
        call_args = self.mock_cursor.executemany.call_args
        sql = call_args[0][0]
        data = call_args[0][1]
        self.assertIn("INSERT INTO", sql)
        self.assertIn(":> VECTOR(3, F32)", sql)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0][0], self.test_ids[0])
        self.assertEqual(data[1][0], self.test_ids[1])

    @patch("mem0.vector_stores.singlestore.s2")
    def test_search_no_filters(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.side_effect = [
            [("test_collection",)],  # list_cols
            [(self.test_ids[0], 0.95, json.dumps({"data": "result"}))],  # search
        ]

        store = self._create_instance()
        results = store.search("query", [0.1, 0.2, 0.3], top_k=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].score, 0.95)
        self.assertEqual(results[0].payload["data"], "result")

        # Verify DOT_PRODUCT is used and ORDER BY DESC
        search_call = self.mock_cursor.execute.call_args_list[-1]
        sql = search_call[0][0]
        self.assertIn("DOT_PRODUCT", sql)
        self.assertIn("ORDER BY score DESC", sql)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_search_with_filters(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.side_effect = [
            [("test_collection",)],
            [(self.test_ids[0], 0.9, json.dumps({"data": "x", "user_id": "alice"}))],
        ]

        store = self._create_instance()
        results = store.search("query", [0.1, 0.2, 0.3], top_k=5, filters={"user_id": "alice"})

        self.assertEqual(len(results), 1)
        search_call = self.mock_cursor.execute.call_args_list[-1]
        sql = search_call[0][0]
        self.assertIn("JSON_EXTRACT_STRING", sql)
        self.assertIn("WHERE", sql)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_search_euclidean(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.side_effect = [
            [("test_collection",)],
            [(self.test_ids[0], 0.05, json.dumps({"data": "close"}))],
        ]

        store = self._create_instance(distance_strategy="EUCLIDEAN_DISTANCE")
        results = store.search("query", [0.1, 0.2, 0.3], top_k=5)

        search_call = self.mock_cursor.execute.call_args_list[-1]
        sql = search_call[0][0]
        self.assertIn("EUCLIDEAN_DISTANCE", sql)
        self.assertIn("ORDER BY score ASC", sql)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_keyword_search(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.side_effect = [
            [("test_collection",)],
            [(self.test_ids[0], 3.5, json.dumps({"data": "match"}))],
        ]

        store = self._create_instance()
        results = store.keyword_search("memory one", top_k=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].score, 3.5)
        search_call = self.mock_cursor.execute.call_args_list[-1]
        sql = search_call[0][0]
        self.assertIn("MATCH(text_lemmatized) AGAINST", sql)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_keyword_search_disabled(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]

        store = self._create_instance(use_fulltext_index=False)
        results = store.keyword_search("query")

        self.assertIsNone(results)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_delete(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]

        store = self._create_instance()
        store.delete(self.test_ids[0])

        delete_call = self.mock_cursor.execute.call_args_list[-1]
        sql = delete_call[0][0]
        params = delete_call[0][1]
        self.assertIn("DELETE FROM", sql)
        self.assertEqual(params, (self.test_ids[0],))

    @patch("mem0.vector_stores.singlestore.s2")
    def test_update_vector_only(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]

        store = self._create_instance()
        store.update(self.test_ids[0], vector=[0.7, 0.8, 0.9])

        update_calls = [c for c in self.mock_cursor.execute.call_args_list if "UPDATE" in str(c)]
        self.assertEqual(len(update_calls), 1)
        sql = update_calls[0][0][0]
        self.assertIn("SET vector", sql)
        self.assertIn(":> VECTOR(3, F32)", sql)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_update_payload_only(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]

        store = self._create_instance()
        store.update(self.test_ids[0], payload={"data": "updated", "text_lemmatized": "updated"})

        update_calls = [c for c in self.mock_cursor.execute.call_args_list if "UPDATE" in str(c)]
        self.assertEqual(len(update_calls), 1)
        sql = update_calls[0][0][0]
        self.assertIn("SET payload", sql)
        self.assertIn("text_lemmatized", sql)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_update_both(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]

        store = self._create_instance()
        store.update(self.test_ids[0], vector=[0.7, 0.8, 0.9], payload={"data": "new"})

        update_calls = [c for c in self.mock_cursor.execute.call_args_list if "UPDATE" in str(c)]
        self.assertEqual(len(update_calls), 2)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_get_found(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]
        self.mock_cursor.fetchone.return_value = (self.test_ids[0], json.dumps({"data": "hello"}))

        store = self._create_instance()
        result = store.get(self.test_ids[0])

        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.test_ids[0])
        self.assertEqual(result.payload["data"], "hello")

    @patch("mem0.vector_stores.singlestore.s2")
    def test_get_not_found(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]
        self.mock_cursor.fetchone.return_value = None

        store = self._create_instance()
        result = store.get("nonexistent")

        self.assertIsNone(result)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_list_cols(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("table1",), ("table2",)]

        store = self._create_instance()
        cols = store.list_cols()

        self.assertEqual(cols, ["table1", "table2"])

    @patch("mem0.vector_stores.singlestore.s2")
    def test_delete_col(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]

        store = self._create_instance()
        store.delete_col()

        drop_calls = [c for c in self.mock_cursor.execute.call_args_list if "DROP TABLE" in str(c)]
        self.assertTrue(len(drop_calls) > 0)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_col_info(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]
        self.mock_cursor.fetchone.return_value = (42,)

        store = self._create_instance()
        info = store.col_info()

        self.assertEqual(info["name"], "test_collection")
        self.assertEqual(info["count"], 42)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_list_with_filters(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.side_effect = [
            [("test_collection",)],
            [(self.test_ids[0], json.dumps({"data": "mem", "user_id": "alice"}))],
        ]

        store = self._create_instance()
        results = store.list(filters={"user_id": "alice"}, top_k=10)

        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]), 1)
        self.assertEqual(results[0][0].id, self.test_ids[0])
        list_call = self.mock_cursor.execute.call_args_list[-1]
        sql = list_call[0][0]
        self.assertIn("WHERE", sql)
        self.assertIn("JSON_EXTRACT_STRING", sql)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_list_no_filters(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.side_effect = [
            [("test_collection",)],
            [(self.test_ids[0], json.dumps({"data": "mem1"})), (self.test_ids[1], json.dumps({"data": "mem2"}))],
        ]

        store = self._create_instance()
        results = store.list(top_k=100)

        self.assertEqual(len(results), 1)
        self.assertEqual(len(results[0]), 2)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_reset(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]

        store = self._create_instance()
        store.reset()

        drop_calls = [c for c in self.mock_cursor.execute.call_args_list if "DROP TABLE" in str(c)]
        create_calls = [c for c in self.mock_cursor.execute.call_args_list if "CREATE TABLE" in str(c)]
        self.assertTrue(len(drop_calls) > 0)
        self.assertTrue(len(create_calls) > 0)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_reconnect_on_disconnect(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]

        store = self._create_instance()

        # Simulate disconnection
        self.mock_conn.is_connected.return_value = False
        store._get_connection()

        # Should have called connect again
        self.assertEqual(mock_s2.connect.call_count, 2)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_connection_url(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]

        store = SingleStore(
            host=None,
            port=3306,
            user=None,
            password=None,
            database=None,
            collection_name="test_collection",
            embedding_model_dims=3,
            connection_url="mysql://user:pass@host:3306/db",
        )

        mock_s2.connect.assert_called_with(host="mysql://user:pass@host:3306/db")


class TestSingleStoreConfig(unittest.TestCase):
    def test_config_registered_in_provider_configs(self):
        from mem0.vector_stores.configs import VectorStoreConfig

        config = VectorStoreConfig.__private_attributes__["_provider_configs"].default
        self.assertIn("singlestore", config)
        self.assertEqual(config["singlestore"], "SingleStoreConfig")

    def test_config_validation_pipeline(self):
        from mem0.vector_stores.configs import VectorStoreConfig

        config = VectorStoreConfig(
            provider="singlestore",
            config={
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "pass",
                "database": "testdb",
                "collection_name": "memories",
            },
        )
        self.assertEqual(config.config.collection_name, "memories")
        self.assertEqual(config.config.embedding_model_dims, 1536)
        self.assertEqual(config.config.distance_strategy, "DOT_PRODUCT")

    def test_config_rejects_missing_required_fields(self):
        from mem0.configs.vector_stores.singlestore import SingleStoreConfig

        with self.assertRaises(ValueError):
            SingleStoreConfig(host="localhost")  # missing user, password, database

    def test_config_accepts_connection_url(self):
        from mem0.configs.vector_stores.singlestore import SingleStoreConfig

        config = SingleStoreConfig(connection_url="mysql://user:pass@host:3306/db")
        self.assertEqual(config.connection_url, "mysql://user:pass@host:3306/db")

    def test_config_rejects_extra_fields(self):
        from mem0.configs.vector_stores.singlestore import SingleStoreConfig

        with self.assertRaises(ValueError):
            SingleStoreConfig(
                host="localhost",
                user="root",
                password="pass",
                database="db",
                unknown_field="bad",
            )

    @patch("mem0.vector_stores.singlestore.s2")
    def test_factory_creates_instance(self, mock_s2):
        from mem0.utils.factory import VectorStoreFactory

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.is_connected.return_value = True
        mock_cursor.fetchall.return_value = [("test_collection",)]
        mock_s2.connect.return_value = mock_conn

        store = VectorStoreFactory.create(
            "singlestore",
            {
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "pass",
                "database": "testdb",
                "collection_name": "test_collection",
                "embedding_model_dims": 3,
            },
        )
        self.assertIsInstance(store, SingleStore)
        self.assertEqual(store.collection_name, "test_collection")


class TestSingleStoreKeywordSearchWithFilters(unittest.TestCase):
    def setUp(self):
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.mock_conn.is_connected.return_value = True

    @patch("mem0.vector_stores.singlestore.s2")
    def test_keyword_search_with_filters(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.side_effect = [
            [("test_collection",)],
            [("id1", 2.5, json.dumps({"data": "result", "user_id": "alice"}))],
        ]

        store = SingleStore(
            host="localhost", port=3306, user="root", password="pass",
            database="testdb", collection_name="test_collection", embedding_model_dims=3,
        )
        results = store.keyword_search("memory", top_k=5, filters={"user_id": "alice"})

        self.assertEqual(len(results), 1)
        sql = self.mock_cursor.execute.call_args_list[-1][0][0]
        self.assertIn("MATCH(text_lemmatized) AGAINST", sql)
        self.assertIn("JSON_EXTRACT_STRING", sql)
        self.assertIn("AND", sql)

    @patch("mem0.vector_stores.singlestore.s2")
    def test_keyword_search_handles_exception(self, mock_s2):
        mock_s2.connect.return_value = self.mock_conn
        self.mock_cursor.fetchall.return_value = [("test_collection",)]
        self.mock_cursor.execute.side_effect = [None, Exception("FTS error")]

        store = SingleStore(
            host="localhost", port=3306, user="root", password="pass",
            database="testdb", collection_name="test_collection", embedding_model_dims=3,
        )
        # Reset side_effect for the keyword_search call
        self.mock_cursor.execute.side_effect = Exception("FTS error")
        results = store.keyword_search("query")

        self.assertIsNone(results)
