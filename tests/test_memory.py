import threading
from unittest.mock import MagicMock, patch

import pytest

from mem0 import Memory
from mem0.configs.base import MemoryConfig


class MockFieldInfo:
    """Mock pydantic field info."""
    def __init__(self, default=None):
        self.default = default


class MockOpenSearchConfig:
    """Mock OpenSearch config with AWS auth objects for testing deepcopy issue."""
    
    # Mock pydantic model fields structure as class attribute
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
        
        # If auth fields are explicitly provided in kwargs, use those values (even if None)
        # This happens when _safe_deepcopy_config creates a new instance
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
    """Mock AWS auth object with threading lock (non-serializable)."""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.region = "us-east-1"
    
    def __deepcopy__(self, memo):
        """Prevent deepcopy to simulate real AWS auth behavior."""
        raise TypeError("cannot pickle '_thread.lock' object")


class MockConnectionClass:
    """Mock connection class with state."""
    
    def __init__(self):
        self._state = {"connected": False}
    
    def __deepcopy__(self, memo):
        """Prevent deepcopy to simulate non-serializable connection."""
        raise TypeError("cannot pickle connection state")


@pytest.fixture
def memory_client():
    with patch.object(Memory, "__init__", return_value=None):
        client = Memory()
        client.add = MagicMock(return_value={"results": [{"id": "1", "memory": "Name is John Doe.", "event": "ADD"}]})
        client.get = MagicMock(return_value={"id": "1", "memory": "Name is John Doe."})
        client.update = MagicMock(return_value={"message": "Memory updated successfully!"})
        client.delete = MagicMock(return_value={"message": "Memory deleted successfully!"})
        client.history = MagicMock(return_value=[{"memory": "I like Indian food."}, {"memory": "I like Italian food."}])
        client.get_all = MagicMock(return_value=["Name is John Doe.", "Name is John Doe. I like to code in Python."])
        yield client


def test_create_memory(memory_client):
    data = "Name is John Doe."
    result = memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    assert result["results"][0]["memory"] == data


def test_get_memory(memory_client):
    data = "Name is John Doe."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    result = memory_client.get("1")
    assert result["memory"] == data


def test_update_memory(memory_client):
    data = "Name is John Doe."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    new_data = "Name is John Kapoor."
    update_result = memory_client.update("1", text=new_data)
    assert update_result["message"] == "Memory updated successfully!"


def test_delete_memory(memory_client):
    data = "Name is John Doe."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    delete_result = memory_client.delete("1")
    assert delete_result["message"] == "Memory deleted successfully!"


def test_history(memory_client):
    data = "I like Indian food."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    memory_client.update("1", text="I like Italian food.")
    history = memory_client.history("1")
    assert history[0]["memory"] == "I like Indian food."
    assert history[1]["memory"] == "I like Italian food."


def test_list_memories(memory_client):
    data1 = "Name is John Doe."
    data2 = "Name is John Doe. I like to code in Python."
    memory_client.add([{"role": "user", "content": data1}], user_id="test_user")
    memory_client.add([{"role": "user", "content": data2}], user_id="test_user")
    memories = memory_client.get_all(user_id="test_user")
    assert data1 in memories
    assert data2 in memories


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_collection_name_preserved_after_reset(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    test_collection_name = "mem0"
    config = MemoryConfig()
    config.vector_store.config.collection_name = test_collection_name

    memory = Memory(config)

    assert memory.collection_name == test_collection_name
    assert memory.config.vector_store.config.collection_name == test_collection_name

    memory.reset()

    assert memory.collection_name == test_collection_name
    assert memory.config.vector_store.config.collection_name == test_collection_name

    reset_calls = [call for call in mock_vector_factory.call_args_list if len(mock_vector_factory.call_args_list) > 2]
    if reset_calls:
        reset_config = reset_calls[-1][0][1]  
        assert reset_config.collection_name == test_collection_name, f"Reset used wrong collection name: {reset_config.collection_name}"


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
    
    # This should not raise TypeError even with non-serializable auth objects
    safe_config = _safe_deepcopy_config(config_with_auth)
    
    # Verify auth fields are excluded for security
    assert safe_config.http_auth is None
    assert safe_config.auth is None
    assert safe_config.credentials is None
    assert safe_config.connection_class is None
    
    # Verify normal fields are preserved  
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
    """Test that _safe_deepcopy_config works normally with serializable configs."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import _safe_deepcopy_config
    
    config_without_auth = MockOpenSearchConfig(collection_name="normal_test", include_auth=False)
    
    # This should work with normal deepcopy path
    safe_config = _safe_deepcopy_config(config_without_auth)
    
    # Verify all fields are preserved exactly
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
    """Test that Memory initialization succeeds with OpenSearch + AWS auth configuration.""" 
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    config = MemoryConfig()
    config.vector_store.provider = "opensearch"
    config.vector_store.config = MockOpenSearchConfig(collection_name="mem0_test", include_auth=True)

    # This should not raise TypeError: cannot pickle '_thread.lock' object
    memory = Memory(config)

    # Verify memory was created successfully  
    assert memory is not None
    assert memory.config.vector_store.provider == "opensearch"

    # Verify telemetry config was created safely
    assert mock_vector_factory.call_count >= 2
