"""Actor attribution through public OSS APIs with real local Qdrant and SQLite."""

from copy import deepcopy

import pytest

from mem0 import AsyncMemory, Memory
from mem0.embeddings.mock import MockEmbeddings


@pytest.fixture(params=[Memory, AsyncMemory], ids=["sync", "async"])
def local_memory(request, tmp_path, mocker, monkeypatch):
    monkeypatch.setattr("mem0.memory.main.MEM0_TELEMETRY", False)
    monkeypatch.setattr("mem0.memory.telemetry.MEM0_TELEMETRY", False)
    embedder = MockEmbeddings()
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=embedder)
    llm = mocker.Mock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", return_value=llm)
    memory = request.param.from_config(
        {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "actor_attribution",
                    "embedding_model_dims": 10,
                    "path": str(tmp_path / "qdrant"),
                },
            },
            "history_db_path": str(tmp_path / "history.db"),
        }
    )
    try:
        yield memory
        llm.generate_response.assert_not_called()
    finally:
        memory.close()
        memory.vector_store.client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("content_parts", [False, True], ids=["string", "content-parts"])
async def test_named_message_actor_survives_add_storage_history_and_search(local_memory, content_parts):
    memory = local_memory
    text = "planner recommends tea"
    content = [{"type": "text", "text": text}] if content_parts else text
    messages = [
        {"role": "assistant", "name": "planner", "content": content},
        {"role": "user", "content": content},
    ]
    original_messages = deepcopy(messages)
    metadata = {"topic": "drink"}
    original_metadata = deepcopy(metadata)

    added = memory.add(messages, user_id="alice", metadata=metadata, infer=False)
    if isinstance(memory, AsyncMemory):
        added = await added
    named, unnamed = added["results"]
    assert named["actor_id"] == "planner"
    assert unnamed["actor_id"] is None
    assert messages == original_messages
    assert metadata == original_metadata

    for result, actor, role in ((named, "planner", "assistant"), (unnamed, None, "user")):
        payload = memory.vector_store.get(result["id"]).payload
        assert payload["data"] == text
        assert payload["user_id"] == "alice"
        assert payload["topic"] == "drink"
        assert payload["role"] == role
        assert payload.get("actor_id") == actor
        history = memory.history(result["id"])
        if isinstance(memory, AsyncMemory):
            history = await history
        assert len(history) == 1
        assert history[0]["actor_id"] == actor
        assert history[0]["role"] == role

    for actor, expected_ids in (("planner", [named["id"]]), ("nobody", [])):
        matches = memory.search(text, filters={"user_id": "alice", "actor_id": actor})
        if isinstance(memory, AsyncMemory):
            matches = await matches
        assert [result["id"] for result in matches["results"]] == expected_ids
