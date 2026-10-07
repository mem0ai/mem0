"""Regression coverage for #7561 with real Qdrant and SQLite storage."""

import inspect
import sys
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from openai import APIConnectionError
from openai.resources.embeddings import Embeddings
from qdrant_client.models import PointVectors, SparseVector

from mem0 import AsyncMemory, Memory
from mem0.memory import main as memory_main
from mem0.memory import telemetry
from mem0.utils import spacy_models
from mem0.vector_stores.qdrant import Qdrant

TEXT = "prefers concise answers"
CHANGED_TEXT = "prefers detailed answers"


async def invoke(method, *args, **kwargs):
    result = method(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


def embedding_response(*, input, **kwargs):
    return SimpleNamespace(
        data=[
            SimpleNamespace(index=i, embedding=[0.0, 1.0, 0.0] if text == CHANGED_TEXT else [1.0, 0.0, 0.0])
            for i, text in enumerate(input)
        ]
    )


@pytest.fixture(params=[Memory, AsyncMemory], ids=["sync", "async"])
def memory_setup(request, tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("MEM0_TELEMETRY", "false")
    # These settings are cached at import time, before this fixture executes.
    monkeypatch.setattr(memory_main, "MEM0_TELEMETRY", False)
    monkeypatch.setattr(telemetry, "MEM0_TELEMETRY", False)
    # Exercise the real optional-dependency fallback without model downloads.
    monkeypatch.setitem(sys.modules, "spacy", None)
    monkeypatch.setitem(sys.modules, "fastembed", None)
    for name in ("_nlp_full", "_nlp_lemma"):
        monkeypatch.setattr(spacy_models, name, None)
    for name in ("_load_failed_full", "_load_failed_lemma"):
        monkeypatch.setattr(spacy_models, name, False)
    mocker.patch.object(httpx.Client, "send", side_effect=AssertionError("Unexpected network request"))
    create = mocker.patch.object(Embeddings, "create", side_effect=embedding_response)
    memory = request.param.from_config(
        {
            "llm": {"provider": "openai", "config": {"api_key": "offline-placeholder"}},
            "embedder": {"provider": "openai", "config": {"api_key": "offline-placeholder", "embedding_dims": 3}},
            "vector_store": {
                "provider": "qdrant",
                "config": {"collection_name": "metadata_updates", "embedding_model_dims": 3, "path": str(tmp_path)},
            },
            "history_db_path": ":memory:",
        }
    )
    try:
        yield memory, create
    finally:
        memory.embedding_model.client.close()
        memory.llm.client.close()
        memory.vector_store.client.close()
        memory.close()


async def seed(memory):
    added = await invoke(
        memory.add,
        TEXT,
        user_id="owner",
        metadata={"reviewed": False, "source": "chat"},
        expiration_date="2099-01-01",
        infer=False,
    )
    memory_id = added["results"][0]["id"]
    # Seed a sparse vector directly: preserving it must not require fastembed.
    memory.vector_store.client.update_vectors(
        collection_name="metadata_updates",
        points=[PointVectors(id=memory_id, vector={"bm25": SparseVector(indices=[7], values=[2.0])})],
    )
    return memory_id


def record(memory, memory_id):
    return memory.vector_store.client.retrieve(
        collection_name="metadata_updates", ids=[memory_id], with_vectors=True, with_payload=True
    )[0]


def outage():
    return APIConnectionError(
        message="synthetic embedding outage", request=httpx.Request("POST", "https://offline.invalid/embeddings")
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"metadata": {"reviewed": True}},
        {"expiration_date": "2098-01-01"},
        {"expiration_date": None},
        {"metadata": {}},
        {"metadata": {"reviewed": True}, "expiration_date": None},
    ],
    ids=["metadata", "set-expiry", "clear-expiry", "empty-metadata", "combined"],
)
async def test_payload_update_preserves_vectors_without_embedding(memory_setup, changes):
    memory, create = memory_setup
    memory_id = await seed(memory)
    before = record(memory, memory_id)
    assert before.vector["bm25"] == SparseVector(indices=[7], values=[2.0])
    original_changes = deepcopy(changes)
    create.reset_mock()
    create.side_effect = outage()

    result = await invoke(memory.update, memory_id, **changes)

    assert result == {"message": "Memory updated successfully!"}
    create.assert_not_called()
    after = record(memory, memory_id)
    assert after.vector == before.vector  # Both dense and BM25 sparse vectors.
    for key in ("data", "hash", "created_at", "user_id", "source", "text_lemmatized"):
        assert after.payload.get(key) == before.payload.get(key)
    assert after.payload["updated_at"] >= before.payload["updated_at"]
    for key, value in changes.get("metadata", {}).items():
        assert after.payload[key] == value
    if "expiration_date" in changes:
        assert after.payload["expiration_date"] == changes["expiration_date"]
    history = await invoke(memory.history, memory_id)
    updates = [entry for entry in history if entry["event"] == "UPDATE"]
    assert len(updates) == 1
    assert updates[0]["old_memory"] == updates[0]["new_memory"] == TEXT
    assert updates[0]["updated_at"] == after.payload["updated_at"]
    assert changes == original_changes


@pytest.mark.asyncio
async def test_payload_update_preserves_identity_and_input(memory_setup):
    memory, create = memory_setup
    memory_id = await seed(memory)
    metadata = {"user_id": "other", "agent_id": "injected", "reviewed": True}
    original = deepcopy(metadata)
    create.reset_mock()
    create.side_effect = outage()

    await invoke(memory.update, memory_id, metadata=metadata)

    create.assert_not_called()
    payload = record(memory, memory_id).payload
    assert payload["user_id"] == "owner"
    assert "agent_id" not in payload
    assert payload["reviewed"] is True
    assert metadata == original


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [TEXT, CHANGED_TEXT], ids=["explicit-same-text", "changed-text"])
async def test_explicit_text_still_embeds(memory_setup, text):
    memory, create = memory_setup
    memory_id = await seed(memory)
    create.reset_mock()

    await invoke(memory.update, memory_id, text=text, metadata={"reviewed": True})

    create.assert_called_once()
    after = record(memory, memory_id)
    assert after.payload["data"] == text
    assert after.payload["reviewed"] is True
    dense = after.vector[""] if isinstance(after.vector, dict) else after.vector
    assert dense == ([0.0, 1.0, 0.0] if text == CHANGED_TEXT else [1.0, 0.0, 0.0])


@pytest.mark.asyncio
async def test_adapter_without_opt_in_keeps_existing_embedding_behavior(memory_setup, monkeypatch):
    memory, create = memory_setup
    memory_id = await seed(memory)
    # Exercise the conservative base behavior through a real store.
    monkeypatch.delattr(Qdrant, "_supports_metadata_only_update", raising=False)
    create.reset_mock()

    await invoke(memory.update, memory_id, metadata={"reviewed": True})

    create.assert_called_once()
    assert record(memory, memory_id).payload["reviewed"] is True


@pytest.mark.asyncio
async def test_missing_memory_does_not_embed(memory_setup):
    memory, create = memory_setup
    create.side_effect = outage()

    with pytest.raises(ValueError, match="not found"):
        await invoke(memory.update, str(uuid4()), metadata={"reviewed": True})

    create.assert_not_called()


@pytest.mark.asyncio
async def test_payload_write_error_propagates_without_embedding_or_history(memory_setup, mocker):
    memory, create = memory_setup
    memory_id = await seed(memory)
    before = record(memory, memory_id)
    history = await invoke(memory.history, memory_id)
    create.reset_mock()
    # Fail at the external storage SDK boundary, not inside Mem0's adapter.
    mocker.patch.object(memory.vector_store.client, "set_payload", side_effect=RuntimeError("storage unavailable"))

    with pytest.raises(RuntimeError, match="storage unavailable"):
        await invoke(memory.update, memory_id, metadata={"reviewed": True})

    create.assert_not_called()
    assert record(memory, memory_id) == before
    assert await invoke(memory.history, memory_id) == history
