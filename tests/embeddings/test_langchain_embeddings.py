import pytest
from langchain.embeddings.base import Embeddings

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.langchain import LangchainEmbedding


class DummyEmbeddings(Embeddings):
    def __init__(self):
        self.queries = []

    def embed_documents(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]

    def embed_query(self, text):
        self.queries.append(text)
        return [0.1, 0.2, 0.3]


def test_missing_model_raises():
    with pytest.raises(ValueError, match="`model` parameter is required"):
        LangchainEmbedding(BaseEmbedderConfig())


def test_model_that_is_not_an_embeddings_instance_raises():
    with pytest.raises(ValueError, match="`model` must be an instance of Embeddings"):
        LangchainEmbedding(BaseEmbedderConfig(model="text-embedding-3-small"))


def test_embed_delegates_to_embed_query():
    model = DummyEmbeddings()
    embedder = LangchainEmbedding(BaseEmbedderConfig(model=model))

    assert embedder.embed("hello", "add") == [0.1, 0.2, 0.3]
    assert model.queries == ["hello"]


def test_embed_batch_falls_back_to_sequential_embed():
    model = DummyEmbeddings()
    embedder = LangchainEmbedding(BaseEmbedderConfig(model=model))

    assert embedder.embed_batch(["a", "b"]) == [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]]
    assert model.queries == ["a", "b"]
