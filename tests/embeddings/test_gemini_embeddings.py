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


def test_embed_batch_single_call(mock_genai, config):
    emb0 = type("Embedding", (), {"values": [0.1, 0.2, 0.3]})()
    emb1 = type("Embedding", (), {"values": [0.4, 0.5, 0.6]})()
    mock_genai.return_value = type("Response", (), {"embeddings": [emb0, emb1]})()

    embedder = GoogleGenAIEmbedding(config)

    texts = ["First text.", "Second text."]
    result = embedder.embed_batch(texts)

    mock_genai.assert_called_once_with(model="test_model", contents=texts, config=ANY)
    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


def test_embed_batch_empty_list(mock_genai, config):
    embedder = GoogleGenAIEmbedding(config)

    result = embedder.embed_batch([])

    assert result == []
    mock_genai.assert_not_called()


def test_embed_batch_count_mismatch_raises(mock_genai, config):
    emb0 = type("Embedding", (), {"values": [0.1, 0.2, 0.3]})()
    mock_genai.return_value = type("Response", (), {"embeddings": [emb0]})()

    embedder = GoogleGenAIEmbedding(config)

    with pytest.raises(ValueError, match="returned 1 embeddings for 2 texts"):
        embedder.embed_batch(["first text", "second text"])


def test_embed_batch_chunks_over_100_texts(mock_genai, config):
    def make_chunk_response(**kwargs):
        chunk = kwargs["contents"]
        emb = type("Embedding", (), {"values": [0.1, 0.2]})
        return type("Response", (), {"embeddings": [emb() for _ in chunk]})()

    mock_genai.side_effect = make_chunk_response

    embedder = GoogleGenAIEmbedding(config)
    texts = [f"text {i}" for i in range(150)]
    result = embedder.embed_batch(texts)

    assert mock_genai.call_count == 2
    assert len(result) == 150


def test_embed_batch_strips_newlines(mock_genai, config):
    emb0 = type("Embedding", (), {"values": [0.1, 0.2, 0.3]})()
    mock_genai.return_value = type("Response", (), {"embeddings": [emb0]})()

    embedder = GoogleGenAIEmbedding(config)
    embedder.embed_batch(["line one\nline two"])

    mock_genai.assert_called_once_with(model="test_model", contents=["line one line two"], config=ANY)


def _single_embedding_response():
    emb = type("Embedding", (), {"values": [0.1, 0.2, 0.3]})()
    return type("Response", (), {"embeddings": [emb]})()


def _task_type_of(mock_genai):
    return mock_genai.call_args.kwargs["config"].task_type


def test_embed_defaults_to_semantic_similarity(mock_genai, config):
    mock_genai.return_value = _single_embedding_response()

    GoogleGenAIEmbedding(config).embed("hello")

    assert _task_type_of(mock_genai) == "SEMANTIC_SIMILARITY"


def test_embed_search_uses_retrieval_query(mock_genai, config):
    mock_genai.return_value = _single_embedding_response()

    GoogleGenAIEmbedding(config).embed("hello", "search")

    assert _task_type_of(mock_genai) == "RETRIEVAL_QUERY"


@pytest.mark.parametrize("action", ["add", "update"])
def test_embed_add_and_update_use_retrieval_document(mock_genai, config, action):
    mock_genai.return_value = _single_embedding_response()

    GoogleGenAIEmbedding(config).embed("hello", action)

    assert _task_type_of(mock_genai) == "RETRIEVAL_DOCUMENT"


def test_embed_respects_config_task_type_override(mock_genai):
    cfg = BaseEmbedderConfig(
        api_key="dummy_api_key",
        model="test_model",
        embedding_dims=786,
        memory_search_embedding_type="CODE_RETRIEVAL_QUERY",
    )
    mock_genai.return_value = _single_embedding_response()

    GoogleGenAIEmbedding(cfg).embed("hello", "search")

    assert _task_type_of(mock_genai) == "CODE_RETRIEVAL_QUERY"


def test_embed_invalid_memory_action_raises(mock_genai, config):
    embedder = GoogleGenAIEmbedding(config)

    with pytest.raises(ValueError, match="Invalid memory action: bogus"):
        embedder.embed("hello", "bogus")


def test_embed_batch_defaults_to_retrieval_document(mock_genai, config):
    mock_genai.return_value = _single_embedding_response()

    GoogleGenAIEmbedding(config).embed_batch(["hello"])

    assert _task_type_of(mock_genai) == "RETRIEVAL_DOCUMENT"


def test_embed_batch_search_uses_retrieval_query(mock_genai, config):
    mock_genai.return_value = _single_embedding_response()

    GoogleGenAIEmbedding(config).embed_batch(["hello"], "search")

    assert _task_type_of(mock_genai) == "RETRIEVAL_QUERY"


def test_embed_batch_update_uses_retrieval_document(mock_genai, config):
    mock_genai.return_value = _single_embedding_response()

    GoogleGenAIEmbedding(config).embed_batch(["hello"], "update")

    assert _task_type_of(mock_genai) == "RETRIEVAL_DOCUMENT"


def test_embed_batch_invalid_memory_action_raises(mock_genai, config):
    embedder = GoogleGenAIEmbedding(config)

    with pytest.raises(ValueError, match="Invalid memory action: bogus"):
        embedder.embed_batch(["hello"], "bogus")
