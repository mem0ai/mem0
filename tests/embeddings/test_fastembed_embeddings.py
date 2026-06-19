"""Tests for FastEmbed embedding provider, including embed_batch."""

import sys
from unittest.mock import Mock, MagicMock, patch

import pytest


# Create a comprehensive numpy mock to satisfy qdrant_client and other imports
def _setup_numpy_mock():
    """Install a fake numpy module tree so downstream packages (qdrant_client etc.) can import."""
    if "numpy" in sys.modules and hasattr(sys.modules["numpy"], "__file__"):
        # Check if real numpy is actually importable
        try:
            sys.modules["numpy"].bool_
            return  # Real numpy works fine
        except (AttributeError, ImportError):
            pass

    # Remove broken numpy entries
    for key in list(sys.modules.keys()):
        if key == "numpy" or key.startswith("numpy."):
            del sys.modules[key]

    # Use MagicMock so any attribute access auto-creates (np.bool_, np.ndarray, etc.)
    np = MagicMock()
    np.__version__ = "1.26.0"
    np.__path__ = ["<mock>"]
    np.__name__ = "numpy"
    np.__package__ = "numpy"
    np.__spec__ = None

    sys.modules["numpy"] = np

    # Create submodules that downstream packages import via `import numpy.X`
    submodules = [
        "numpy.core",
        "numpy._core",
        "numpy.typing",
        "numpy.linalg",
        "numpy.random",
        "numpy.lib",
        "numpy.lib.stride_tricks",
        "numpy.testing",
        "numpy.core.numeric",
        "numpy.core.multiarray",
        "numpy.distutils",
        "numpy.ma",
    ]
    for name in submodules:
        mock_mod = MagicMock()
        mock_mod.__name__ = name
        mock_mod.__package__ = name
        mock_mod.__path__ = ["<mock>"]
        mock_mod.__spec__ = None
        sys.modules[name] = mock_mod
        # Also set as attr on parent
        parts = name.split(".")
        parent = sys.modules[".".join(parts[:-1])]
        setattr(parent, parts[-1], mock_mod)


_setup_numpy_mock()

# Also mock fastembed itself (it depends on numpy/onnxruntime which may not load)
_mock_text_embedding = MagicMock()
sys.modules.setdefault("fastembed", MagicMock(TextEmbedding=_mock_text_embedding))

from mem0.configs.embeddings.base import BaseEmbedderConfig  # noqa: E402
from mem0.embeddings.fastembed import FastEmbedEmbedding  # noqa: E402


class FakeArray:
    """Mimics a numpy array with tolist() for testing without numpy dependency."""

    def __init__(self, values):
        self._values = list(values)

    def tolist(self):
        return self._values

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __getitem__(self, idx):
        return self._values[idx]


@pytest.fixture
def mock_fastembed_client():
    with patch("mem0.embeddings.fastembed.TextEmbedding") as mock_fastembed:
        mock_client = Mock()
        mock_fastembed.return_value = mock_client
        yield mock_client


def test_embed_with_jina_model(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_embedding = FakeArray([0.1, 0.2, 0.3, 0.4, 0.5])
    mock_fastembed_client.embed.return_value = iter([mock_embedding])

    text = "Sample text to embed."
    embedding = embedder.embed(text)

    mock_fastembed_client.embed.assert_called_once_with(text)
    assert list(embedding) == [0.1, 0.2, 0.3, 0.4, 0.5]


def test_embed_removes_newlines(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_embedding = FakeArray([0.7, 0.8, 0.9])
    mock_fastembed_client.embed.return_value = iter([mock_embedding])

    text_with_newlines = "Hello\nworld"
    embedding = embedder.embed(text_with_newlines)

    mock_fastembed_client.embed.assert_called_once_with("Hello world")
    assert list(embedding) == [0.7, 0.8, 0.9]


def test_embed_batch_uses_native_list_input(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_fastembed_client.embed.return_value = [
        FakeArray([0.1, 0.2, 0.3]),
        FakeArray([0.4, 0.5, 0.6]),
    ]
    result = embedder.embed_batch(["hello", "world"])
    mock_fastembed_client.embed.assert_called_once_with(["hello", "world"])
    assert len(result) == 2
    assert result[0] == [0.1, 0.2, 0.3]
    assert result[1] == [0.4, 0.5, 0.6]


def test_embed_batch_empty_returns_empty(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    result = embedder.embed_batch([])
    assert result == []


def test_embed_batch_replaces_newlines(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_fastembed_client.embed.return_value = [FakeArray([0.1, 0.2])]
    embedder.embed_batch(["hello\nworld"])
    mock_fastembed_client.embed.assert_called_once_with(["hello world"])


def test_embed_batch_falls_back_on_error(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    # First call (from embed_batch) raises, subsequent calls (from fallback embed()) succeed
    mock_fastembed_client.embed.side_effect = [
        RuntimeError("fail"),
        iter([FakeArray([0.1, 0.2])]),
        iter([FakeArray([0.3, 0.4])]),
    ]
    result = embedder.embed_batch(["a", "b"])
    assert len(result) == 2


def test_embed_batch_falls_back_on_count_mismatch(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    # Return 1 embedding for 2 texts -> count mismatch -> fallback
    mock_fastembed_client.embed.side_effect = [
        [FakeArray([0.1, 0.2])],  # batch call returns wrong count
        iter([FakeArray([0.1, 0.2])]),  # fallback embed("a")
        iter([FakeArray([0.3, 0.4])]),  # fallback embed("b")
    ]
    result = embedder.embed_batch(["a", "b"])
    assert len(result) == 2
