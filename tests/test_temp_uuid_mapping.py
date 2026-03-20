import logging
from types import SimpleNamespace

import pytest

from mem0.memory.main import AsyncMemory, Memory


def _build_memory(mocker, memory_cls):
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create", side_effect=[mock_vector_store.return_value, mocker.MagicMock()]
    )
    mocker.patch("mem0.utils.factory.LlmFactory.create", mocker.MagicMock())
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())
    mocker.patch("mem0.memory.main.capture_event", mocker.MagicMock())

    memory = memory_cls()
    memory.config = mocker.MagicMock()
    memory.config.custom_fact_extraction_prompt = None
    memory.config.custom_update_memory_prompt = None
    memory.api_version = "v1.1"
    return memory


@pytest.mark.parametrize("event_type", ["UPDATE", "DELETE"])
def test_sync_skips_missing_temp_uuid_mapping_ids(mocker, caplog, event_type):
    memory = _build_memory(mocker, Memory)
    memory.llm.generate_response.side_effect = [
        '{"facts": ["new fact"]}',
        f'{{"memory": [{{"id": "12", "text": "changed memory", "event": "{event_type}"}}]}}',
    ]
    memory.vector_store.search.return_value = [SimpleNamespace(id="real-memory-id", payload={"data": "stored memory"})]
    memory._update_memory = mocker.MagicMock()
    memory._delete_memory = mocker.MagicMock()

    with caplog.at_level(logging.WARNING):
        result = memory._add_to_vector_store(
            messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
        )

    assert result == []
    assert f"Skipping {event_type}: memory ID '12' not found in mapping" in caplog.text
    memory._update_memory.assert_not_called()
    memory._delete_memory.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("event_type", ["UPDATE", "DELETE"])
async def test_async_skips_missing_temp_uuid_mapping_ids(mocker, caplog, event_type):
    memory = _build_memory(mocker, AsyncMemory)
    memory.llm.generate_response.side_effect = [
        '{"facts": ["new fact"]}',
        f'{{"memory": [{{"id": "12", "text": "changed memory", "event": "{event_type}"}}]}}',
    ]
    memory.vector_store.search.return_value = [SimpleNamespace(id="real-memory-id", payload={"data": "stored memory"})]
    memory._update_memory = mocker.AsyncMock()
    memory._delete_memory = mocker.AsyncMock()

    with caplog.at_level(logging.WARNING):
        result = await memory._add_to_vector_store(
            messages=[{"role": "user", "content": "test"}], metadata={}, effective_filters={}, infer=True
        )

    assert result == []
    assert f"Skipping {event_type}: memory ID '12' not found in mapping" in caplog.text
    memory._update_memory.assert_not_awaited()
    memory._delete_memory.assert_not_awaited()
