from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.configs import EmbedderConfig

try:
    from mem0.embeddings import voyageai as voyageai_module
    from mem0.embeddings.voyageai import VoyageEmbedding
except ImportError:
    pytest.skip("voyageai not installed", allow_module_level=True)

DEFAULT_MODEL = "voyage-3.5"
DEFAULT_EMBEDDING_DIMS = 1024


@pytest.fixture
def mock_voyage_client():
    with patch("mem0.embeddings.voyageai.Client") as mock_client_cls:
        mock_client = Mock()
        mock_client_cls.return_value = mock_client
        # Cheap, deterministic token estimate so batching tests can override it.
        mock_client.count_tokens.return_value = 1
        yield mock_client


def test_default_config_applies_voyage_defaults(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig())

    assert embedder.config.model == DEFAULT_MODEL
    assert embedder.config.embedding_dims == DEFAULT_EMBEDDING_DIMS


def test_embed_single_text_documents(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model=DEFAULT_MODEL))
    mock_voyage_client.embed.return_value = Mock(embeddings=[[0.1, 0.2, 0.3]])

    embedding = embedder.embed("Sample text to embed.")

    assert embedding == [0.1, 0.2, 0.3]
    _, kwargs = mock_voyage_client.embed.call_args
    assert kwargs["model"] == DEFAULT_MODEL
    assert kwargs["input_type"] == "document"
    assert kwargs["output_dimension"] == DEFAULT_EMBEDDING_DIMS


def test_embed_search_uses_query_input_type(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model=DEFAULT_MODEL))
    mock_voyage_client.embed.return_value = Mock(embeddings=[[0.4, 0.5, 0.6]])

    embedder.embed("What did I say?", memory_action="search")

    _, kwargs = mock_voyage_client.embed.call_args
    assert kwargs["input_type"] == "query"


def test_embed_batch_single_call(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model=DEFAULT_MODEL))
    mock_voyage_client.embed.return_value = Mock(embeddings=[[0.1, 0.2], [0.3, 0.4]])

    embeddings = embedder.embed_batch(["first", "second"])

    assert embeddings == [[0.1, 0.2], [0.3, 0.4]]
    args, kwargs = mock_voyage_client.embed.call_args
    assert args[0] == ["first", "second"]


def test_embed_batch_empty_list(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model=DEFAULT_MODEL))

    assert embedder.embed_batch([]) == []
    mock_voyage_client.embed.assert_not_called()


def test_embed_batch_count_mismatch_raises(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model=DEFAULT_MODEL))
    mock_voyage_client.embed.return_value = Mock(embeddings=[[0.1, 0.2]])

    with pytest.raises(ValueError, match="returned 1 embeddings for 2 texts"):
        embedder.embed_batch(["first text", "second text"])


def test_fixed_dimension_model_omits_output_dimension(mock_voyage_client):
    # voyage-2 has a fixed dimension and rejects output_dimension.
    embedder = VoyageEmbedding(BaseEmbedderConfig(model="voyage-2"))
    mock_voyage_client.embed.return_value = Mock(embeddings=[[0.1]])

    embedder.embed("hello")

    _, kwargs = mock_voyage_client.embed.call_args
    assert "output_dimension" not in kwargs


# --- Contextualized (voyage-context-*) path -------------------------------------


def _ctx_response(vectors):
    """Build a fake contextualized response: one result per input, one chunk each."""
    results = [Mock(index=i, embeddings=[vec]) for i, vec in enumerate(vectors)]
    return Mock(results=results)


def test_contextualized_document_path_uses_auto_chunking(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model="voyage-context-4"))
    mock_voyage_client.contextualized_embed.return_value = _ctx_response([[0.1], [0.2]])

    embeddings = embedder.embed_batch(["doc one", "doc two"], memory_action="add")

    assert embeddings == [[0.1], [0.2]]
    _, kwargs = mock_voyage_client.contextualized_embed.call_args
    # Flat list[str] — each string is its own independent document, not one
    # document's chunk list.
    assert kwargs["inputs"] == ["doc one", "doc two"]
    assert kwargs["input_type"] == "document"
    assert kwargs["enable_auto_chunking"] is True
    assert kwargs["chunk_size"] == voyageai_module.CONTEXT_CHUNK_SIZE
    mock_voyage_client.embed.assert_not_called()


def test_contextualized_query_path_disables_auto_chunking(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model="voyage-context-4"))
    mock_voyage_client.contextualized_embed.return_value = _ctx_response([[0.9]])

    embedder.embed("a question", memory_action="search")

    _, kwargs = mock_voyage_client.contextualized_embed.call_args
    assert kwargs["input_type"] == "query"
    # Auto-chunking is invalid for queries and must not be sent.
    assert "enable_auto_chunking" not in kwargs
    assert "chunk_size" not in kwargs


def test_contextualized_result_order_preserved(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model="voyage-context-4"))
    # Return results out of order; the embedder must re-sort by index.
    results = [Mock(index=1, embeddings=[[0.2]]), Mock(index=0, embeddings=[[0.1]])]
    mock_voyage_client.contextualized_embed.return_value = Mock(results=results)

    embeddings = embedder.embed_batch(["first", "second"], memory_action="add")

    assert embeddings == [[0.1], [0.2]]


# --- Token-aware batching -------------------------------------------------------


def test_batching_splits_at_token_boundary(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model="voyage-3-large"))  # 120K limit
    # Each text is 80K tokens: two fit in no single 120K batch.
    embedder._num_tokens = Mock(return_value=80_000)
    mock_voyage_client.embed.side_effect = [
        Mock(embeddings=[[0.1]]),
        Mock(embeddings=[[0.2]]),
    ]

    embeddings = embedder.embed_batch(["a", "b"])

    assert embeddings == [[0.1], [0.2]]
    assert mock_voyage_client.embed.call_count == 2
    assert [c.args[0] for c in mock_voyage_client.embed.call_args_list] == [["a"], ["b"]]


def test_batching_single_oversized_text_goes_alone(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model="voyage-3-large"))  # 120K limit
    # One text exceeds the whole per-request budget; it must still be sent alone.
    embedder._num_tokens = Mock(side_effect=[500_000, 10])
    mock_voyage_client.embed.side_effect = [
        Mock(embeddings=[[0.1]]),
        Mock(embeddings=[[0.2]]),
    ]

    embeddings = embedder.embed_batch(["huge", "small"])

    assert embeddings == [[0.1], [0.2]]
    assert [c.args[0] for c in mock_voyage_client.embed.call_args_list] == [["huge"], ["small"]]


def test_batching_respects_item_count_cap(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model="voyage-3-large"))
    embedder._num_tokens = Mock(return_value=1)  # never hit the token limit
    texts = ["t"] * 5
    mock_voyage_client.embed.side_effect = [
        Mock(embeddings=[[0.1], [0.2]]),
        Mock(embeddings=[[0.3], [0.4]]),
        Mock(embeddings=[[0.5]]),
    ]

    with patch.object(voyageai_module, "MAX_BATCH_SIZE", 2):
        embeddings = embedder.embed_batch(texts)

    assert len(embeddings) == 5
    batch_sizes = [len(c.args[0]) for c in mock_voyage_client.embed.call_args_list]
    assert batch_sizes == [2, 2, 1]


def test_single_embed_skips_token_counting(mock_voyage_client):
    # The single-text hot path must not touch token-aware batching: count_tokens
    # loads a HuggingFace tokenizer on every call, so it must stay off `embed()`.
    embedder = VoyageEmbedding(BaseEmbedderConfig(model=DEFAULT_MODEL))
    mock_voyage_client.embed.return_value = Mock(embeddings=[[0.1, 0.2, 0.3]])

    embedder.embed("Sample text to embed.")

    mock_voyage_client.count_tokens.assert_not_called()
    mock_voyage_client.embed.assert_called_once()


def test_single_embed_contextualized_skips_token_counting(mock_voyage_client):
    embedder = VoyageEmbedding(BaseEmbedderConfig(model="voyage-context-4"))
    mock_voyage_client.contextualized_embed.return_value = _ctx_response([[0.1]])

    embedder.embed("Sample text to embed.")

    mock_voyage_client.count_tokens.assert_not_called()
    mock_voyage_client.contextualized_embed.assert_called_once()


# --- Config / factory integration path -----------------------------------------


def test_embedder_config_accepts_voyageai_provider():
    # The documented `Memory.from_config` path routes through EmbedderConfig, whose
    # validator rejects any provider missing from its allowlist. This guards against
    # the factory being registered while the config allowlist is not.
    config = EmbedderConfig(provider="voyageai", config={"model": "voyage-3.5", "embedding_dims": 1024})

    assert config.provider == "voyageai"


def test_factory_creates_voyage_embedder(mock_voyage_client):
    from mem0.utils.factory import EmbedderFactory

    embedder = EmbedderFactory.create("voyageai", {"model": "voyage-3.5"}, vector_config=None)

    assert isinstance(embedder, VoyageEmbedding)
