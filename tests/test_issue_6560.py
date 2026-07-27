"""Regression test for UpstashVector.list respecting its requested limit."""

import importlib
import importlib.metadata
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock


def test_issue_6560(monkeypatch):
    """list() must not return more records than the requested top_k."""
    mem0_was_loaded = "mem0" in sys.modules
    with monkeypatch.context() as patch:
        upstash_vector = ModuleType("upstash_vector")
        upstash_vector.Index = MagicMock()
        patch.setitem(sys.modules, "upstash_vector", upstash_vector)
        patch.setattr(importlib.metadata, "version", lambda _: "0.0.0")

        client_main = ModuleType("mem0.client.main")
        client_main.AsyncMemoryClient = MagicMock
        client_main.MemoryClient = MagicMock
        memory_main = ModuleType("mem0.memory.main")
        memory_main.AsyncMemory = MagicMock
        memory_main.Memory = MagicMock
        patch.setitem(sys.modules, "mem0.client.main", client_main)
        patch.setitem(sys.modules, "mem0.memory.main", memory_main)

        module = importlib.import_module("mem0.vector_stores.upstash_vector")
        client = MagicMock()
        client.info.return_value = SimpleNamespace(
            dimension=3,
            namespaces={"memories": SimpleNamespace(vector_count=100)},
        )
        client.resumable_query.return_value = (
            [
                SimpleNamespace(id=str(index), score=1.0, metadata={"index": index})
                for index in range(100)
            ],
            MagicMock(),
        )
        vector_store = module.UpstashVector(client=client, collection_name="memories")

        [results] = vector_store.list(top_k=5)

        if not mem0_was_loaded:
            for module_name in (
                "mem0.vector_stores.upstash_vector",
                "mem0.vector_stores.base",
                "mem0.vector_stores",
                "mem0.client",
                "mem0.memory",
                "mem0",
            ):
                sys.modules.pop(module_name, None)

    assert len(results) == 5
