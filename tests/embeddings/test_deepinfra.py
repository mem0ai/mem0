
from unittest.mock import patch, MagicMock
import pytest
from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.deepinfra import DeepInfraEmbedding  # Update import as needed


@pytest.fixture
def mock_openai():
    with patch("mem0.embeddings.deepinfra.OpenAI") as mock_openai_client:
        yield mock_openai_client

@pytest.fixture
def config():
    return BaseEmbedderConfig(
        api_key="dummy_api_key",
        model="BAAI/bge-large-en-v1.5",
        embedding_dims=1024,
        encoding_format="float"
    )


def test_embed_query(mock_openai, config):

    mock_embedding_response = MagicMock()
    mock_embedding_response.data[0].embedding = [0.1, 0.2, 0.3, 0.4]
    mock_openai.return_value.embeddings.create.return_value = mock_embedding_response

    embedder = DeepInfraEmbedding(config)

    text = "Hello, world!"
    embedding = embedder.embed(text)

    assert embedding == [0.1, 0.2, 0.3, 0.4]
    mock_openai.return_value.embeddings.create.assert_called_once_with(
        input=["Hello, world!"],
        model="BAAI/bge-large-en-v1.5",
        encoding_format="float"
    )
