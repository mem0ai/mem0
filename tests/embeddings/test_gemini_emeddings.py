from unittest.mock import ANY, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.gemini import GoogleGenAIEmbedding


@pytest.fixture
def mock_genai():
    with patch("mem0.embeddings.gemini.genai.Client") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.models.embed_content.return_value = None
        yield mock_client.models.embed_content


@pytest.fixture
def config():
    return BaseEmbedderConfig(api_key="dummy_api_key", model="test_model", embedding_dims=786)


def test_embed_query(mock_genai, config):
    mock_embedding_response = type(
        "Response", (), {"embeddings": [type("Embedding", (), {"values": [0.1, 0.2, 0.3, 0.4]})]}
    )()
    mock_genai.return_value = mock_embedding_response

    embedder = GoogleGenAIEmbedding(config)

    text = "Hello, world!"
    embedding = embedder.embed(text)

    assert embedding == [0.1, 0.2, 0.3, 0.4]
    mock_genai.assert_called_once_with(model="test_model", contents="Hello, world!", config=ANY)


def test_embed_returns_empty_list_if_none(mock_genai, config):
    mock_genai.return_value = type("Response", (), {"embeddings": [type("Embedding", (), {"values": []})]})()

    embedder = GoogleGenAIEmbedding(config)

    result = embedder.embed("test")
    assert result == []


def test_embed_raises_on_error(mock_genai, config):
    mock_genai.side_effect = RuntimeError("Embedding failed")

    embedder = GoogleGenAIEmbedding(config)

    with pytest.raises(RuntimeError, match="Embedding failed"):
        embedder.embed("some input")


def test_config_initialization(config):
    embedder = GoogleGenAIEmbedding(config)

    assert embedder.config.api_key == "dummy_api_key"
    assert embedder.config.model == "test_model"
    assert embedder.config.embedding_dims == 786


def test_embed_batch(mock_genai, config):
    def make_embedding(values):
        return type("Embedding", (), {"values": values})()

    mock_genai.return_value = type(
        "Response", (), {"embeddings": [make_embedding([0.1, 0.2]), make_embedding([0.3, 0.4])]}
    )()

    embedder = GoogleGenAIEmbedding(config)
    result = embedder.embed_batch(["hello world", "foo bar"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    mock_genai.assert_called_once_with(model="test_model", contents=["hello world", "foo bar"], config=ANY)


def test_embed_batch_chunks_at_100(mock_genai, config):
    def make_embedding(values):
        return type("Embedding", (), {"values": values})()

    mock_genai.return_value = type(
        "Response", (), {"embeddings": [make_embedding([0.1]) for _ in range(100)]}
    )()

    embedder = GoogleGenAIEmbedding(config)
    embedder.embed_batch([f"text {i}" for i in range(150)])

    assert mock_genai.call_count == 2


def test_embed_batch_strips_newlines(mock_genai, config):
    def make_embedding(values):
        return type("Embedding", (), {"values": values})()

    mock_genai.return_value = type(
        "Response", (), {"embeddings": [make_embedding([0.1, 0.2])]}
    )()

    embedder = GoogleGenAIEmbedding(config)
    embedder.embed_batch(["hello\nworld"])

    call_contents = mock_genai.call_args.kwargs["contents"]
    assert call_contents == ["hello world"]
