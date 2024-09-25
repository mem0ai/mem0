
from unittest.mock import patch

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.huggingface import HuggingFaceEmbedder


def test_huggingface_embedder_with_model(monkeypatch):
    config = BaseEmbedderConfig(model="test-model", model_kwargs={"param": "value"})
    with patch('embedchain.embedder.huggingface.HuggingFaceEmbeddings') as mock_embeddings:
        embedder = HuggingFaceEmbedder(config=config)
        assert embedder.config.model == "test-model"
        assert embedder.config.model_kwargs == {"param": "value"}
        mock_embeddings.assert_called_once_with(
            model_name="test-model",
            model_kwargs={"param": "value"}
        )


