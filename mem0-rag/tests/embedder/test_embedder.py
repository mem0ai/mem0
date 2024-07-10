import pytest
from chromadb.api.types import Documents, Embeddings

from embedchain.config.embedder.base import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder


@pytest.fixture
def base_embedder():
    return BaseEmbedder()


def test_initialization(base_embedder):
    assert isinstance(base_embedder.config, BaseEmbedderConfig)
    # not initialized
    assert not hasattr(base_embedder, "embedding_fn")
    assert not hasattr(base_embedder, "vector_dimension")


def test_set_embedding_fn(base_embedder):
    def embedding_function(texts: Documents) -> Embeddings:
        return [f"Embedding for {text}" for text in texts]

    base_embedder.set_embedding_fn(embedding_function)
    assert hasattr(base_embedder, "embedding_fn")
    assert callable(base_embedder.embedding_fn)
    embeddings = base_embedder.embedding_fn(["text1", "text2"])
    assert embeddings == ["Embedding for text1", "Embedding for text2"]


def test_set_embedding_fn_when_not_a_function(base_embedder):
    with pytest.raises(ValueError):
        base_embedder.set_embedding_fn(None)


def test_set_vector_dimension(base_embedder):
    base_embedder.set_vector_dimension(256)
    assert hasattr(base_embedder, "vector_dimension")
    assert base_embedder.vector_dimension == 256


def test_set_vector_dimension_type_error(base_embedder):
    with pytest.raises(TypeError):
        base_embedder.set_vector_dimension(None)


def test_embedder_with_config():
    embedder = BaseEmbedder(BaseEmbedderConfig())
    assert isinstance(embedder.config, BaseEmbedderConfig)
