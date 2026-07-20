from unittest.mock import MagicMock

from mem0.configs.vector_stores.qdrant import QdrantConfig
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
