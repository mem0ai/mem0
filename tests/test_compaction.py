"""
Tests for memory compaction.
"""

from unittest.mock import MagicMock

import pytest

from mem0.configs.base import MemoryConfig, CompactionConfig
from mem0.memory.main import Memory


def _make_mock_memory_with_data(memories_data, compaction_cfg=None):
    """Helper to create a Memory with controlled store for compaction tests."""
    cfg = MemoryConfig(compaction=compaction_cfg or CompactionConfig(enabled=True))
    m = Memory.__new__(Memory)
    m.config = cfg

    # Embedder
    def _embed(t, *args, **kwargs):
        if "pizza" in t.lower():
            return [1.0, 0.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0, 0.0]

    mock_emb = MagicMock()
    mock_emb.embed.side_effect = _embed
    mock_emb.embed_batch.side_effect = lambda ts, *args, **kwargs: [_embed(t) for t in ts]
    m.embedding_model = mock_emb

    # LLM returns nice consolidated
    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = (
        '{"memory": "User really loves pizza.", "confidence": 0.9, "reason": "merged"}'
    )
    m.llm = mock_llm

    class Store:
        def __init__(self):
            self.data = {}

        def list(self, filters=None, top_k=None):
            class Item:
                pass

            items = []
            for mid, p in self.data.items():
                it = Item()
                it.id = mid
                it.payload = p
                items.append(it)
            return items

        def insert(self, vectors, ids, payloads):
            for i, vid in enumerate(ids):
                self.data[vid] = payloads[i]

        def delete(self, vid):
            self.data.pop(vid, None)

        def search(self, *args, **kwargs):
            return []

        def update(self, *args, **kwargs):
            pass

        def get(self, vid):
            return None

        def create_col(self, *args, **kwargs):
            pass

        def delete_col(self):
            pass

        def col_info(self):
            return {}

        def list_cols(self):
            return []

        def reset(self):
            self.data.clear()

    m.vector_store = Store()
    m.db = MagicMock()
    m.reranker = None
    m._entity_store = None
    m.custom_instructions = None
    m.api_version = "v1.1"

    # seed
    for i, txt in enumerate(memories_data):
        mid = f"m{i}"
        m.vector_store.data[mid] = {"data": txt, "user_id": "u1", "created_at": "2026-01-01"}

    m.compactor = None  # will be created lazily
    return m


def test_compaction_runs_without_error_and_returns_report():
    data = [
        "I love pizza",
        "Pizza is my favorite food",
        "I really enjoy pizza especially Italian",
        "Coffee is great in the morning",
    ]
    mem = _make_mock_memory_with_data(data)
    res = mem.compact(filters={"user_id": "u1"}, similarity_threshold=0.7, dry_run=True)

    assert res["before_count"] == 4
    assert res["after_count"] == 4
    assert res["merges"] == 1
    assert res["details"][0]["size"] == 3
    assert res["dry_run"] is True


def test_compaction_dry_run_does_not_modify():
    data = ["love pizza", "pizza pizza pizza"]
    mem = _make_mock_memory_with_data(data)
    before = len(mem.vector_store.list({}))
    res = mem.compact(filters={"user_id": "u1"}, dry_run=True)
    after = len(mem.vector_store.list({}))
    assert before == after
    assert res["dry_run"] is True


def test_compaction_replaces_a_cluster_with_one_memory():
    mem = _make_mock_memory_with_data(["love pizza", "pizza is my favorite"])

    res = mem.compact(filters={"user_id": "u1"}, dry_run=False)

    assert res["before_count"] == 2
    assert res["after_count"] == 1
    assert res["merges"] == 1
    assert len(mem.vector_store.data) == 1
    assert next(iter(mem.vector_store.data.values()))["data"] == "User really loves pizza."


def test_compaction_preserves_originals_when_insert_fails():
    mem = _make_mock_memory_with_data(["love pizza", "pizza is my favorite"])
    mem.vector_store.insert = MagicMock(side_effect=RuntimeError("write failed"))

    res = mem.compact(filters={"user_id": "u1"}, dry_run=False)

    assert res["before_count"] == 2
    assert res["after_count"] == 2
    assert res["merges"] == 0
    assert len(mem.vector_store.data) == 2


def test_compaction_requires_scope_filters():
    mem = _make_mock_memory_with_data(["love pizza", "pizza is my favorite"])

    with pytest.raises(ValueError, match="requires filters"):
        mem.compact()
