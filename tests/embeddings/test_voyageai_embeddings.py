import sys
from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig


@pytest.fixture
def mock_voyageai_client():
    """Mock the voyageai module before VoyageAIEmbedding imports it."""
    mock_voyageai = Mock()
    mock_client = Mock()
    mock_voyageai.Client.return_value = mock_client

    with patch.dict(sys.modules, {"voyageai": mock_voyageai}):
        # Import here so it picks up the mocked module
        from mem0.embeddings.voyageai import VoyageAIEmbedding

        yield mock_client, VoyageAIEmbedding


# === Text Embedding Tests ===


def test_embed_default_model(mock_voyageai_client):
    """Test embedding with default model configuration."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.embed.return_value = mock_response

    result = embedder.embed("Hello world")

    mock_client.embed.assert_called_once_with(
        texts=["Hello world"],
        model="voyage-3.5",
        truncation=True,
        output_dimension=1024,
    )
    assert result == [0.1, 0.2, 0.3]


def test_embed_custom_model(mock_voyageai_client):
    """Test embedding with custom model and dimensions."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(
        api_key="test_key",
        model="voyage-3-large",
        embedding_dims=2048,
    )
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.4, 0.5, 0.6]]
    mock_client.embed.return_value = mock_response

    result = embedder.embed("Test embedding")

    mock_client.embed.assert_called_once_with(
        texts=["Test embedding"],
        model="voyage-3-large",
        truncation=True,
        output_dimension=2048,
    )
    assert result == [0.4, 0.5, 0.6]


def test_embed_custom_dimensions(mock_voyageai_client):
    """Test embedding with various supported dimensions."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    for dims in [256, 512, 1024, 2048]:
        config = BaseEmbedderConfig(
            api_key="test_key",
            model="voyage-3-large",
            embedding_dims=dims,
        )
        embedder = VoyageAIEmbedding(config)

        mock_response = Mock()
        mock_response.embeddings = [[0.1] * dims]
        mock_client.embed.return_value = mock_response

        result = embedder.embed("Test")

        call_kwargs = mock_client.embed.call_args[1]
        assert call_kwargs["output_dimension"] == dims


def test_embed_with_memory_action_add(mock_voyageai_client):
    """Test embedding with 'add' memory action maps to 'document' input_type."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.embed.return_value = mock_response

    embedder.embed("Document text", memory_action="add")

    call_kwargs = mock_client.embed.call_args[1]
    assert call_kwargs["input_type"] == "document"


def test_embed_with_memory_action_search(mock_voyageai_client):
    """Test embedding with 'search' memory action maps to 'query' input_type."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.embed.return_value = mock_response

    embedder.embed("Search query", memory_action="search")

    call_kwargs = mock_client.embed.call_args[1]
    assert call_kwargs["input_type"] == "query"


def test_embed_with_memory_action_update(mock_voyageai_client):
    """Test embedding with 'update' memory action maps to 'document' input_type."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.embed.return_value = mock_response

    embedder.embed("Updated text", memory_action="update")

    call_kwargs = mock_client.embed.call_args[1]
    assert call_kwargs["input_type"] == "document"


def test_embed_custom_embedding_type_mapping(mock_voyageai_client):
    """Test custom memory_*_embedding_type configuration."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(
        api_key="test_key",
        memory_add_embedding_type="query",  # Override default
        memory_search_embedding_type="document",  # Override default
    )
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.embed.return_value = mock_response

    # Test overridden add behavior
    embedder.embed("Text", memory_action="add")
    call_kwargs = mock_client.embed.call_args[1]
    assert call_kwargs["input_type"] == "query"

    # Test overridden search behavior
    embedder.embed("Text", memory_action="search")
    call_kwargs = mock_client.embed.call_args[1]
    assert call_kwargs["input_type"] == "document"


def test_embed_removes_newlines(mock_voyageai_client):
    """Test that newlines are replaced with spaces."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.7, 0.8, 0.9]]
    mock_client.embed.return_value = mock_response

    embedder.embed("Hello\nworld")

    call_kwargs = mock_client.embed.call_args[1]
    assert call_kwargs["texts"] == ["Hello world"]


def test_embed_truncation_enabled(mock_voyageai_client):
    """Test that truncation is enabled by default."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.embed.return_value = mock_response

    embedder.embed("Text")

    call_kwargs = mock_client.embed.call_args[1]
    assert call_kwargs["truncation"] is True


def test_embed_truncation_disabled(mock_voyageai_client):
    """Test that truncation can be disabled."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(
        api_key="test_key",
        voyageai_truncation=False,
    )
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.embed.return_value = mock_response

    embedder.embed("Text")

    call_kwargs = mock_client.embed.call_args[1]
    assert call_kwargs["truncation"] is False


def test_embed_output_dtype(mock_voyageai_client):
    """Test output dtype options."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    for dtype in ["float", "int8", "uint8", "binary", "ubinary"]:
        config = BaseEmbedderConfig(
            api_key="test_key",
            voyageai_output_dtype=dtype,
        )
        embedder = VoyageAIEmbedding(config)

        mock_response = Mock()
        mock_response.embeddings = [[0.1, 0.2, 0.3]]
        mock_client.embed.return_value = mock_response

        embedder.embed("Text")

        call_kwargs = mock_client.embed.call_args[1]
        assert call_kwargs["output_dtype"] == dtype


def test_embed_uses_environment_api_key(mock_voyageai_client, monkeypatch):
    """Test API key is read from environment variable."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    monkeypatch.setenv("VOYAGE_API_KEY", "env_key")
    config = BaseEmbedderConfig()

    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[1.0, 1.1, 1.2]]
    mock_client.embed.return_value = mock_response

    result = embedder.embed("Environment key test")
    assert result == [1.0, 1.1, 1.2]


def test_missing_api_key_raises_error(mock_voyageai_client, monkeypatch):
    """Test that missing API key raises ValueError."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    config = BaseEmbedderConfig()

    with pytest.raises(ValueError, match="VoyageAI API key is required"):
        VoyageAIEmbedding(config)


# === Multimodal Embedding Tests ===


def test_embed_multimodal_default_model(mock_voyageai_client):
    """Test multimodal embedding with default model."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.multimodal_embed.return_value = mock_response

    # Simulate text + image input
    inputs = ["This is a product", Mock()]  # Mock for PIL Image
    result = embedder.embed_multimodal(inputs)

    mock_client.multimodal_embed.assert_called_once()
    call_kwargs = mock_client.multimodal_embed.call_args[1]
    assert call_kwargs["model"] == "voyage-multimodal-3.5"
    assert result == [0.1, 0.2, 0.3]


def test_embed_multimodal_custom_model(mock_voyageai_client):
    """Test multimodal embedding with custom model."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(
        api_key="test_key",
        voyageai_multimodal_model="voyage-multimodal-3.5.5",
    )
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.4, 0.5, 0.6]]
    mock_client.multimodal_embed.return_value = mock_response

    inputs = ["Text with image", Mock()]
    result = embedder.embed_multimodal(inputs)

    call_kwargs = mock_client.multimodal_embed.call_args[1]
    assert call_kwargs["model"] == "voyage-multimodal-3.5.5"
    assert result == [0.4, 0.5, 0.6]


def test_embed_multimodal_with_memory_action(mock_voyageai_client):
    """Test multimodal embedding with memory action."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_client.multimodal_embed.return_value = mock_response

    inputs = ["Product description", Mock()]
    embedder.embed_multimodal(inputs, memory_action="add")

    call_kwargs = mock_client.multimodal_embed.call_args[1]
    assert call_kwargs["input_type"] == "document"


# === Contextualized Chunk Embedding Tests ===


def test_embed_contextualized_default_model(mock_voyageai_client):
    """Test contextualized embedding with default model."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    # Mock response with results structure
    mock_result1 = Mock()
    mock_result1.embeddings = [[0.1, 0.2], [0.3, 0.4]]
    mock_result2 = Mock()
    mock_result2.embeddings = [[0.5, 0.6]]
    mock_response = Mock()
    mock_response.results = [mock_result1, mock_result2]
    mock_client.contextualized_embed.return_value = mock_response

    chunks = [
        ["Introduction", "Background"],
        ["Conclusion"],
    ]
    result = embedder.embed_contextualized(chunks)

    mock_client.contextualized_embed.assert_called_once()
    call_kwargs = mock_client.contextualized_embed.call_args[1]
    assert call_kwargs["model"] == "voyage-context-3"
    # Should flatten embeddings from all documents
    assert result == [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]


def test_embed_contextualized_custom_model(mock_voyageai_client):
    """Test contextualized embedding with custom model."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(
        api_key="test_key",
        voyageai_context_model="voyage-context-3",
    )
    embedder = VoyageAIEmbedding(config)

    mock_result = Mock()
    mock_result.embeddings = [[0.1, 0.2]]
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.contextualized_embed.return_value = mock_response

    chunks = [["Single chunk"]]
    embedder.embed_contextualized(chunks)

    call_kwargs = mock_client.contextualized_embed.call_args[1]
    assert call_kwargs["model"] == "voyage-context-3"


def test_embed_contextualized_with_dimensions(mock_voyageai_client):
    """Test contextualized embedding with custom dimensions."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(
        api_key="test_key",
        embedding_dims=512,
    )
    embedder = VoyageAIEmbedding(config)

    mock_result = Mock()
    mock_result.embeddings = [[0.1] * 512]
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.contextualized_embed.return_value = mock_response

    chunks = [["Chunk"]]
    embedder.embed_contextualized(chunks)

    call_kwargs = mock_client.contextualized_embed.call_args[1]
    assert call_kwargs["output_dimension"] == 512


def test_embed_contextualized_with_memory_action(mock_voyageai_client):
    """Test contextualized embedding with memory action."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    mock_result = Mock()
    mock_result.embeddings = [[0.1, 0.2]]
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.contextualized_embed.return_value = mock_response

    chunks = [["Document chunk"]]
    embedder.embed_contextualized(chunks, memory_action="add")

    call_kwargs = mock_client.contextualized_embed.call_args[1]
    assert call_kwargs["input_type"] == "document"


def test_embed_contextualized_with_output_dtype(mock_voyageai_client):
    """Test contextualized embedding with output dtype."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(
        api_key="test_key",
        voyageai_output_dtype="int8",
    )
    embedder = VoyageAIEmbedding(config)

    mock_result = Mock()
    mock_result.embeddings = [[1, 2, 3]]
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.contextualized_embed.return_value = mock_response

    chunks = [["Chunk"]]
    embedder.embed_contextualized(chunks)

    call_kwargs = mock_client.contextualized_embed.call_args[1]
    assert call_kwargs["output_dtype"] == "int8"


# === Batch Embedding Tests ===


def test_embed_batch_single_batch(mock_voyageai_client):
    """Test batch embedding with texts that fit in a single batch."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    # Mock tokenize to return small token counts
    mock_client.tokenize.return_value = [[1, 2, 3]]  # 3 tokens per text

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]
    mock_client.embed.return_value = mock_response

    texts = ["Text 1", "Text 2", "Text 3"]
    result = embedder.embed_batch(texts, memory_action="add")

    # Should make only one embed call with all texts
    assert mock_client.embed.call_count == 1
    call_kwargs = mock_client.embed.call_args[1]
    assert call_kwargs["texts"] == ["Text 1", "Text 2", "Text 3"]
    assert call_kwargs["input_type"] == "document"
    assert len(result) == 3


def test_embed_batch_multiple_batches_by_tokens(mock_voyageai_client):
    """Test batch embedding splits based on token limits."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key", model="voyage-context-3")  # 32k token limit
    embedder = VoyageAIEmbedding(config)

    # Mock tokenize to return 20k tokens per text (exceeds 32k limit after 2 texts)
    mock_client.tokenize.return_value = [[1] * 20000]

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2]]
    mock_client.embed.return_value = mock_response

    texts = ["Text 1", "Text 2", "Text 3"]
    result = embedder.embed_batch(texts)

    # Should split into multiple batches due to token limits
    assert mock_client.embed.call_count >= 2
    assert len(result) == 3


def test_embed_batch_respects_batch_size(mock_voyageai_client):
    """Test batch embedding respects configured batch size."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key", voyageai_batch_size=2)
    embedder = VoyageAIEmbedding(config)

    # Mock tokenize to return small token counts
    mock_client.tokenize.return_value = [[1, 2, 3]]

    # Return different number of embeddings based on batch size
    def mock_embed(**kwargs):
        response = Mock()
        response.embeddings = [[0.1, 0.2]] * len(kwargs["texts"])
        return response

    mock_client.embed.side_effect = mock_embed

    texts = ["Text 1", "Text 2", "Text 3", "Text 4", "Text 5"]
    result = embedder.embed_batch(texts)

    # Should split into 3 batches (2, 2, 1)
    assert mock_client.embed.call_count == 3
    assert len(result) == 5


def test_embed_batch_empty_list(mock_voyageai_client):
    """Test batch embedding with empty list returns empty list."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    result = embedder.embed_batch([])

    assert result == []
    assert mock_client.embed.call_count == 0


def test_embed_batch_removes_newlines(mock_voyageai_client):
    """Test batch embedding removes newlines from texts."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)

    mock_client.tokenize.return_value = [[1, 2, 3]]

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2]]
    mock_client.embed.return_value = mock_response

    texts = ["Hello\nworld", "Test\ntext"]
    embedder.embed_batch(texts)

    call_kwargs = mock_client.embed.call_args[1]
    assert call_kwargs["texts"] == ["Hello world", "Test text"]


def test_embed_batch_with_all_params(mock_voyageai_client):
    """Test batch embedding passes all VoyageAI parameters."""
    mock_client, VoyageAIEmbedding = mock_voyageai_client
    config = BaseEmbedderConfig(
        api_key="test_key",
        model="voyage-3-large",
        embedding_dims=512,
        voyageai_output_dtype="int8",
        voyageai_truncation=False,
    )
    embedder = VoyageAIEmbedding(config)

    mock_client.tokenize.return_value = [[1, 2, 3]]

    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2]]
    mock_client.embed.return_value = mock_response

    embedder.embed_batch(["Text"], memory_action="search")

    call_kwargs = mock_client.embed.call_args[1]
    assert call_kwargs["model"] == "voyage-3-large"
    assert call_kwargs["output_dimension"] == 512
    assert call_kwargs["output_dtype"] == "int8"
    assert call_kwargs["truncation"] is False
    assert call_kwargs["input_type"] == "query"
