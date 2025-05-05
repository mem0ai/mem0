import os
import unittest
from unittest.mock import MagicMock, patch

import dotenv

try:
    from opensearchpy import AWSV4SignerAuth, OpenSearch
except ImportError:
    raise ImportError("OpenSearch requires extra dependencies. Install with `pip install opensearch-py`") from None

from mem0.vector_stores.opensearch import OpenSearchDB


class TestOpenSearchDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        dotenv.load_dotenv()
        cls.original_env = {
            "OS_URL": os.getenv("OS_URL", "http://localhost:9200"),
            "OS_USERNAME": os.getenv("OS_USERNAME", "test_user"),
            "OS_PASSWORD": os.getenv("OS_PASSWORD", "test_password"),
        }
        os.environ["OS_URL"] = "http://localhost"
        os.environ["OS_USERNAME"] = "test_user"
        os.environ["OS_PASSWORD"] = "test_password"

    def setUp(self):
        self.client_mock = MagicMock(spec=OpenSearch)
        self.client_mock.indices = MagicMock()
        self.client_mock.indices.exists = MagicMock(return_value=False)
        self.client_mock.indices.create = MagicMock()
        self.client_mock.indices.delete = MagicMock()
        self.client_mock.indices.get_alias = MagicMock()
        self.client_mock.get = MagicMock()
        self.client_mock.update = MagicMock()
        self.client_mock.delete = MagicMock()
        self.client_mock.search = MagicMock()

        patcher = patch("mem0.vector_stores.opensearch.OpenSearch", return_value=self.client_mock)
        self.mock_os = patcher.start()
        self.addCleanup(patcher.stop)

        self.os_db = OpenSearchDB(
            host=os.getenv("OS_URL"),
            port=9200,
            collection_name="test_collection",
            embedding_model_dims=1536,
            user=os.getenv("OS_USERNAME"),
            password=os.getenv("OS_PASSWORD"),
            verify_certs=False,
            use_ssl=False,
            auto_create_index=False,
        )
        self.client_mock.reset_mock()

    @classmethod
    def tearDownClass(cls):
        for key, value in cls.original_env.items():
            if value is not None:
                os.environ[key] = value
            else:
                os.environ.pop(key, None)

    def tearDown(self):
        self.client_mock.reset_mock()

    def test_create_index(self):
        self.client_mock.indices.exists.return_value = False
        self.os_db.create_index()
        self.client_mock.indices.create.assert_called_once()
        create_args = self.client_mock.indices.create.call_args[1]
        self.assertEqual(create_args["index"], "test_collection")
        mappings = create_args["body"]["mappings"]["properties"]
        self.assertEqual(mappings["vector"]["type"], "knn_vector")
        self.assertEqual(mappings["vector"]["dimension"], 1536)
        self.client_mock.reset_mock()
        self.client_mock.indices.exists.return_value = True
        self.os_db.create_index()
        self.client_mock.indices.create.assert_not_called()

    def test_insert(self):
        vectors = [[0.1] * 1536, [0.2] * 1536]
        payloads = [{"key1": "value1"}, {"key2": "value2"}]
        ids = ["id1", "id2"]
        with patch("mem0.vector_stores.opensearch.bulk") as mock_bulk:
            mock_bulk.return_value = (2, [])
            results = self.os_db.insert(vectors=vectors, payloads=payloads, ids=ids)
            mock_bulk.assert_called_once()
            actions = mock_bulk.call_args[0][1]
            self.assertEqual(actions[0]["_index"], "test_collection")
            self.assertEqual(actions[0]["_id"], "id1")
            self.assertEqual(actions[0]["_source"]["vector"], vectors[0])
            self.assertEqual(actions[0]["_source"]["metadata"], payloads[0])
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0].id, "id1")
            self.assertEqual(results[0].payload, payloads[0])

    def test_get(self):
        mock_response = {"_id": "id1", "_source": {"metadata": {"key1": "value1"}}}
        self.client_mock.get.return_value = mock_response
        result = self.os_db.get("id1")
        self.client_mock.get.assert_called_once_with(index="test_collection", id="id1")
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "id1")
        self.assertEqual(result.payload, {"key1": "value1"})

    def test_update(self):
        vector = [0.3] * 1536
        payload = {"key3": "value3"}
        self.os_db.update("id1", vector=vector, payload=payload)
        self.client_mock.update.assert_called_once()
        update_args = self.client_mock.update.call_args[1]
        self.assertEqual(update_args["index"], "test_collection")
        self.assertEqual(update_args["id"], "id1")
        self.assertEqual(update_args["body"], {"doc": {"vector": vector, "metadata": payload}})

    def test_list_cols(self):
        self.client_mock.indices.get_alias.return_value = {"test_collection": {}}
        result = self.os_db.list_cols()
        self.client_mock.indices.get_alias.assert_called_once()
        self.assertEqual(result, ["test_collection"])

    def test_search(self):
        mock_response = {
            "hits": {
                "hits": [
                    {"_id": "id1", "_score": 0.8, "_source": {"vector": [0.1] * 1536, "metadata": {"key1": "value1"}}}
                ]
            }
        }
        self.client_mock.search.return_value = mock_response
        vectors = [[0.1] * 1536]
        results = self.os_db.search(query="", vectors=vectors, limit=5)
        self.client_mock.search.assert_called_once()
        search_args = self.client_mock.search.call_args[1]
        self.assertEqual(search_args["index"], "test_collection")
        body = search_args["body"]
        self.assertIn("knn", body["query"])
        self.assertIn("vector", body["query"]["knn"])
        self.assertEqual(body["query"]["knn"]["vector"]["vector"], vectors)
        self.assertEqual(body["query"]["knn"]["vector"]["k"], 5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "id1")
        self.assertEqual(results[0].score, 0.8)
        self.assertEqual(results[0].payload, {"key1": "value1"})

    def test_delete(self):
        self.os_db.delete(vector_id="id1")
        self.client_mock.delete.assert_called_once_with(index="test_collection", id="id1")

    def test_delete_col(self):
        self.os_db.delete_col()
        self.client_mock.indices.delete.assert_called_once_with(index="test_collection")

    def test_init_with_http_auth(self):
        mock_credentials = MagicMock()
        mock_signer = AWSV4SignerAuth(mock_credentials, "us-east-1", "es")

        with patch("mem0.vector_stores.opensearch.OpenSearch") as mock_opensearch:
            OpenSearchDB(
                host="localhost",
                port=9200,
                collection_name="test_collection",
                embedding_model_dims=1536,
                http_auth=mock_signer,
                verify_certs=True,
                use_ssl=True,
                auto_create_index=False,
            )

            # Verify OpenSearch was initialized with correct params
            mock_opensearch.assert_called_once_with(
                hosts=[{"host": "localhost", "port": 9200}],
                http_auth=mock_signer,
                use_ssl=True,
                verify_certs=True,
                connection_class=unittest.mock.ANY,
            )
