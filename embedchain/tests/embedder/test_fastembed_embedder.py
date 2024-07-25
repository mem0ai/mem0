
from unittest.mock import patch

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.fastembed import FastEmbedEmbedder


def test_fastembed_embedder_with_model(monkeypatch):
    model =  "intfloat/multilingual-e5-large"
    model_kwargs = {"threads": 5}
    config = BaseEmbedderConfig(model=model, model_kwargs=model_kwargs)
    with patch('embedchain.embedder.fastembed.TextEmbedding') as mock_embeddings:
        embedder = FastEmbedEmbedder(config=config)
        assert embedder.config.model == model
        assert embedder.config.model_kwargs == model_kwargs
        mock_embeddings.assert_called_once_with(
            model_name=model,
            threads=5
        )