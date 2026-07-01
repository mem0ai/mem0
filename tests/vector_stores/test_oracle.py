import array
import unittest
from unittest.mock import MagicMock, patch

from mem0.configs.vector_stores.oracle import OracleConfig
from mem0.vector_stores.oracle import OracleDB


class TestOracleConfig(unittest.TestCase):
    def test_requires_dsn_without_connection_pool(self):
        with self.assertRaises(ValueError):
            OracleConfig(user="mem0", password="password")

    def test_requires_user_and_password_without_connection_pool(self):
        with self.assertRaises(ValueError):
            OracleConfig(dsn="localhost:1521/FREEPDB1")

    def test_normalizes_distance_and_search_mode(self):
        config = OracleConfig(dsn="localhost:1521/FREEPDB1", user="mem0", password="password", distance="cosine")
        self.assertEqual(config.distance, "COSINE")
        self.assertEqual(config.search_mode, "approx")

    def test_rejects_extra_fields(self):
        with self.assertRaises(ValueError):
            OracleConfig(dsn="localhost:1521/FREEPDB1", user="mem0", password="password", unsupported=True)


class TestOracleDB(unittest.TestCase):
    def setUp(self):
        self.mock_pool = MagicMock()
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_pool.acquire.return_value = self.mock_conn
        self.mock_conn.cursor.return_value = self.mock_cursor
        self.mock_cursor.fetchone.return_value = None
        self.mock_cursor.fetchall.return_value = []

    def create_store(self, **kwargs):
        params = {
            "dsn": "localhost:1521/FREEPDB1",
            "user": "mem0",
            "password": "password",
            "collection_name": "mem0_test",
            "embedding_model_dims": 3,
            "auto_create": False,
        }
        params.update(kwargs)
        with patch("mem0.vector_stores.oracle.oracledb.create_pool", return_value=self.mock_pool):
            return OracleDB(**params)

    def executed_sql(self):
        return "\n".join(str(call.args[0]) for call in self.mock_cursor.execute.call_args_list)

    def test_initialization_creates_pool(self):
        with patch("mem0.vector_stores.oracle.oracledb.create_pool", return_value=self.mock_pool) as create_pool:
            OracleDB(
                dsn="localhost:1521/FREEPDB1",
                user="mem0",
                password="password",
                collection_name="mem0_test",
                embedding_model_dims=3,
                auto_create=False,
            )
        create_pool.assert_called_once()
        self.assertEqual(create_pool.call_args.kwargs["dsn"], "localhost:1521/FREEPDB1")
        self.assertEqual(create_pool.call_args.kwargs["min"], 1)
        self.assertEqual(create_pool.call_args.kwargs["max"], 5)

    def test_rejects_invalid_identifier(self):
        with self.assertRaises(ValueError):
            self.create_store(collection_name="bad-name")

    def test_rejects_unsupported_metric(self):
        for distance in ("HAMMING", "JACCARD"):
            with self.subTest(distance=distance):
                with self.assertRaises(ValueError):
                    self.create_store(distance=distance)

    def test_rejects_unsupported_search_mode(self):
        with self.assertRaises(ValueError):
            self.create_store(search_mode="fast")

    def test_create_col_creates_native_vector_table_and_metadata_indexes(self):
        store = self.create_store(index={"create": False})
        store.create_col()
        sql = self.executed_sql()
        self.assertIn("CREATE TABLE MEM0_TEST", sql)
        self.assertIn("EMBEDDING VECTOR(3, FLOAT32)", sql)
        self.assertIn("PAYLOAD JSON", sql)
        self.assertIn("CREATE INDEX MEM0_TEST_USER_ID_IDX", sql)
        self.assertIn("CREATE INDEX MEM0_TEST_AGENT_ID_IDX", sql)
        self.assertIn("CREATE INDEX MEM0_TEST_RUN_ID_IDX", sql)
        self.assertIn("CREATE SEARCH INDEX MEM0_TEST_JSON_SEARCH_IDX", sql)
        self.assertIn("FOR JSON PARAMETERS ('SEARCH_ON TEXT SYNC (ON COMMIT)')", sql)

    def test_create_col_creates_hnsw_vector_index(self):
        store = self.create_store(
            index={"create": True, "type": "hnsw", "target_accuracy": 90, "neighbors": 40, "efconstruction": 500}
        )
        store.create_col()
        sql = self.executed_sql()
        self.assertIn("CREATE VECTOR INDEX MEM0_TEST_HNSW_IDX", sql)
        self.assertIn("ORGANIZATION INMEMORY NEIGHBOR GRAPH", sql)
        self.assertIn("DISTANCE COSINE", sql)
        self.assertIn("WITH TARGET ACCURACY 90", sql)
        self.assertIn("PARAMETERS (TYPE HNSW, NEIGHBORS 40, EFCONSTRUCTION 500)", sql)

    def test_create_col_creates_ivf_vector_index(self):
        store = self.create_store(
            index={"create": True, "type": "ivf", "target_accuracy": 90, "neighbor_partitions": 100}
        )
        store.create_col()
        sql = self.executed_sql()
        self.assertIn("CREATE VECTOR INDEX MEM0_TEST_IVF_IDX", sql)
        self.assertIn("ORGANIZATION NEIGHBOR PARTITIONS", sql)
        self.assertIn("DISTANCE COSINE", sql)
        self.assertIn("PARAMETERS (TYPE IVF, NEIGHBOR PARTITIONS 100)", sql)

    def test_insert_binds_vectors_payload_and_filter_columns(self):
        store = self.create_store()
        store.insert(
            vectors=[[0.1, 0.2, 0.3]],
            payloads=[{"user_id": "alice", "agent_id": "agent", "run_id": "run", "category": "movies"}],
            ids=["memory-1"],
        )
        self.mock_cursor.executemany.assert_called_once()
        data = self.mock_cursor.executemany.call_args.args[1]
        self.assertEqual(data[0][0], "memory-1")
        self.assertIsInstance(data[0][1], array.array)
        self.assertEqual(data[0][3], "alice")
        self.assertEqual(data[0][4], "agent")
        self.assertEqual(data[0][5], "run")

    def test_search_uses_approximate_vector_distance_with_target_accuracy_and_filters(self):
        store = self.create_store(search_mode="approx", target_accuracy=90)
        self.mock_cursor.fetchall.return_value = [("memory-1", 0.12, '{"category": "movies"}')]
        results = store.search(
            "movie preference",
            [0.1, 0.2, 0.3],
            top_k=2,
            filters={"user_id": "alice", "category": "movies"},
        )
        sql = self.mock_cursor.execute.call_args.args[0]
        params = self.mock_cursor.execute.call_args.args[1]
        self.assertIn("VECTOR_DISTANCE(EMBEDDING, :query_vector, COSINE)", sql)
        self.assertIn("USER_ID = :filter_0", sql)
        self.assertIn("JSON_VALUE(PAYLOAD, '$.category') = :filter_1", sql)
        self.assertIn("FETCH APPROX FIRST 2 ROWS ONLY WITH TARGET ACCURACY 90", sql)
        self.assertIsInstance(params["query_vector"], array.array)
        self.assertEqual(results[0].id, "memory-1")
        self.assertAlmostEqual(results[0].score, 0.88)
        self.assertEqual(results[0].payload["category"], "movies")

    def test_search_uses_exact_fetch_clause(self):
        store = self.create_store(search_mode="exact")
        store.search("query", [0.1, 0.2, 0.3], top_k=3)
        sql = self.mock_cursor.execute.call_args.args[0]
        self.assertIn("FETCH EXACT FIRST 3 ROWS ONLY", sql)

    def test_search_uses_auto_fetch_clause(self):
        store = self.create_store(search_mode="auto")
        store.search("query", [0.1, 0.2, 0.3], top_k=3)
        sql = self.mock_cursor.execute.call_args.args[0]
        self.assertIn("FETCH FIRST 3 ROWS ONLY", sql)
        self.assertNotIn("FETCH APPROX", sql)
        self.assertNotIn("FETCH EXACT", sql)

    def test_search_normalizes_euclidean_distance_scores(self):
        store = self.create_store(distance="EUCLIDEAN")
        self.mock_cursor.fetchall.return_value = [("memory-1", 3.0, '{"category": "movies"}')]

        results = store.search("movie preference", [0.1, 0.2, 0.3], top_k=1, filters={"user_id": "alice"})

        sql = self.mock_cursor.execute.call_args.args[0]
        self.assertIn("VECTOR_DISTANCE(EMBEDDING, :query_vector, EUCLIDEAN)", sql)
        self.assertAlmostEqual(results[0].score, 0.25)

    def test_keyword_search_uses_json_textcontains_and_filters(self):
        store = self.create_store()
        store._keyword_search_available = True
        self.mock_cursor.fetchall.return_value = [("memory-1", 12, '{"category": "movies"}')]

        results = store.keyword_search(
            "vector memory",
            top_k=2,
            filters={"agent_id": "agent-1", "category": "movies"},
        )

        sql = self.mock_cursor.execute.call_args.args[0]
        params = self.mock_cursor.execute.call_args.args[1]
        self.assertIn("JSON_TEXTCONTAINS(PAYLOAD, '$.text_lemmatized', :keyword_query, 1)", sql)
        self.assertIn("AGENT_ID = :filter_0", sql)
        self.assertIn("JSON_VALUE(PAYLOAD, '$.category') = :filter_1", sql)
        self.assertIn("ORDER BY SCORE(1) DESC", sql)
        self.assertIn("FETCH FIRST 2 ROWS ONLY", sql)
        self.assertEqual(params["keyword_query"], "vector | memory")
        self.assertEqual(results[0].id, "memory-1")
        self.assertEqual(results[0].payload["category"], "movies")

    def test_falls_back_to_exact_when_hnsw_creation_runs_out_of_space(self):
        def execute_side_effect(sql, *args, **kwargs):
            if "CREATE VECTOR INDEX" in str(sql):
                raise Exception("ORA-51962: The vector memory area is out of space for the current container.")
            return MagicMock()

        self.mock_cursor.execute.side_effect = execute_side_effect
        with patch("mem0.vector_stores.oracle.oracledb.DatabaseError", Exception):
            store = self.create_store(search_mode="approx", index={"create": True, "type": "hnsw"})
            store.create_col()

        self.assertEqual(store.search_mode, "exact")
        self.assertFalse(store._vector_index_available)
        self.assertTrue(store._fallback_to_exact_activated)

    def test_delete_updates_get_list_and_reset(self):
        store = self.create_store(index={"create": False})

        store.delete("memory-1")
        self.assertIn("DELETE FROM MEM0_TEST WHERE ID = :vector_id", self.executed_sql())

        store.update("memory-1", vector=[0.1, 0.2, 0.3], payload={"user_id": "alice"})
        self.assertIn("UPDATE MEM0_TEST SET", self.executed_sql())
        self.assertIn("UPDATED_AT = CURRENT_TIMESTAMP", self.executed_sql())

        self.mock_cursor.fetchone.return_value = ("memory-1", '{"user_id": "alice"}')
        result = store.get("memory-1")
        self.assertEqual(result.id, "memory-1")
        self.assertEqual(result.payload["user_id"], "alice")

        self.mock_cursor.fetchall.return_value = [("memory-1", '{"user_id": "alice"}')]
        listed = store.list(filters={"user_id": "alice"}, top_k=1)
        self.assertEqual(listed[0].id, "memory-1")

        self.mock_cursor.fetchone.side_effect = [("MEM0_TEST",), None, None, None, None, None]
        store.reset()
        sql = self.executed_sql()
        self.assertIn("DROP TABLE MEM0_TEST PURGE", sql)
        self.assertIn("CREATE TABLE MEM0_TEST", sql)


if __name__ == "__main__":
    unittest.main()
