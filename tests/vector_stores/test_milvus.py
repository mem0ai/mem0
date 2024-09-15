import unittest
from unittest.mock import MagicMock
from mem0.vector_stores.milvus import MilvusDB, OutputData, MetricType


class TestMilvusDB(unittest.TestCase):

    def setUp(self):
        self.mock_client = MagicMock()
        self.collection_name = "test_collection"
        self.embedding_model_dims = 1536
        self.metric_type = MetricType.COSINE
        self.url = "http://localhost:19530"
        self.token = "dummy_token"

        self.db = MilvusDB(
            url=self.url,
            token=self.token,
            collection_name=self.collection_name,
            embedding_model_dims=self.embedding_model_dims,
            metric_type=self.metric_type,
        )
        self.db.client = self.mock_client

    def test_create_col(self):
        self.mock_client.has_collection.return_value = False
        self.db.create_col(self.collection_name, vector_size=self.embedding_model_dims)
        self.mock_client.create_collection.assert_called_once()

    def test_insert(self):
        ids = ["id1", "id2"]
        vectors = [[0.1, 0.2], [0.3, 0.4]]
        payloads = [{"meta": "data1"}, {"meta": "data2"}]
        self.db.insert(ids, vectors, payloads)
        self.mock_client.insert.assert_called_once_with(
            collection_name=self.collection_name,
            data={"id": "id1", "vectors": [0.1, 0.2], "metadata": {"meta": "data1"}},
        )

    def test_create_filter(self):
        filters = {"user_id": "123", "agent_id": "456"}
        expected_filter = (
            '(metadata["user_id"] == "123") and (metadata["agent_id"] == "456")'
        )
        self.assertEqual(self.db._create_filter(filters), expected_filter)

    def test_parse_output(self):
        data = [
            {"id": "id1", "distance": 0.1, "entity": {"metadata": {"key": "value1"}}}
        ]
        parsed_data = self.db._parse_output(data)
        self.assertEqual(len(parsed_data), 1)
        self.assertEqual(parsed_data[0].id, "id1")
        self.assertEqual(parsed_data[0].score, 0.1)
        self.assertEqual(parsed_data[0].payload, {"key": "value1"})

    def test_search(self):
        query = [0.1, 0.2]
        hits = [
            {"id": "id1", "distance": 0.5, "entity": {"metadata": {"key": "value"}}}
        ]
        self.mock_client.search.return_value = [hits]
        result = self.db.search(query)
        self.assertEqual(result[0].id, "id1")
        self.assertEqual(result[0].score, 0.5)
        self.assertEqual(result[0].payload, {"key": "value"})

    def test_delete(self):
        vector_id = "id1"
        self.db.delete(vector_id)
        self.mock_client.delete.assert_called_once_with(
            collection_name=self.collection_name, ids=vector_id
        )

    def test_update(self):
        vector_id = "id1"
        vector = [0.1, 0.2]
        payload = {"key": "new_value"}
        self.db.update(vector_id, vector, payload)
        self.mock_client.upsert.assert_called_once_with(
            collection_name=self.collection_name,
            data={"id": vector_id, "vectors": vector, "metadata": payload},
        )

    def test_get(self):
        vector_id = "id1"
        mock_result = [{"id": "id1", "metadata": {"key": "value"}}]
        self.mock_client.get.return_value = mock_result
        result = self.db.get(vector_id)
        self.assertEqual(result.id, "id1")
        self.assertEqual(result.payload, {"key": "value"})

    def test_list_cols(self):
        self.db.list_cols()
        self.mock_client.list_collections.assert_called_once()

    def test_delete_col(self):
        self.db.delete_col()
        self.mock_client.drop_collection.assert_called_once_with(
            collection_name=self.collection_name
        )

    def test_col_info(self):
        self.db.col_info()
        self.mock_client.get_collection_stats.assert_called_once_with(
            collection_name=self.collection_name
        )

    def test_list(self):
        filters = {"key": "value"}
        mock_result = [{"id": "id1", "metadata": {"key": "value"}}]
        self.mock_client.query.return_value = mock_result
        result = self.db.list(filters)
        self.assertEqual(len(result[0]), 1)
        self.assertEqual(result[0][0].id, "id1")
        self.assertEqual(result[0][0].payload, {"key": "value"})


if __name__ == "__main__":
    unittest.main()
