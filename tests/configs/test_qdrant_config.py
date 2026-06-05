from mem0.configs.vector_stores.qdrant import QdrantConfig


def test_qdrant_config_uses_url_and_api_key_from_environment_when_connection_is_unset(monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "test-key")

    config = QdrantConfig(collection_name="memories", embedding_model_dims=1536, path=None)

    assert config.url == "http://localhost:6333"
    assert config.api_key == "test-key"


def test_qdrant_config_explicit_values_override_environment(monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "http://env-qdrant:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "env-key")

    config = QdrantConfig(
        collection_name="memories",
        embedding_model_dims=1536,
        path=None,
        url="https://cloud.qdrant.io",
        api_key="explicit-key",
    )

    assert config.url == "https://cloud.qdrant.io"
    assert config.api_key == "explicit-key"


def test_qdrant_config_keeps_explicit_host_port_when_environment_url_is_set(monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "http://env-qdrant:6333")
    monkeypatch.setenv("QDRANT_API_KEY", "env-key")

    config = QdrantConfig(
        collection_name="memories",
        embedding_model_dims=1536,
        host="localhost",
        port=6333,
    )

    assert config.host == "localhost"
    assert config.port == 6333
    assert config.url is None
    assert config.api_key is None
