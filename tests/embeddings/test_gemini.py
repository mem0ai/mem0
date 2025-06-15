from unittest.mock import patch, MagicMock # Import MagicMock

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.gemini import GoogleGenAIEmbedding


@pytest.fixture
def mock_gemini_embedding_client():
    # Patch genai.Client within the mem0.embeddings.gemini module
    with patch("mem0.embeddings.gemini.genai.Client") as mock_genai_client_constructor:
        mock_client_instance = MagicMock()
        # Configure the nested structure: client.models.embed_content
        mock_client_instance.models = MagicMock()
        mock_client_instance.models.embed_content = MagicMock()

        mock_genai_client_constructor.return_value = mock_client_instance
        yield mock_client_instance


@pytest.fixture
def config():
    # Using embedding_dims as per existing test, GoogleGenAIEmbedding will convert to output_dimensionality
    return BaseEmbedderConfig(api_key="dummy_api_key", model="test_model", embedding_dims=768)


def test_embed_text(mock_gemini_embedding_client: MagicMock, config: BaseEmbedderConfig): # Renamed test and updated type hint
    mock_embedding_response = {"embedding": [0.1, 0.2, 0.3, 0.4]}
    # Set the return value for the mock embed_content method
    mock_gemini_embedding_client.models.embed_content.return_value = mock_embedding_response

    embedder = GoogleGenAIEmbedding(config)

    text = "Hello, world!"
    embedding = embedder.embed(text)

    assert embedding == [0.1, 0.2, 0.3, 0.4]
    # Assert that the mock embed_content method was called with the correct parameters
    mock_gemini_embedding_client.models.embed_content.assert_called_once_with(
        model="test_model",
        content="Hello, world!",
        output_dimensionality=768 # This comes from config.embedding_dims
    )
