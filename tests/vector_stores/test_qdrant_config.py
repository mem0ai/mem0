from unittest.mock import MagicMock

import pytest

from mem0.configs.vector_stores.qdrant import QdrantConfig
from mem0.vector_stores.configs import VectorStoreConfig
from mem0.vector_stores import qdrant as qdrant_module


def test_qdrant_config_accepts_explicit_https_false():
    config = QdrantConfig(
        host="127.0.0.1",
        port=6333,
        api_key="test-key",
        https=False,
    )

    assert config.https is False


def test_qdrant_passes_explicit_https_to_client(monkeypatch):
    client_cls = MagicMock()
    monkeypatch.setattr(qdrant_module, "QdrantClient", client_cls)
    monkeypatch.setattr(qdrant_module.Qdrant, "create_col", lambda *args, **kwargs: None)

    qdrant_module.Qdrant(
        collection_name="memories",
        embedding_model_dims=1536,
        host="127.0.0.1",
        port=6333,
        api_key="test-key",
        https=False,
    )

    client_cls.assert_called_once_with(
        api_key="test-key",
        host="127.0.0.1",
        port=6333,
        https=False,
    )


def test_remote_qdrant_config_does_not_inject_local_path():
    config = VectorStoreConfig(
        provider="qdrant",
        config={"url": "https://qdrant.internal:6333", "api_key": "test-key"},
    )

    assert config.config.url == "https://qdrant.internal:6333"
    assert config.config.path is None


def test_default_sdk_qdrant_config_keeps_explicit_local_fallback():
    config = VectorStoreConfig(provider="qdrant")

    assert config.config.path == "/tmp/qdrant"


@pytest.mark.parametrize("extra", [{"api_key": "secret"}, {"https": False}])
def test_local_qdrant_rejects_remote_only_options(extra):
    with pytest.raises(ValueError, match="remote-only"):
        QdrantConfig(path="/tmp/qdrant", **extra)


def test_qdrant_adapter_uses_explicit_local_path_only(monkeypatch):
    client_cls = MagicMock()
    monkeypatch.setattr(qdrant_module, "QdrantClient", client_cls)
    monkeypatch.setattr(qdrant_module.Qdrant, "create_col", lambda *args, **kwargs: None)

    store = qdrant_module.Qdrant(
        collection_name="memories",
        embedding_model_dims=1536,
        path="/tmp/qdrant",
    )

    client_cls.assert_called_once_with(path="/tmp/qdrant")
    assert store.is_local is True


def test_qdrant_adapter_rejects_ambiguous_local_mode(monkeypatch):
    client_cls = MagicMock()
    monkeypatch.setattr(qdrant_module, "QdrantClient", client_cls)

    with pytest.raises(ValueError, match="cannot use api_key"):
        qdrant_module.Qdrant(
            collection_name="memories",
            embedding_model_dims=1536,
            path="/tmp/qdrant",
            api_key="secret",
        )

    client_cls.assert_not_called()
