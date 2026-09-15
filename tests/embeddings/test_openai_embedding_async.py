import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.openai import OpenAIEmbedding


def _make_embedding_response(start, count):
    response = Mock()
    response.data = [Mock(index=index, embedding=[start + index]) for index in range(count)]
    return response


@pytest.fixture
def openai_clients(monkeypatch):
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    with (
        patch("mem0.embeddings.openai.OpenAI") as mock_sync_ctor,
        patch("mem0.embeddings.openai.AsyncOpenAI") as mock_async_ctor,
    ):
        sync_client = Mock()
        async_client = Mock()
        sync_client.embeddings = Mock(create=Mock())
        async_client.embeddings = Mock(create=Mock())
        mock_sync_ctor.return_value = sync_client
        mock_async_ctor.return_value = async_client
        yield sync_client, async_client, mock_sync_ctor, mock_async_ctor


def test_openai_embedding_clients_share_constructor_args(openai_clients):
    sync_client, async_client, sync_ctor, async_ctor = openai_clients

    embedder = OpenAIEmbedding(
        BaseEmbedderConfig(
            model="text-embedding-3-small", api_key="config-key", openai_base_url="https://api.example/v1"
        )
    )

    assert sync_ctor.call_args.kwargs == {"api_key": "config-key", "base_url": "https://api.example/v1"}
    assert async_ctor.call_args.kwargs == {"api_key": "config-key", "base_url": "https://api.example/v1"}
    assert embedder.client is sync_client
    assert embedder.async_client is async_client


def test_openai_embedding_async_embed_matches_sync_and_normalizes_text(openai_clients):
    sync_client, async_client, _, _ = openai_clients
    embedder = OpenAIEmbedding(
        BaseEmbedderConfig(model="text-embedding-3-small", api_key="config-key", embedding_dims=256)
    )
    sync_response = Mock(data=[Mock(embedding=[1.0, 2.0])])
    async_response = Mock(data=[Mock(embedding=[1.0, 2.0])])
    sync_client.embeddings.create = Mock(return_value=sync_response)
    async_client.embeddings.create = AsyncMock(return_value=async_response)

    sync_result = embedder.embed("hello\nworld")
    async_result = asyncio.run(embedder.aembed("hello\nworld"))

    expected = {
        "input": ["hello world"],
        "model": "text-embedding-3-small",
        "encoding_format": "float",
        "dimensions": 256,
    }
    assert sync_client.embeddings.create.call_args.kwargs == expected
    assert async_client.embeddings.create.call_args.kwargs == expected
    assert sync_result == async_result == [1.0, 2.0]


def test_openai_embedding_async_batch_matches_sync_and_chunks(openai_clients):
    sync_client, async_client, _, _ = openai_clients
    embedder = OpenAIEmbedding(
        BaseEmbedderConfig(model="text-embedding-3-small", api_key="config-key", embedding_dims=256)
    )
    texts = [f"text {index}\nline" for index in range(101)]
    sync_client.embeddings.create = Mock(
        side_effect=[
            _make_embedding_response(0, 100),
            _make_embedding_response(100, 1),
        ]
    )
    async_client.embeddings.create = AsyncMock(
        side_effect=[
            _make_embedding_response(0, 100),
            _make_embedding_response(100, 1),
        ]
    )

    sync_result = embedder.embed_batch(texts)
    async_result = asyncio.run(embedder.aembed_batch(texts))

    expected_first_call = {
        "input": [f"text {index} line" for index in range(100)],
        "model": "text-embedding-3-small",
        "encoding_format": "float",
        "dimensions": 256,
    }
    expected_second_call = {
        "input": ["text 100 line"],
        "model": "text-embedding-3-small",
        "encoding_format": "float",
        "dimensions": 256,
    }
    assert sync_client.embeddings.create.call_args_list[0].kwargs == expected_first_call
    assert async_client.embeddings.create.call_args_list[0].kwargs == expected_first_call
    assert sync_client.embeddings.create.call_args_list[1].kwargs == expected_second_call
    assert async_client.embeddings.create.call_args_list[1].kwargs == expected_second_call
    assert sync_result == async_result == [[index] for index in range(101)]


def test_openai_embedding_async_batch_count_mismatch_raises(openai_clients):
    _, async_client, _, _ = openai_clients
    embedder = OpenAIEmbedding(BaseEmbedderConfig(model="text-embedding-3-small", api_key="config-key"))
    async_client.embeddings.create = AsyncMock(return_value=_make_embedding_response(0, 1))

    with pytest.raises(ValueError, match="returned 1 embeddings for 2 texts"):
        asyncio.run(embedder.aembed_batch(["first text", "second text"]))
