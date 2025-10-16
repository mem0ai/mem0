import os
import threading
import unittest
from unittest.mock import MagicMock, patch

import dotenv

try:
    from opensearchpy import AWSV4SignerAuth, OpenSearch
except ImportError:
    raise ImportError("OpenSearch requires extra dependencies. Install with `pip install opensearch-py`") from None

from mem0 import Memory
from mem0.configs.base import MemoryConfig
from mem0.vector_stores.opensearch import OpenSearchDB


# Mock classes for testing OpenSearch with AWS authentication
class MockFieldInfo:
    """Mock pydantic field info."""
    def __init__(self, default=None):
        self.default = default


class MockOpenSearchConfig:
    
    model_fields = {
        'collection_name': MockFieldInfo(default="default_collection"),
        'host': MockFieldInfo(default="localhost"),
        'port': MockFieldInfo(default=9200),
        'embedding_model_dims': MockFieldInfo(default=1536),
        'http_auth': MockFieldInfo(default=None),
        'auth': MockFieldInfo(default=None),
        'credentials': MockFieldInfo(default=None),
        'connection_class': MockFieldInfo(default=None),
        'use_ssl': MockFieldInfo(default=False),
        'verify_certs': MockFieldInfo(default=False),
    }
    
    def __init__(self, collection_name="test_collection", include_auth=True, **kwargs):
        self.collection_name = collection_name
        self.host = kwargs.get("host", "localhost")
        self.port = kwargs.get("port", 9200)
        self.embedding_model_dims = kwargs.get("embedding_model_dims", 1536)
        self.use_ssl = kwargs.get("use_ssl", True)
        self.verify_certs = kwargs.get("verify_certs", True)
        
        if any(field in kwargs for field in ["http_auth", "auth", "credentials", "connection_class"]):
            self.http_auth = kwargs.get("http_auth")
            self.auth = kwargs.get("auth")
            self.credentials = kwargs.get("credentials")
            self.connection_class = kwargs.get("connection_class")
        elif include_auth:
            self.http_auth = MockAWSAuth()
            self.auth = MockAWSAuth()
            self.credentials = {"key": "value"}
            self.connection_class = MockConnectionClass()
        else:
            self.http_auth = None
            self.auth = None
            self.credentials = None
            self.connection_class = None


class MockAWSAuth:
    
    def __init__(self):
        self._lock = threading.Lock()
        self.region = "us-east-1"
    
    def __deepcopy__(self, memo):
        raise TypeError("cannot pickle '_thread.lock' object")


class MockConnectionClass:
    
    def __init__(self):
        self._state = {"connected": False}
    
    def __deepcopy__(self, memo):
        raise TypeError("cannot pickle connection state")


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
        self.client_mock.indices.refresh = MagicMock()
        self.client_mock.get = MagicMock()
        self.client_mock.update = MagicMock()
        self.client_mock.delete = MagicMock()
        self.client_mock.search = MagicMock()
        self.client_mock.index = MagicMock(return_value={"_id": "doc1"})

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
        self.assertEqual(mappings["vector_field"]["type"], "knn_vector")
        self.assertEqual(mappings["vector_field"]["dimension"], 1536)
        self.client_mock.reset_mock()
        self.client_mock.indices.exists.return_value = True
        self.os_db.create_index()
        self.client_mock.indices.create.assert_not_called()

    def test_insert(self):
        vectors = [[0.1] * 1536, [0.2] * 1536]
        payloads = [{"key1": "value1"}, {"key2": "value2"}]
        ids = ["id1", "id2"]

        # Mock the index method
        self.client_mock.index = MagicMock()

        results = self.os_db.insert(vectors=vectors, payloads=payloads, ids=ids)

        # Verify index was called twice (once for each vector)
        self.assertEqual(self.client_mock.index.call_count, 2)

        # Check first call
        first_call = self.client_mock.index.call_args_list[0]
        self.assertEqual(first_call[1]["index"], "test_collection")
        self.assertEqual(first_call[1]["body"]["vector_field"], vectors[0])
        self.assertEqual(first_call[1]["body"]["payload"], payloads[0])
        self.assertEqual(first_call[1]["body"]["id"], ids[0])

        # Check second call
        second_call = self.client_mock.index.call_args_list[1]
        self.assertEqual(second_call[1]["index"], "test_collection")
        self.assertEqual(second_call[1]["body"]["vector_field"], vectors[1])
        self.assertEqual(second_call[1]["body"]["payload"], payloads[1])
        self.assertEqual(second_call[1]["body"]["id"], ids[1])

        # Check results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, "id1")
        self.assertEqual(results[0].payload, payloads[0])
        self.assertEqual(results[1].id, "id2")
        self.assertEqual(results[1].payload, payloads[1])

    def test_get(self):
        mock_response = {"hits": {"hits": [{"_id": "doc1", "_source": {"id": "id1", "payload": {"key1": "value1"}}}]}}
        self.client_mock.search.return_value = mock_response
        result = self.os_db.get("id1")
        self.client_mock.search.assert_called_once()
        search_args = self.client_mock.search.call_args[1]
        self.assertEqual(search_args["index"], "test_collection")
        self.assertIsNotNone(result)
        self.assertEqual(result.id, "id1")
        self.assertEqual(result.payload, {"key1": "value1"})

        # Test when no results are found
        self.client_mock.search.return_value = {"hits": {"hits": []}}
        result = self.os_db.get("nonexistent")
        self.assertIsNone(result)

    def test_update(self):
        vector = [0.3] * 1536
        payload = {"key3": "value3"}
        mock_search_response = {"hits": {"hits": [{"_id": "doc1", "_source": {"id": "id1"}}]}}
        self.client_mock.search.return_value = mock_search_response
        self.os_db.update("id1", vector=vector, payload=payload)
        self.client_mock.update.assert_called_once()
        update_args = self.client_mock.update.call_args[1]
        self.assertEqual(update_args["index"], "test_collection")
        self.assertEqual(update_args["id"], "doc1")
        self.assertEqual(update_args["body"], {"doc": {"vector_field": vector, "payload": payload}})

    def test_list_cols(self):
        self.client_mock.indices.get_alias.return_value = {"test_collection": {}}
        result = self.os_db.list_cols()
        self.client_mock.indices.get_alias.assert_called_once()
        self.assertEqual(result, ["test_collection"])

    def test_search(self):
        mock_response = {
            "hits": {
                "hits": [
                    {
                        "_id": "id1",
                        "_score": 0.8,
                        "_source": {"vector_field": [0.1] * 1536, "id": "id1", "payload": {"key1": "value1"}},
                    }
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
        self.assertIn("vector_field", body["query"]["knn"])
        self.assertEqual(body["query"]["knn"]["vector_field"]["vector"], vectors)
        self.assertEqual(body["query"]["knn"]["vector_field"]["k"], 10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, "id1")
        self.assertEqual(results[0].score, 0.8)
        self.assertEqual(results[0].payload, {"key1": "value1"})

    def test_delete(self):
        mock_search_response = {"hits": {"hits": [{"_id": "doc1", "_source": {"id": "id1"}}]}}
        self.client_mock.search.return_value = mock_search_response
        self.os_db.delete(vector_id="id1")
        self.client_mock.delete.assert_called_once_with(index="test_collection", id="doc1")

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
            )

            # Verify OpenSearch was initialized with correct params
            mock_opensearch.assert_called_once_with(
                hosts=[{"host": "localhost", "port": 9200}],
                http_auth=mock_signer,
                use_ssl=True,
                verify_certs=True,
                connection_class=unittest.mock.ANY,
                pool_maxsize=20,
            )


# Tests for OpenSearch config deepcopy with AWS authentication (Issue #3464)
@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_safe_deepcopy_config_handles_opensearch_auth(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """Test that _safe_deepcopy_config handles OpenSearch configs with AWS auth objects gracefully."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import _safe_deepcopy_config
    
    config_with_auth = MockOpenSearchConfig(collection_name="opensearch_test", include_auth=True)
    
    safe_config = _safe_deepcopy_config(config_with_auth)
    
    assert safe_config.http_auth is None
    assert safe_config.auth is None
    assert safe_config.credentials is None
    assert safe_config.connection_class is None
    
    assert safe_config.collection_name == "opensearch_test"
    assert safe_config.host == "localhost"
    assert safe_config.port == 9200
    assert safe_config.embedding_model_dims == 1536
    assert safe_config.use_ssl is True
    assert safe_config.verify_certs is True


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create') 
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_safe_deepcopy_config_normal_configs(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """Test that _safe_deepcopy_config handles normal OpenSearch configs without auth."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import _safe_deepcopy_config
    
    config_without_auth = MockOpenSearchConfig(collection_name="normal_test", include_auth=False)
    
    safe_config = _safe_deepcopy_config(config_without_auth)
    
    assert safe_config.collection_name == "normal_test" 
    assert safe_config.host == "localhost"
    assert safe_config.port == 9200
    assert safe_config.embedding_model_dims == 1536
    assert safe_config.use_ssl is True
    assert safe_config.verify_certs is True


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_memory_initialization_opensearch_aws_auth(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """Test that Memory initialization works with OpenSearch configs containing AWS auth."""
    
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    config = MemoryConfig()
    config.vector_store.provider = "opensearch"
    config.vector_store.config = MockOpenSearchConfig(collection_name="mem0_test", include_auth=True)

    memory = Memory(config)

    assert memory is not None
    assert memory.config.vector_store.provider == "opensearch"

    assert mock_vector_factory.call_count >= 2
