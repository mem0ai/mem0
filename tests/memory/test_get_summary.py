from unittest.mock import MagicMock

import pytest

from mem0.exceptions import LLMError
from mem0.memory.main import AsyncMemory, Memory


def _setup_mocks(mocker):
    """Mock the factories so Memory/AsyncMemory construct without real providers."""
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vector_store.return_value, mocker.MagicMock()],
    )

    mocker.patch("mem0.utils.factory.LlmFactory.create", mocker.MagicMock())
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())
    mocker.patch("mem0.memory.main.capture_event")


_MEMORIES = [
    {"id": "1", "memory": "User's name is Yash"},
    {"id": "2", "memory": "User prefers dark mode"},
]


class TestGetSummarySync:
    @pytest.fixture
    def memory(self, mocker):
        _setup_mocks(mocker)
        return Memory()

    def test_returns_summary_and_count(self, memory):
        memory.get_all = MagicMock(return_value={"results": _MEMORIES})
        memory.llm.generate_response = MagicMock(return_value="Yash prefers dark mode.")

        result = memory.get_summary(filters={"user_id": "u1"})

        assert result == {"summary": "Yash prefers dark mode.", "memory_count": 2}
        memory.get_all.assert_called_once_with(filters={"user_id": "u1"}, top_k=100)
        # every memory's text is fed to the summarizer
        user_msg = memory.llm.generate_response.call_args[1]["messages"][1]["content"]
        assert "User's name is Yash" in user_msg
        assert "User prefers dark mode" in user_msg

    def test_empty_scope_returns_blank_without_calling_llm(self, memory):
        memory.get_all = MagicMock(return_value={"results": []})
        memory.llm.generate_response = MagicMock()

        result = memory.get_summary(filters={"user_id": "u1"})

        assert result == {"summary": "", "memory_count": 0}
        memory.llm.generate_response.assert_not_called()

    def test_missing_scope_raises_value_error(self, memory):
        # get_all enforces "at least one of user_id/agent_id/run_id"; get_summary must surface it.
        with pytest.raises(ValueError):
            memory.get_summary(filters={})

    @pytest.mark.parametrize("bad_limit", [0, -5, True])
    def test_invalid_limit_raises_value_error(self, memory, bad_limit):
        with pytest.raises(ValueError, match="limit must be a positive integer"):
            memory.get_summary(filters={"user_id": "u1"}, limit=bad_limit)

    def test_llm_failure_raises_llmerror_with_cause(self, memory):
        memory.get_all = MagicMock(return_value={"results": _MEMORIES})
        memory.llm.generate_response = MagicMock(side_effect=RuntimeError("429 rate limit"))

        with pytest.raises(LLMError) as exc_info:
            memory.get_summary(filters={"user_id": "u1"})
        assert isinstance(exc_info.value.__cause__, RuntimeError)


class TestGetSummaryAsync:
    @pytest.fixture
    def memory(self, mocker):
        _setup_mocks(mocker)
        return AsyncMemory()

    @pytest.mark.asyncio
    async def test_returns_summary_and_count(self, memory, mocker):
        memory.get_all = mocker.AsyncMock(return_value={"results": _MEMORIES})
        memory.llm.generate_response = MagicMock(return_value="Yash prefers dark mode.")

        result = await memory.get_summary(filters={"user_id": "u1"})

        assert result == {"summary": "Yash prefers dark mode.", "memory_count": 2}
        memory.get_all.assert_awaited_once_with(filters={"user_id": "u1"}, top_k=100)

    @pytest.mark.asyncio
    async def test_empty_scope_returns_blank_without_calling_llm(self, memory, mocker):
        memory.get_all = mocker.AsyncMock(return_value={"results": []})
        memory.llm.generate_response = MagicMock()

        result = await memory.get_summary(filters={"user_id": "u1"})

        assert result == {"summary": "", "memory_count": 0}
        memory.llm.generate_response.assert_not_called()
