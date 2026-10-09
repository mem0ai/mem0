import inspect
import json
from copy import deepcopy
from unittest.mock import Mock

import pytest
from qdrant_client import QdrantClient

from mem0 import AsyncMemory, Memory
from mem0.configs.base import MemoryConfig
from mem0.memory.utils import parse_vision_messages


@pytest.mark.parametrize("vision", [False, True])
def test_system_text_parts_preserve_fields_and_input(vision):
    llm = Mock() if vision else None
    message = {
        "role": "system",
        "name": "instructions",
        "content": [{"type": "text", "text": "You are"}, {"type": "text", "text": "helpful."}],
        "custom_field": {"enabled": True},
    }
    original = deepcopy(message)

    assert parse_vision_messages([message], llm=llm) == [{**original, "content": "You are helpful."}]
    assert message == original
    if llm is not None:
        llm.generate_response.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("memory_class", [Memory, AsyncMemory], ids=["sync", "async"])
@pytest.mark.parametrize("vision", [False, True], ids=["vision-off", "vision-on"])
@pytest.mark.parametrize("extract_fact", [False, True], ids=["no-facts", "one-fact"])
@pytest.mark.parametrize("text_parts", [True, False], ids=["text-parts", "plain-string"])
async def test_add_system_text_persists_consistently(memory_class, vision, extract_fact, text_parts, monkeypatch):
    """Exercise the public API with real local Qdrant and SQLite, including the no-facts path."""
    fact = "The user likes coffee."
    llm = Mock()
    llm.generate_response.return_value = json.dumps({"memory": [{"text": fact}] if extract_fact else []})
    embedder = Mock()
    embedder.embed.return_value = [1.0, 0.0, 0.0]
    embedder.embed_batch.side_effect = lambda texts, *args: [[1.0, 0.0, 0.0] for _ in texts]
    monkeypatch.setattr("mem0.memory.main.LlmFactory.create", lambda *args: llm)
    monkeypatch.setattr("mem0.memory.main.EmbedderFactory.create", lambda *args: embedder)
    monkeypatch.setattr("mem0.memory.main.MEM0_TELEMETRY", False)
    monkeypatch.setattr("mem0.memory.main.capture_event", lambda *args: None)

    client = QdrantClient(":memory:")
    config = MemoryConfig(
        history_db_path=":memory:",
        vector_store={"provider": "qdrant", "config": {"client": client, "embedding_model_dims": 3}},
        llm={"provider": "openai", "config": {"enable_vision": vision}},
    )
    memory = memory_class(config)
    system_text = "You are helpful."
    messages = [
        {
            "role": "system",
            "name": "instructions",
            "content": [{"type": "text", "text": system_text}] if text_parts else system_text,
        },
        {"role": "user", "content": "I like coffee."},
    ]
    original = deepcopy(messages)
    try:
        result = memory.add(messages, user_id="alice", infer=True)
        if inspect.isawaitable(result):
            result = await result

        rows = memory.db.connection.execute("SELECT role, content, name FROM messages ORDER BY rowid").fetchall()
        assert rows == [("system", system_text, "instructions"), ("user", "I like coffee.", None)]
        assert messages == original
        llm.generate_response.assert_called_once()
        request = llm.generate_response.call_args.kwargs
        assert request["response_format"] == {"type": "json_object"}
        assert f"system: {system_text}\n" in request["messages"][1]["content"]

        vectors = client.scroll(collection_name=memory.collection_name)[0]
        history = memory.db.connection.execute("SELECT memory_id, new_memory, event FROM history").fetchall()
        if extract_fact:
            returned = result["results"]
            assert len(returned) == len(vectors) == len(history) == 1
            assert returned[0] == {"id": vectors[0].id, "memory": fact, "event": "ADD"}
            assert vectors[0].payload["data"] == fact
            assert history == [(returned[0]["id"], fact, "ADD")]
        else:
            assert result["results"] == vectors == history == []
    finally:
        memory.close()
        client.close()
