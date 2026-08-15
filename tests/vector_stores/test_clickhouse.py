import json
import unittest
from unittest.mock import MagicMock, patch

from mem0.vector_stores.clickhouse import ClickhouseDB


class TestClickhouseDB(unittest.TestCase):
    @patch("mem0.vector_stores.clickhouse.clickhouse_connect")
    def setUp(self, mock_clickhouse_connect):
        self.mock_client = MagicMock()
        mock_clickhouse_connect.get_client.return_value = self.mock_client

        self.db = ClickhouseDB(
            collection_name="test_collection",
            embedding_model_dims=128,
            client=self.mock_client,
        )

    def test_create_col(self):
        self.db.create_col()
        self.mock_client.command.assert_called_with(
            "\n            CREATE TABLE IF NOT EXISTS test_collection (\n                id String,\n                payload String,\n                vector Array(Float32)\n            ) ENGINE = ReplacingMergeTree()\n            ORDER BY id\n        "
        )

    def test_insert(self):
        vectors = [[0.1, 0.2], [0.3, 0.4]]
        payloads = [{"key": "value1"}, {"key": "value2"}]
        ids = ["id1", "id2"]

        self.db.insert(vectors=vectors, payloads=payloads, ids=ids)

        expected_data = [
            ("id1", json.dumps({"key": "value1"}), [0.1, 0.2]),
            ("id2", json.dumps({"key": "value2"}), [0.3, 0.4]),
        ]

        self.mock_client.insert.assert_called_once_with(
            "test_collection",
            expected_data,
            column_names=["id", "payload", "vector"],
        )

    def test_search(self):
        query_vector = [0.1, 0.2]
        
        mock_result = MagicMock()
        mock_result.result_rows = [
            ("id1", json.dumps({"key": "value1"}), 0.95),
            ("id2", json.dumps({"key": "value2"}), 0.85),
        ]
        self.mock_client.query.return_value = mock_result

        results = self.db.search(query=query_vector, top_k=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], "id1")
        self.assertEqual(results[0]["payload"], {"key": "value1"})
        self.assertEqual(results[0]["score"], 0.95)

        self.mock_client.query.assert_called_once()
        called_query = self.mock_client.query.call_args[0][0]
        self.assertIn("1 - cosineDistance", called_query)
        self.assertIn("LIMIT 2", called_query)

    def test_delete(self):
        vector_id = "id1"
        self.db.delete(vector_id)
        self.mock_client.command.assert_called_with(
            "ALTER TABLE test_collection DELETE WHERE id = 'id1'"
        )

    def test_update(self):
        vector_id = "id1"
        vector = [0.5, 0.6]
        payload = {"key": "new_value"}

        mock_get_result = MagicMock()
        mock_get_result.result_rows = [
            ("id1", json.dumps({"key": "old_value"}), [0.1, 0.2])
        ]
        self.mock_client.query.return_value = mock_get_result

        self.db.update(vector_id=vector_id, vector=vector, payload=payload)

        # get is called, then insert, then optimize
        self.mock_client.query.assert_called_with(
            "SELECT id, payload, vector FROM test_collection WHERE id = 'id1' LIMIT 1"
        )
        self.mock_client.insert.assert_called_with(
            "test_collection",
            [("id1", json.dumps({"key": "new_value"}), [0.5, 0.6])],
            column_names=["id", "payload", "vector"],
        )
        self.mock_client.command.assert_called_with(
            "OPTIMIZE TABLE test_collection FINAL"
        )

    def test_get(self):
        vector_id = "id1"
        mock_result = MagicMock()
        mock_result.result_rows = [
            ("id1", json.dumps({"key": "value"}), [0.1, 0.2])
        ]
        self.mock_client.query.return_value = mock_result

        result = self.db.get(vector_id)

        self.assertEqual(result.id, "id1")
        self.assertEqual(result.payload, {"key": "value"})
        self.assertEqual(result.vector, [0.1, 0.2])
        self.mock_client.query.assert_called_once_with(
            "SELECT id, payload, vector FROM test_collection WHERE id = 'id1' LIMIT 1"
        )

    def test_list_cols(self):
        mock_result = MagicMock()
        mock_result.result_rows = [("col1",), ("col2",)]
        self.mock_client.query.return_value = mock_result

        cols = self.db.list_cols()

        self.assertEqual(cols, ["col1", "col2"])
        self.mock_client.query.assert_called_once_with("SHOW TABLES")

    def test_delete_col(self):
        self.db.delete_col()
        self.mock_client.command.assert_called_with(
            "DROP TABLE IF EXISTS test_collection"
        )

    def test_col_info(self):
        mock_result = MagicMock()
        mock_result.result_rows = [(42,)]
        self.mock_client.query.return_value = mock_result

        info = self.db.col_info()

        self.assertEqual(info["name"], "test_collection")
        self.assertEqual(info["count"], 42)
        self.mock_client.query.assert_called_once_with("SELECT count() FROM test_collection")

    def test_list(self):
        mock_result = MagicMock()
        mock_result.result_rows = [
            ("id1", json.dumps({"key": "value1"}), [0.1, 0.2]),
            ("id2", json.dumps({"key": "value2"}), [0.3, 0.4]),
        ]
        self.mock_client.query.return_value = mock_result

        results = self.db.list(top_k=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], "id1")
        self.assertEqual(results[0]["payload"], {"key": "value1"})
        self.assertEqual(results[0]["vector"], [0.1, 0.2])
        
        called_query = self.mock_client.query.call_args[0][0]
        self.assertIn("SELECT id, payload, vector", called_query)
        self.assertIn("LIMIT 2", called_query)
