"""Verify that MemoryConfig.use_input_language reaches the extraction prompt."""

from unittest.mock import MagicMock

import pytest

from mem0.configs.base import MemoryConfig
from mem0.memory.main import AsyncMemory, Memory


def _build_memory(mocker, memory_cls, *, use_input_language):
    embedder = MagicMock()
    embedder.embed.return_value = [0.1, 0.2, 0.3]
    vector_store = MagicMock()
    vector_store.search.return_value = []
    llm = MagicMock()
    llm.generate_response.return_value = '{"memory": []}'

    mocker.patch("mem0.memory.main.EmbedderFactory.create", return_value=embedder)
    mocker.patch("mem0.memory.main.VectorStoreFactory.create", return_value=vector_store)
    mocker.patch("mem0.memory.main.LlmFactory.create", return_value=llm)
    mocker.patch("mem0.memory.main.SQLiteManager", return_value=MagicMock())
    mocker.patch("mem0.memory.main.MEM0_TELEMETRY", False)

    memory = memory_cls.from_config({"use_input_language": use_input_language})
    memory.db.get_last_messages.return_value = []
    return memory


def _extraction_user_prompt(memory):
    return memory.llm.generate_response.call_args.kwargs["messages"][1]["content"]


def test_flag_defaults_to_false():
    assert MemoryConfig().use_input_language is False


@pytest.mark.parametrize("use_input_language", [False, True])
def test_sync_config_reaches_extraction_prompt(mocker, use_input_language):
    memory = _build_memory(mocker, Memory, use_input_language=use_input_language)

    memory._add_to_vector_store(
        messages=[{"role": "user", "content": "我叫小明"}],
        metadata={},
        filters={"user_id": "xiaoming"},
        infer=True,
    )

    user_prompt = _extraction_user_prompt(memory)
    assert ("## Language Requirement" in user_prompt) is use_input_language


@pytest.mark.asyncio
@pytest.mark.parametrize("use_input_language", [False, True])
async def test_async_config_reaches_extraction_prompt(mocker, use_input_language):
    memory = _build_memory(mocker, AsyncMemory, use_input_language=use_input_language)

    await memory._add_to_vector_store(
        messages=[{"role": "user", "content": "我叫小明"}],
        metadata={},
        effective_filters={"user_id": "xiaoming"},
        infer=True,
    )

    user_prompt = _extraction_user_prompt(memory)
    assert ("## Language Requirement" in user_prompt) is use_input_language
