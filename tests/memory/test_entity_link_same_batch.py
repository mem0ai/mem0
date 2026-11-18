"""Same-batch entity resolutions must not drop earlier linked_memory_ids.

Adapted from the offline reproduction in
https://github.com/mem0ai/mem0/issues/7950. Two extracted names in one
``add()`` (``Alice`` by exact match, ``Alice.`` by similarity >= 0.95)
resolve to the entity row created by an earlier ``add()``. Links from that
earlier call stay; links written earlier in the same batch must stay too.
"""

import hashlib
import json
import os
from contextlib import contextmanager
from unittest.mock import patch

import pytest

os.environ.setdefault("MEM0_TELEMETRY", "False")

DIMS = 8

_ENTITIES = {
    "Alice likes tea": [("PROPER", "Alice")],
    "Alice met Bob": [("PROPER", "Alice")],
    "Alice. is a nurse": [("PROPER", "Alice.")],
}


def _vec(text):
    # "Alice" and "Alice." share a vector so the semantic merge threshold fires.
    key = text.rstrip(".").strip().lower()
    digest = hashlib.sha256(key.encode()).digest()
    raw = [((byte / 255.0) - 0.5) for byte in digest[:DIMS]]
    norm = sum(value * value for value in raw) ** 0.5
    return [value / norm for value in raw]


class _FakeEmbedder:
    def embed(self, text, memory_action=None):
        return _vec(text if isinstance(text, str) else json.dumps(text))

    def embed_batch(self, texts, memory_action="add"):
        return [self.embed(text, memory_action) for text in texts]


class _FakeLLM:
    def __init__(self):
        self.responses = []

    def generate_response(self, messages, **kwargs):
        return self.responses.pop(0)


def _extract_entities_batch(texts, batch_size=32):
    return [_ENTITIES.get(text, []) for text in texts]


def _config(tmp_path):
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "entity_link_same_batch",
                "path": str(tmp_path / "qdrant"),
                "embedding_model_dims": DIMS,
                "on_disk": False,
            },
        },
        "history_db_path": str(tmp_path / "history.db"),
    }


@contextmanager
def _patched_dependencies():
    with (
        patch("mem0.utils.factory.EmbedderFactory.create", return_value=_FakeEmbedder()),
        patch("mem0.utils.factory.LlmFactory.create", return_value=_FakeLLM()),
        patch("mem0.memory.main.extract_entities_batch", side_effect=_extract_entities_batch),
        patch("mem0.memory.main.capture_event"),
    ):
        yield


def _close_memory(memory):
    client = getattr(getattr(memory, "vector_store", None), "client", None)
    if client is not None and hasattr(client, "close"):
        client.close()
    memory.close()


def _alice_rows(memory):
    listed = memory.entity_store.list(filters={"user_id": "u1"}, top_k=100)
    rows = listed[0] if isinstance(listed, (list, tuple)) else listed
    return [row for row in rows if (row.payload or {}).get("data") in ("Alice", "Alice.")]


def _assert_same_batch_links(memory, m0, m1, m2, hits):
    alice_rows = _alice_rows(memory)
    assert [row.payload["data"] for row in alice_rows] == ["Alice"]
    linked = set()
    for row in alice_rows:
        linked |= set(row.payload.get("linked_memory_ids", []))
    assert linked == {m0, m1, m2}

    by_memory = {hit["memory"]: hit for hit in hits}
    assert "Alice met Bob" in by_memory
    # The link written earlier in the batch is what search uses to boost.
    assert by_memory["Alice met Bob"]["score_details"]["entity_boost"] > 0


def _queue_extractions(memory):
    memory.llm.responses.append(json.dumps({"memory": [{"text": "Alice likes tea"}]}))
    memory.llm.responses.append(json.dumps({"memory": [{"text": "Alice met Bob"}, {"text": "Alice. is a nurse"}]}))


def test_same_batch_entity_resolutions_keep_every_link(tmp_path):
    """Memory.add keeps every memory that resolves to one stored entity in the batch."""
    from mem0.memory.main import Memory

    with _patched_dependencies():
        memory = Memory.from_config(_config(tmp_path))
        try:
            _queue_extractions(memory)
            first = memory.add("I like tea. My name is Alice.", user_id="u1")["results"]
            second = memory.add("I met Bob. I am a nurse.", user_id="u1")["results"]
            ids = {item["memory"]: item["id"] for item in second}
            with patch("mem0.memory.main.extract_entities", return_value=[("PROPER", "Alice")]):
                hits = memory.search("Alice", filters={"user_id": "u1"}, threshold=0.0, explain=True)["results"]
            _assert_same_batch_links(memory, first[0]["id"], ids["Alice met Bob"], ids["Alice. is a nurse"], hits)
        finally:
            _close_memory(memory)


@pytest.mark.asyncio
async def test_async_same_batch_entity_resolutions_keep_every_link(tmp_path):
    """AsyncMemory.add keeps every memory that resolves to one stored entity in the batch."""
    from mem0.memory.main import AsyncMemory

    with _patched_dependencies():
        memory = AsyncMemory.from_config(_config(tmp_path))
        try:
            _queue_extractions(memory)
            first = (await memory.add("I like tea. My name is Alice.", user_id="u1"))["results"]
            second = (await memory.add("I met Bob. I am a nurse.", user_id="u1"))["results"]
            ids = {item["memory"]: item["id"] for item in second}
            with patch("mem0.memory.main.extract_entities", return_value=[("PROPER", "Alice")]):
                hits = (await memory.search("Alice", filters={"user_id": "u1"}, threshold=0.0, explain=True))["results"]
            _assert_same_batch_links(memory, first[0]["id"], ids["Alice met Bob"], ids["Alice. is a nurse"], hits)
        finally:
            _close_memory(memory)
