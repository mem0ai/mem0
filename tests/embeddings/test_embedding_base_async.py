import asyncio

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class EchoEmbedder(EmbeddingBase):
    def __init__(self):
        super().__init__(BaseEmbedderConfig(model="demo-model"))
        self.embed_calls = []
        self.batch_calls = []

    def embed(self, text, memory_action=None):
        self.embed_calls.append((text, memory_action))
        return {"text": text, "memory_action": memory_action}

    def embed_batch(self, texts, memory_action="add"):
        self.batch_calls.append((texts, memory_action))
        return [{"text": text, "memory_action": memory_action} for text in texts]


def test_aembed_and_aembed_batch_fall_back_to_sync_provider():
    embedder = EchoEmbedder()

    default_single = asyncio.run(embedder.aembed("default"))
    single = asyncio.run(embedder.aembed("hello", "search"))
    batch = asyncio.run(embedder.aembed_batch(["alpha", "beta"], "update"))

    assert default_single == {"text": "default", "memory_action": None}
    assert single == {"text": "hello", "memory_action": "search"}
    assert batch == [
        {"text": "alpha", "memory_action": "update"},
        {"text": "beta", "memory_action": "update"},
    ]
    assert embedder.embed_calls == [("default", None), ("hello", "search")]
    assert embedder.batch_calls == [(["alpha", "beta"], "update")]
