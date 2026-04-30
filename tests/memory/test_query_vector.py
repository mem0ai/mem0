"""
Tests for the precomputed `query_vector` kwarg on Memory.search and AsyncMemory.search.

Covers:
1. Vector path bypasses the embedder
2. Vector-only (query=None) path skips BM25 / entity steps that require text
3. Validation: ValueError when neither query nor query_vector is provided
4. Both query and query_vector keep BM25 active while still skipping the embed

Each test has a sync (Memory) and async (AsyncMemory) mirror.

Mocking convention follows tests/memory/test_main.py — patch the factory
functions before instantiating Memory/AsyncMemory so no real network /
API key is required.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mem0.memory.main import AsyncMemory, Memory


def _setup_factory_mocks(mocker):
    """Match the convention in tests/memory/test_main.py."""
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store_instance = mocker.MagicMock()
    mock_vector_store_instance.search.return_value = []
    mock_vector_store_instance.keyword_search.return_value = None
    mock_vector_store = mocker.MagicMock(return_value=mock_vector_store_instance)
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vector_store_instance, mocker.MagicMock()],
    )

    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())
    return mock_embedder.return_value, mock_vector_store_instance


@pytest.fixture
def memory(mocker):
    embedder, vector_store = _setup_factory_mocks(mocker)
    m = Memory()
    m.embedding_model = embedder
    m.vector_store = vector_store
    return m


@pytest.fixture
def async_memory(mocker):
    embedder, vector_store = _setup_factory_mocks(mocker)
    m = AsyncMemory()
    m.embedding_model = embedder
    m.vector_store = vector_store
    return m


# ---------------------------------------------------------------------------
# 1. Vector bypasses embed
# ---------------------------------------------------------------------------

def test_search_with_query_vector_skips_embed(memory):
    """When query_vector is supplied, embedding_model.embed is NOT called."""
    query_vector = [0.1, 0.2, 0.3]
    memory.search(query_vector=query_vector, filters={"user_id": "u1"})

    memory.embedding_model.embed.assert_not_called()
    memory.vector_store.search.assert_called()
    _args, kwargs = memory.vector_store.search.call_args
    assert kwargs["vectors"] == query_vector


@pytest.mark.asyncio
async def test_async_search_with_query_vector_skips_embed(async_memory):
    """AsyncMemory mirror."""
    query_vector = [0.1, 0.2, 0.3]
    await async_memory.search(query_vector=query_vector, filters={"user_id": "u1"})

    async_memory.embedding_model.embed.assert_not_called()
    async_memory.vector_store.search.assert_called()
    _args, kwargs = async_memory.vector_store.search.call_args
    assert kwargs["vectors"] == query_vector


# ---------------------------------------------------------------------------
# 2. Vector-only (query=None) skips BM25 / entity (would crash on .lower(None))
# ---------------------------------------------------------------------------

def test_search_query_vector_only_skips_bm25_and_entity_extraction(memory, mocker):
    """
    When query is None, lemmatize_for_bm25 and extract_entities cannot run
    (they call .lower() on None). The implementation must skip those steps
    and not call vector_store.keyword_search either.
    """
    mock_lemma = mocker.patch("mem0.memory.main.lemmatize_for_bm25")
    mock_entities = mocker.patch("mem0.memory.main.extract_entities")

    memory.search(query_vector=[0.1, 0.2, 0.3], filters={"user_id": "u1"})

    mock_lemma.assert_not_called()
    mock_entities.assert_not_called()
    memory.vector_store.keyword_search.assert_not_called()


@pytest.mark.asyncio
async def test_async_search_query_vector_only_skips_bm25_and_entity_extraction(async_memory, mocker):
    """AsyncMemory mirror — async version uses asyncio.to_thread for these calls."""
    mock_lemma = mocker.patch("mem0.memory.main.lemmatize_for_bm25")
    mock_entities = mocker.patch("mem0.memory.main.extract_entities")

    await async_memory.search(query_vector=[0.1, 0.2, 0.3], filters={"user_id": "u1"})

    mock_lemma.assert_not_called()
    mock_entities.assert_not_called()
    async_memory.vector_store.keyword_search.assert_not_called()


# ---------------------------------------------------------------------------
# 3. Validation: ValueError when neither query nor query_vector is provided
# ---------------------------------------------------------------------------

def test_search_requires_query_or_query_vector(memory):
    """Calling search() with neither argument is a programmer error."""
    with pytest.raises(ValueError, match="query.*query_vector"):
        memory.search(filters={"user_id": "u1"})


@pytest.mark.asyncio
async def test_async_search_requires_query_or_query_vector(async_memory):
    """AsyncMemory mirror."""
    with pytest.raises(ValueError, match="query.*query_vector"):
        await async_memory.search(filters={"user_id": "u1"})


# ---------------------------------------------------------------------------
# 4. Both query AND query_vector — vector for ANN, query for BM25
# ---------------------------------------------------------------------------

def test_search_with_both_query_and_vector_keeps_bm25_active(memory):
    """
    Caller supplies both: vector for ANN (skip embed), query string for BM25.
    The optimization target — embed once, hybrid-search across many namespaces.
    """
    query_vector = [0.4, 0.5, 0.6]
    memory.vector_store.keyword_search.return_value = []  # opt into the call path

    memory.search(query="hello world", query_vector=query_vector, filters={"user_id": "u1"})

    memory.embedding_model.embed.assert_not_called()
    _args, kwargs = memory.vector_store.search.call_args
    assert kwargs["vectors"] == query_vector
    memory.vector_store.keyword_search.assert_called()


@pytest.mark.asyncio
async def test_async_search_with_both_query_and_vector_keeps_bm25_active(async_memory):
    """AsyncMemory mirror."""
    query_vector = [0.4, 0.5, 0.6]
    async_memory.vector_store.keyword_search.return_value = []

    await async_memory.search(query="hello world", query_vector=query_vector, filters={"user_id": "u1"})

    async_memory.embedding_model.embed.assert_not_called()
    _args, kwargs = async_memory.vector_store.search.call_args
    assert kwargs["vectors"] == query_vector
    async_memory.vector_store.keyword_search.assert_called()
