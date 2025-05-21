import os
import unittest
from unittest.mock import MagicMock, Mock, patch

import dotenv

try:
    from elasticsearch import Elasticsearch
except ImportError:
    raise ImportError("Elasticsearch requires extra dependencies. Install with `pip install elasticsearch`") from None

from mem0.vector_stores.elasticsearch import ElasticsearchDB, OutputData


class TestElasticsearchDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load environment variables before any test
        dotenv.load_dotenv()

        # Save original environment variables
        cls.original_env = {
            "ES_URL": os.getenv("ES_URL", "http://localhost:9200"),
            "ES_USERNAME": os.getenv("ES_USERNAME", "test_user"),
            "ES_PASSWORD": os.getenv("ES_PASSWORD", "test_password"),
            "ES_CLOUD_ID": os.getenv("ES_CLOUD_ID", "test_cloud_id"),
        }

        # Set test environment variables
        os.environ["ES_URL"] = "http://localhost"
        os.environ["ES_USERNAME"] = "test_user"
        os.environ["ES_PASSWORD"] = "test_password"

    def setUp(self):
        # Create a mock Elasticsearch client with proper attributes
        self.client_mock = MagicMock(spec=Elasticsearch)
        self.client_mock.indices = MagicMock()
        self.client_mock.indices.exists = MagicMock(return_value=False)
        self.client_mock.indices.create = MagicMock()
        self.client_mock.indices.delete = MagicMock()
        self.client_mock.indices.get_alias = MagicMock()

        # Start patches BEFORE creating ElasticsearchDB instance
        patcher = patch("mem0.vector_stores.elasticsearch.Elasticsearch", return_value=self.client_mock)
        self.mock_es = patcher.start()
        self.addCleanup(patcher.stop)

        # Initialize ElasticsearchDB with test config and auto_create_index=False
        self.es_db = ElasticsearchDB(
            host=os.getenv("ES_URL"),
            port=9200,
            collection_name="test_collection",
            embedding_model_dims=1536,
            user=os.getenv("ES_USERNAME"),
            password=os.getenv("ES_PASSWORD"),
            verify_certs=False,
            use_ssl=False,
            auto_create_index=False,  # Disable auto creation for tests
        )

        # Reset mock counts after initialization
        self.client_mock.reset_mock()

    @classmethod
    def tearDownClass(cls):
        # Restore original environment variables
        for key, value in cls.original_env.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)

    def tearDown(self):
        self.client_mock.reset_mock()
        # No need to stop patches here as we're using addCleanup

    def test_create_index(self):
        # Test when index doesn't exist
        self.client_mock.indices.exists.return_value = False
        self.es_db.create_index()

        # Verify index creation was called with correct settings
        self.client_mock.indices.create.assert_called_once()
        create_args = self.client_mock.indices.create.call_args[1]

        # Verify basic index settings
        self.assertEqual(create_args["index"], "test_collection")
        self.assertIn("mappings", create_args["body"])

        # Verify field mappings
        mappings = create_args["body"]["mappings"]["properties"]
        self.assertEqual(mappings["text"]["type"], "text")
        self.assertEqual(mappings["vector"]["type"], "dense_vector")
        self.assertEqual(mappings["vector"]["dims"], 1536)
        self.assertEqual(mappings["vector"]["index"], True)
        self.assertEqual(mappings["vector"]["similarity"], "cosine")
        self.assertEqual(mappings["metadata"]["type"], "object")

        # Reset mocks for next test
        self.client_mock.reset_mock()

        # Test when index already exists
        self.client_mock.indices.exists.return_value = True
        self.es_db.create_index()

        # Verify create was not called when index exists
        self.client_mock.indices.create.assert_not_called()

    def test_auto_create_index(self):
        # Reset mock
        self.client_mock.reset_mock()

        # Test with auto_create_index=True
        ElasticsearchDB(
            host=os.getenv("ES_URL"),
            port=9200,
            collection_name="test_collection",
            embedding_model_dims=1536,
            user=os.getenv("ES_USERNAME"),
            password=os.getenv("ES_PASSWORD"),
            verify_certs=False,
            use_ssl=False,
            auto_create_index=True,
        )

        # Verify create_index was called during initialization
        self.client_mock.indices.exists.assert_called_once()

        # Reset mock
        self.client_mock.reset_mock()

        # Test with auto_create_index=False
        ElasticsearchDB(
            host=os.getenv("ES_URL"),
            port=9200,
            collection_name="test_collection",
            embedding_model_dims=1536,
            user=os.getenv("ES_USERNAME"),
            password=os.getenv("ES_PASSWORD"),
            verify_certs=False,
            use_ssl=False,
            auto_create_index=False,
        )

        # Verify create_index was not called during initialization
        self.client_mock.indices.exists.assert_not_called()

    def test_insert(self):
        # Test data
        vectors = [[0.1] * 1536, [0.2] * 1536]
        payloads = [{"key1": "value1"}, {"key2": "value2"}]
        ids = ["id1", "id2"]

        # Mock bulk operation
        with patch("mem0.vector_stores.elasticsearch.bulk") as mock_bulk:
            mock_bulk.return_value = (2, [])  # Simulate successful bulk insert

            # Perform insert
            results = self.es_db.insert(vectors=vectors, payloads=payloads, ids=ids)

            # Verify bulk was called
            mock_bulk.assert_called_once()

            # Verify bulk actions format
            actions = mock_bulk.call_args[0][1]
            self.assertEqual(len(actions), 2)
            self.assertEqual(actions[0]["_index"], "test_collection")
            self.assertEqual(actions[0]["_id"], "id1")
            self.assertEqual(actions[0]["_source"]["vector"], vectors[0])
            self.assertEqual(actions[0]["_source"]["metadata"], payloads[0])

            # Verify returned objects
            self.assertEqual(len(results), 2)
            self.assertIsInstance(results[0], OutputData)
            self.assertEqual(results[0].id, "id1")
            self.assertEqual(results[0].payload, payloads[0])

    def test_search(self):
        # Mock search response
        mock_response = {
            "hits": {
                "hits": [
                    {"_id": "id1", "_score": 0.8, "_source": {"vector": [0.1] * 1536, "metadata": {"key1": "value1"}}}
                ]
            }
        }
        self.client_mock.search.return_value = mock_response

        # Perform search
        vectors = [[0.1] * 1536]
        results = self.es_db.search(query="", vectors=vectors, limit=5)

        # Verify search call
        self.client_mock.search.assert_called_once()
        search_args = self.client_mock.search.call_args[1]

        # Verify search parameters
        self.assertEqual(search_args["index"], "test_collection")
        body = search_args["body"]

        # Verify KNN query structure
        self.assertIn("knn", body)
        self.assertEqual(body["knn"]["field"], "vector")
        self.assertEqual(body["knn"]["query_vector"], vectors)
        self.assertEqual(body["knn"]["k"], 5)
        self.assertEqual(body["knn"]["num_candidates"], 10)

        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "id1")
        self.assertEqual(results[0].score, 0.8)
        self.assertEqual(results[0].payload, {"key1": "value1"})

    def test_custom_search_query(self):
        # Mock custom search query
        self.es_db.custom_search_query = Mock()
        self.es_db.custom_search_query.return_value = {"custom_key": "custom_value"}

        # Perform search
        vectors = [[0.1] * 1536]
        limit = 5
        filters = {"key1": "value1"}
        self.es_db.search(query="", vectors=vectors, limit=limit, filters=filters)

        # Verify custom search query function was called
        self.es_db.custom_search_query.assert_called_once_with(vectors, limit, filters)

        # Verify custom search query was used
        self.client_mock.search.assert_called_once_with(
            index=self.es_db.collection_name, body={"custom_key": "custom_value"}
        )

    def test_get(self):
        # Mock get response with correct structure
        mock_response = {
            "_id": "id1",
            "_source": {"vector": [0.1] * 1536, "metadata": {"key": "value"}, "text": "sample text"},
        }
        self.client_mock.get.return_value = mock_response

        # Perform get
        result = self.es_db.get(vector_id="id1")

        # Verify get call
        self.client_mock.get.assert_called_once_with(index="test_collection", id="id1")

        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "id1")
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.payload, {"key": "value"})

    def test_get_not_found(self):
        # Mock get raising exception
        self.client_mock.get.side_effect = Exception("Not found")

        # Verify get returns None when document not found
        result = self.es_db.get(vector_id="nonexistent")
        self.assertIsNone(result)

    def test_list(self):
        # Mock search response with scores
        mock_response = {
            "hits": {
                "hits": [
                    {"_id": "id1", "_source": {"vector": [0.1] * 1536, "metadata": {"key1": "value1"}}, "_score": 1.0},
                    {"_id": "id2", "_source": {"vector": [0.2] * 1536, "metadata": {"key2": "value2"}}, "_score": 0.8},
                ]
            }
        }
        self.client_mock.search.return_value = mock_response

        # Perform list operation
        results = self.es_db.list(limit=10)

        # Verify search call
        self.client_mock.search.assert_called_once()

        # Verify results
        self.assertEqual(len(results), 1)  # Outer list
        self.assertEqual(len(results[0]), 2)  # Inner list
        self.assertIsInstance(results[0][0], OutputData)
        self.assertEqual(results[0][0].id, "id1")
        self.assertEqual(results[0][0].payload, {"key1": "value1"})
        self.assertEqual(results[0][1].id, "id2")
        self.assertEqual(results[0][1].payload, {"key2": "value2"})

    def test_delete(self):
        # Perform delete
        self.es_db.delete(vector_id="id1")

        # Verify delete call
        self.client_mock.delete.assert_called_once_with(index="test_collection", id="id1")

    def test_list_cols(self):
        # Mock indices response
        mock_indices = {"index1": {}, "index2": {}}
        self.client_mock.indices.get_alias.return_value = mock_indices

        # Get collections
        result = self.es_db.list_cols()

        # Verify result
        self.assertEqual(result, ["index1", "index2"])

    def test_delete_col(self):
        # Delete collection
        self.es_db.delete_col()

        # Verify delete call
        self.client_mock.indices.delete.assert_called_once_with(index="test_collection")
