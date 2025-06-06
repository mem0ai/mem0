from unittest.mock import Mock, patch

import pytest
from google.genai import types

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.gemini import GoogleGenAIEmbedding


@pytest.fixture
def mock_genai_client():
    with patch("mem0.embeddings.gemini.genai.Client") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def config():
    return BaseEmbedderConfig(api_key="dummy_api_key", model="models/text-embedding-004", embedding_dims=768)


def test_embed_query(mock_genai_client, config):
    # Mock the embedding response structure for the new SDK
    mock_embedding = Mock()
    mock_embedding.values = [0.1, 0.2, 0.3, 0.4]
    
    mock_response = Mock()
    mock_response.embeddings = [mock_embedding]
    
    mock_genai_client.models.embed_content.return_value = mock_response

    embedder = GoogleGenAIEmbedding(config)

    text = "Hello, world!"
    embedding = embedder.embed(text)

    assert embedding == [0.1, 0.2, 0.3, 0.4]
    
    # Verify the call was made with correct parameters for the new SDK
    expected_config = types.EmbedContentConfig(
        output_dimensionality=768
    )
    
    mock_genai_client.models.embed_content.assert_called_once_with(
        model="models/text-embedding-004",
        contents="Hello, world!",
        config=expected_config
    )
