from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.together import TogetherEmbedding


@pytest.fixture
def mock_together_client():
    with patch("mem0.embeddings.together.Together") as mock_together:
        mock_client = Mock()
        mock_together.return_value = mock_client
        yield mock_client


@pytest.fixture
def embedder(mock_together_client):
    config = BaseEmbedderConfig(
        model="togethercomputer/m2-bert-80M-8k-retrieval",
        api_key="test-key",
        embedding_dims=768,
    )
    return TogetherEmbedding(config)


def _make_response(embeddings: list):
    """Build a mock Together embeddings response."""
    items = []
    for idx, emb in enumerate(embeddings):
        item = Mock()
        item.index = idx
        item.embedding = emb
        items.append(item)
    response = Mock()
    response.data = items
    return response


def test_embed(embedder, mock_together_client):
    mock_together_client.embeddings.create.return_value = _make_response([[0.1, 0.2, 0.3]])

    result = embedder.embed("hello world")

    mock_together_client.embeddings.create.assert_called_once_with(
        model="togethercomputer/m2-bert-80M-8k-retrieval", input="hello world"
    )
    assert result == [0.1, 0.2, 0.3]


def test_embed_batch(embedder, mock_together_client):
    mock_together_client.embeddings.create.return_value = _make_response([[0.1, 0.2], [0.3, 0.4]])

    texts = ["first text", "second text"]
    result = embedder.embed_batch(texts)

    mock_together_client.embeddings.create.assert_called_once_with(
        model="togethercomputer/m2-bert-80M-8k-retrieval", input=texts
    )
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_batch_single_api_call(embedder, mock_together_client):
    mock_together_client.embeddings.create.return_value = _make_response([[0.1] * 768] * 50)

    embedder.embed_batch([f"text {i}" for i in range(50)])

    assert mock_together_client.embeddings.create.call_count == 1


def test_embed_batch_chunks_at_100(embedder, mock_together_client):
    mock_together_client.embeddings.create.return_value = _make_response([[0.1] * 768] * 100)

    embedder.embed_batch([f"text {i}" for i in range(150)])

    assert mock_together_client.embeddings.create.call_count == 2


def test_embed_batch_preserves_order(embedder, mock_together_client):
    """Results should be sorted by index, not by API return order."""
    item0 = Mock()
    item0.index = 0
    item0.embedding = [0.1, 0.2]
    item1 = Mock()
    item1.index = 1
    item1.embedding = [0.3, 0.4]

    response = Mock()
    response.data = [item1, item0]  # intentionally reversed
    mock_together_client.embeddings.create.return_value = response

    result = embedder.embed_batch(["first", "second"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
