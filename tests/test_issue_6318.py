import importlib.metadata
import sys
import types
from unittest.mock import patch

import numpy as np
import pytest

sys.modules.setdefault("posthog", types.SimpleNamespace(Posthog=lambda *args, **kwargs: None))
sys.modules.setdefault("qdrant_client", types.SimpleNamespace(QdrantClient=type("QdrantClient", (), {})))

with patch.object(importlib.metadata, "version", return_value="0.0.0"):
    from mem0 import Memory


class FakeEmbeddingModel:
    def embed(self, query, mode):
        assert query == "hello"
        assert mode == "search"
        return np.ones(1024)


class FakeVectorStore:
    def __init__(self):
        self.vectors = np.empty((0, 1536))

    def search(self, query, vectors, top_k=5, filters=None):
        assert query == "hello"
        assert top_k == 60
        assert filters == {"user_id": "default_user"}
        return self.vectors.dot(vectors)


def test_issue_6318():
    memory = Memory.__new__(Memory)
    memory.embedding_model = FakeEmbeddingModel()
    memory.vector_store = FakeVectorStore()

    with pytest.raises(ValueError, match=r"shapes \(0,1536\) and \(1024,\) not aligned"):
        memory._search_vector_store("hello", {"user_id": "default_user"}, limit=3)
