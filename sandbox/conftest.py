import copy
import hashlib
import os
import socket
import uuid

import pytest

from mem0 import Memory
from mem0.configs.base import MemoryConfig
from mem0.embeddings.base import EmbeddingBase

EMBED_DIMS = 64

os.environ.setdefault("OPENAI_API_KEY", "sk-sandbox-unused")

STORE_CONFIGS = {
    "qdrant": {
        "provider": "qdrant",
        "config": {
            "embedding_model_dims": EMBED_DIMS,
            "host": "localhost",
            "port": 6333,
            "path": None,
        },
    },
    "pgvector": {
        "provider": "pgvector",
        "config": {
            "embedding_model_dims": EMBED_DIMS,
            "dbname": "mem0",
            "user": "mem0",
            "password": "mem0",
            "host": "localhost",
            "port": 5433,
        },
    },
}


class HashEmbedder(EmbeddingBase):
    """Deterministic token-hash embedding: no network, no API key, stable across runs."""

    def embed(self, text, memory_action=None):
        vector = [0.0] * EMBED_DIMS
        for token in str(text).lower().split():
            digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
            vector[int.from_bytes(digest, "big") % EMBED_DIMS] += 1.0
        norm = sum(value * value for value in vector) ** 0.5
        if norm == 0:
            return [1.0] + [0.0] * (EMBED_DIMS - 1)
        return [value / norm for value in vector]


def _reachable(host, port):
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


@pytest.fixture(params=list(STORE_CONFIGS))
def memory(request, tmp_path):
    store = copy.deepcopy(STORE_CONFIGS[request.param])
    host, port = store["config"]["host"], store["config"]["port"]
    if not _reachable(host, port):
        pytest.skip(f"{request.param} unreachable at {host}:{port} — start it with sandbox/docker-compose.yml")

    store["config"]["collection_name"] = f"sandbox_{uuid.uuid4().hex[:12]}"
    instance = Memory(MemoryConfig(vector_store=store, history_db_path=str(tmp_path / "history.db")))
    instance.embedding_model = HashEmbedder()
    yield instance
    instance.vector_store.delete_col()
    instance.close()
