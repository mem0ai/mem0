from unittest.mock import patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.gemini import GoogleGenAIEmbedding


@pytest.fixture
def mock_genai():
    with patch("mem0.embeddings.gemini.genai.embed_content") as mock_genai:
        yield mock_genai


@pytest.fixture
def config():
    return BaseEmbedderConfig(api_key="dummy_api_key", model="test_model", embedding_dims=786)


def test_embed_query(mock_genai, config):
    mock_embedding_response = {"embedding": [0.1, 0.2, 0.3, 0.4]}
    mock_genai.return_value = mock_embedding_response

    embedder = GoogleGenAIEmbedding(config)

    text = "Hello, world!"
    embedding = embedder.embed(text)

    assert embedding == [0.1, 0.2, 0.3, 0.4]
    mock_genai.assert_called_once_with(model="test_model", content="Hello, world!", output_dimensionality=786)
