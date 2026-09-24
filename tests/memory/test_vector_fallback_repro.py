"""Regression tests for #7201: V3 add() returns failed fallback vector
inserts as successful memories, and passes them to history/entity indexing."""

import asyncio
from unittest.mock import MagicMock

import pytest

from mem0.exceptions import VectorStoreError
from mem0.memory.main import Memory, AsyncMemory


def _build_memory(mocker, cls=Memory):
    """Wire a Memory/AsyncMemory with mocked LLM/embeddings/vector store; the
    vector store fails the batch insert and the second individual fallback
    insert. AsyncMemory routes its sync calls through asyncio.to_thread, so
    the same MagicMock wiring works for both classes."""
    memory = cls.__new__(cls)
    memory.api_version = "v1.1"
    memory.custom_instructions = None
    memory.db = MagicMock()
    memory.db.get_last_messages.return_value = []
    memory.embedding_model = MagicMock()
    memory.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    memory.embedding_model.embed_batch.return_value = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
    ]
    memory.llm = MagicMock()
    memory.llm.generate_response.return_value = '{"memory": [{"text": "first memory"}, {"text": "second memory"}]}'
    memory.vector_store = MagicMock()
    memory._entity_store = MagicMock()

    def fail_batch_and_second_record(*, vectors, ids, payloads):
        if len(ids) > 1:
            raise RuntimeError("batch insert failed")
        if payloads[0]["data"] == "second memory":
            raise RuntimeError("single insert failed")

    memory.vector_store.insert.side_effect = fail_batch_and_second_record
    extract_entities = mocker.patch(
        "mem0.memory.main.extract_entities_batch",
        return_value=[[]],
    )
    mocker.patch("mem0.memory.main.capture_event")
    return memory, extract_entities


def test_failed_fallback_record_is_not_returned_or_indexed(mocker):
    memory, extract_entities = _build_memory(mocker)

    result = memory._add_to_vector_store(
        messages=[{"role": "user", "content": "remember two facts"}],
        metadata={},
        filters={"user_id": "u1"},
        infer=True,
    )

    assert [item["memory"] for item in result] == ["first memory"]
    history_records = memory.db.batch_add_history.call_args.args[0]
    assert [record["new_memory"] for record in history_records] == ["first memory"]
    extract_entities.assert_called_once_with(["first memory"])


def test_failed_fallback_record_is_not_indexed_async(mocker):
    """The async path (AsyncMemory) has the identical bug; it must be fixed
    in lockstep."""
    memory, _ = _build_memory(mocker, cls=AsyncMemory)

    result = asyncio.run(
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "remember two facts"}],
            metadata={},
            effective_filters={"user_id": "u1"},
            infer=True,
        )
    )

    assert [item["memory"] for item in result] == ["first memory"]
    history_records = memory.db.batch_add_history.call_args.args[0]
    assert [record["new_memory"] for record in history_records] == ["first memory"]


def test_all_fallback_inserts_failing_raises(mocker):
    """If no fallback insert succeeds, the write must raise an explicit
    vector-store error instead of reporting success with zero memories."""
    memory = Memory.__new__(Memory)
    memory.api_version = "v1.1"
    memory.custom_instructions = None
    memory.db = MagicMock()
    memory.db.get_last_messages.return_value = []
    memory.embedding_model = MagicMock()
    memory.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    memory.embedding_model.embed_batch.return_value = [[0.1, 0.2, 0.3]]
    memory.llm = MagicMock()
    memory.llm.generate_response.return_value = '{"memory": [{"text": "one memory"}]}'
    memory.vector_store = MagicMock()
    memory.vector_store.insert.side_effect = RuntimeError("vector store down")
    memory._entity_store = MagicMock()
    mocker.patch("mem0.memory.main.extract_entities_batch", return_value=[[]])
    mocker.patch("mem0.memory.main.capture_event")

    with pytest.raises(VectorStoreError) as exc_info:
        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "remember one fact"}],
            metadata={},
            filters={"user_id": "u1"},
            infer=True,
        )

    assert "vector store" in str(exc_info.value).lower()
    memory.db.batch_add_history.assert_not_called()
