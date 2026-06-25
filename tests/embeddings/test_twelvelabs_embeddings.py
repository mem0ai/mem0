import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.twelvelabs import TwelveLabsEmbedding


@pytest.fixture
def mock_twelvelabs_client():
    with patch("mem0.embeddings.twelvelabs.TwelveLabs") as mock_twelvelabs:
        mock_client = Mock()
        mock_twelvelabs.return_value = mock_client
        yield mock_client


def test_defaults_and_embed(mock_twelvelabs_client):
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = TwelveLabsEmbedding(config)

    # Marengo defaults: marengo3.0, 512 dims.
    assert embedder.config.model == "marengo3.0"
    assert embedder.config.embedding_dims == 512

    segment = Mock(float_=[0.1, 0.2, 0.3])
    response = Mock(text_embedding=Mock(segments=[segment]))
    mock_twelvelabs_client.embed.create.return_value = response

    embedding = embedder.embed("Sample text to embed.")

    mock_twelvelabs_client.embed.create.assert_called_once_with(model_name="marengo3.0", text="Sample text to embed.")
    assert embedding == [0.1, 0.2, 0.3]


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("TWELVELABS_API_KEY", raising=False)
    with pytest.raises(ValueError, match="API key is required"):
        TwelveLabsEmbedding(BaseEmbedderConfig())


def test_summarize_video(mock_twelvelabs_client):
    embedder = TwelveLabsEmbedding(BaseEmbedderConfig(api_key="test_key"))
    mock_twelvelabs_client.analyze.return_value = Mock(data="A cat plays the piano.")

    summary = embedder.summarize_video("https://example.com/cat.mp4")

    assert summary == "A cat plays the piano."
    _, kwargs = mock_twelvelabs_client.analyze.call_args
    assert kwargs["model_name"] == "pegasus1.5"


@pytest.mark.skipif(not os.getenv("TWELVELABS_API_KEY"), reason="TWELVELABS_API_KEY not set")
def test_embed_live():
    embedder = TwelveLabsEmbedding(BaseEmbedderConfig())
    embedding = embedder.embed("a cat playing piano")
    assert len(embedding) == 512
    assert all(isinstance(x, float) for x in embedding)
