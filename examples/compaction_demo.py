"""
Simple demo of mem0 memory compaction.

Shows how similar memories can be merged into higher quality ones.

Run with:
    PYTHONPATH=mem0 python mem0/examples/compaction_demo.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mem0"))

from mem0 import Memory
from mem0.configs.base import MemoryConfig, CompactionConfig


def build_mock_memory():
    """Create a mocked Memory for demonstration purposes."""
    cfg = MemoryConfig(
        compaction=CompactionConfig(enabled=True, similarity_threshold=0.75)
    )

    mem = Memory.__new__(Memory)
    mem.config = cfg

    # Mock embedder - returns simple deterministic vectors based on text hash-ish
    def fake_embed(text, action=None):
        # Extreme separation for reliable demo clustering
        t = text.lower()
        if any(k in t for k in ["pizza", "italian", "margherita", "crust"]):
            return [1.0, 0.99, 0.98, 1.0, 0.99, 0.97, 1.0, 0.98]
        if any(k in t for k in ["coffee", "morning", "wake"]):
            return [0.0, 0.01, 0.02, 0.0, 0.01, 0.0, 0.02, 0.01]
        return [0.5 + (i * 0.01) for i in range(8)]

    def fake_embed_batch(texts, action=None):
        return [fake_embed(t) for t in texts]

    mock_embedder = MagicMock()
    mock_embedder.embed.side_effect = fake_embed
    mock_embedder.embed_batch.side_effect = fake_embed_batch
    mem.embedding_model = mock_embedder

    # Mock LLM that returns a nice consolidated fact
    def fake_llm(messages, response_format=None):
        # The last user message contains the cluster
        user_content = messages[-1]["content"] if messages else ""
        if "pizza" in user_content.lower():
            return '{"memory": "User loves pizza, especially authentic Italian pizza from local restaurants.", "confidence": 0.93, "reason": "Merged variations about pizza preference"}'
        return '{"memory": "User enjoys coffee in the morning.", "confidence": 0.8, "reason": "Consolidated coffee facts"}'

    mock_llm = MagicMock()
    mock_llm.generate_response.side_effect = fake_llm
    mem.llm = mock_llm

    # In-memory fake vector store using a simple list
    class FakeVectorStore:
        def __init__(self):
            self._store = {}  # id -> {"vector": , "payload": }

        def insert(self, vectors=None, payloads=None, ids=None):
            for vid, vec, pay in zip(ids or [], vectors or [], payloads or []):
                self._store[vid] = {"vector": vec, "payload": pay}

        def list(self, filters=None, top_k=None):
            # Return objects that mimic real vector results
            results = []
            for vid, item in list(self._store.items())[: (top_k or 10000)]:
                class R:
                    pass
                r = R()
                r.id = vid
                r.payload = item["payload"]
                results.append(r)
            return results

        def search(self, *a, **k):
            return []

        def delete(self, vector_id):
            self._store.pop(vector_id, None)

        def update(self, *a, **k):
            pass

        def get(self, vid):
            item = self._store.get(vid)
            if item:
                class G: pass
                g = G()
                g.id = vid
                g.payload = item["payload"]
                return g
            return None

        # other required
        def create_col(self, *a, **k): pass
        def col_info(self): return {}
        def list_cols(self): return []
        def delete_col(self): pass
        def reset(self): self._store.clear()

    mem.vector_store = FakeVectorStore()
    mem.db = MagicMock()  # history not critical for demo

    # minimal other attrs
    mem.reranker = None
    mem._entity_store = None
    mem.custom_instructions = None
    mem.api_version = "v1.1"

    # Attach compactor manually (demo bypasses normal __init__)
    from mem0.memory.compaction import MemoryCompactor
    mem.compactor = MemoryCompactor(mem, cfg.compaction)

    # Seed some realistic bloat (variations of same facts)
    seeds = [
        "I really love pizza",
        "My favorite food is pizza, especially margherita",
        "I prefer authentic Italian pizza from local places",
        "Pizza is the best — thin crust only",
        "User drinks coffee every morning to wake up",
        "I need coffee first thing",
    ]

    for i, txt in enumerate(seeds):
        mid = f"mem_{i}"
        vec = fake_embed(txt)
        payload = {
            "data": txt,
            "user_id": "demo_user",
            "created_at": "2026-01-01T00:00:00+00:00",
            "hash": str(abs(hash(txt))),
        }
        mem.vector_store.insert(vectors=[vec], ids=[mid], payloads=[payload])

    return mem


def main():
    print("=== mem0 Compaction Demo ===\n")

    memory = build_mock_memory()

    print("Before compaction (seeded duplicates):")
    before = memory.vector_store.list(filters={"user_id": "demo_user"})
    print(f"  Count: {len(before)}")
    for m in before:
        print(f"    - {m.payload.get('data')}")

    print("\nRunning compaction (dry_run=False)...")
    result = memory.compact(
        filters={"user_id": "demo_user"},
        similarity_threshold=0.75,
        dry_run=False,
    )

    print("\nCompaction report:")
    import json
    print(json.dumps(result, indent=2))

    print("\nAfter compaction:")
    after = memory.vector_store.list(filters={"user_id": "demo_user"})
    print(f"  Count: {len(after)}")
    for m in after:
        print(f"    + {m.payload.get('data')}")

    print("\nDone. Similar memories were merged into cleaner, higher-quality entries.")


if __name__ == "__main__":
    main()
