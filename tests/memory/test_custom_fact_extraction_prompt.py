"""Tests for the ``custom_fact_extraction_prompt`` full-override lever.

Restores the pre-#4805 capability that let self-hosted callers replace the
extraction system prompt entirely so recall can be dialled down (see
https://github.com/mem0ai/mem0/issues/5730). The default (``None``) is
byte-for-byte identical to current behaviour; when set, the value replaces
``ADDITIVE_EXTRACTION_PROMPT`` as the extraction system prompt. Caller owns
the JSON output contract when overriding.
"""

from unittest.mock import MagicMock

import pytest

from mem0.configs.base import MemoryConfig
from mem0.configs.prompts import ADDITIVE_EXTRACTION_PROMPT, AGENT_CONTEXT_SUFFIX
from mem0.memory.main import AsyncMemory, Memory


def _setup_mocks(mocker):
    """Mirror of the fixture helper in tests/memory/test_main.py."""
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vector_store.return_value, mocker.MagicMock()],
    )

    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)

    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

    return mock_llm, mock_vector_store


def _extract_system_prompt(mock_memory):
    """Return the system-message content passed to the mocked LLM."""
    call_args = mock_memory.llm.generate_response.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    system_messages = [m["content"] for m in messages if m["role"] == "system"]
    assert len(system_messages) == 1, f"expected exactly one system message, got {len(system_messages)}"
    return system_messages[0]


def _extract_user_prompt(mock_memory):
    """Return the user-message content passed to the mocked LLM."""
    call_args = mock_memory.llm.generate_response.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    user_messages = [m["content"] for m in messages if m["role"] == "user"]
    assert len(user_messages) == 1
    return user_messages[0]


# ---------------------------------------------------------------------------
# Sync ``Memory`` — full-override behaviour
# ---------------------------------------------------------------------------


class TestCustomFactExtractionPromptSync:
    @pytest.fixture
    def mock_memory(self, mocker):
        mock_llm, _ = _setup_mocks(mocker)
        mock_llm.return_value.generate_response.return_value = '{"memory": []}'

        memory = Memory()
        memory.custom_instructions = None
        memory.custom_fact_extraction_prompt = None
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        return memory

    def test_default_behavior_unchanged(self, mock_memory):
        """Characterization: with the override unset, the extraction system
        prompt is exactly ``ADDITIVE_EXTRACTION_PROMPT`` (no regression)."""
        mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            filters={"user_id": "u1"},
            infer=True,
        )
        assert _extract_system_prompt(mock_memory) == ADDITIVE_EXTRACTION_PROMPT

    def test_override_replaces_system_prompt(self, mock_memory):
        """When set, the override string replaces the extraction system prompt.

        This is the recall-knob for #5730 — the caller can now dial recall
        DOWN by supplying a stricter extraction prompt.
        """
        override = (
            "You are a strict fact extractor. Only extract explicit, durable "
            'user facts. Return JSON: {"memory": [{"text": <str>}, ...]}.'
        )
        mock_memory.custom_fact_extraction_prompt = override

        mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            filters={"user_id": "u1"},
            infer=True,
        )

        system_prompt = _extract_system_prompt(mock_memory)
        assert system_prompt == override
        # And critically: the high-recall additive prompt must not leak in.
        assert "Memory Extractor" not in system_prompt

    def test_override_coexists_with_custom_instructions(self, mock_memory):
        """The two levers are orthogonal: ``custom_fact_extraction_prompt``
        replaces the SYSTEM prompt, while ``custom_instructions`` still
        appends to the USER prompt. Users can (and typically will) use both."""
        override = "You are a strict fact extractor."
        mock_memory.custom_fact_extraction_prompt = override
        mock_memory.custom_instructions = "Never extract sports scores."

        mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            filters={"user_id": "u1"},
            infer=True,
        )

        assert _extract_system_prompt(mock_memory) == override
        user_prompt = _extract_user_prompt(mock_memory)
        assert "## Custom Instructions" in user_prompt
        assert "Never extract sports scores." in user_prompt

    def test_override_preserves_agent_context_suffix(self, mock_memory):
        """Agent-scoping is orthogonal to which base prompt is chosen: when
        the caller overrides AND the extraction is agent-scoped, the
        ``AGENT_CONTEXT_SUFFIX`` still appends to the override."""
        override = "You are a strict fact extractor."
        mock_memory.custom_fact_extraction_prompt = override

        mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            filters={"agent_id": "a1"},  # agent-scoped, no user_id
            infer=True,
        )

        system_prompt = _extract_system_prompt(mock_memory)
        assert system_prompt == override + AGENT_CONTEXT_SUFFIX

    @pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
    def test_blank_override_falls_back_to_default(self, mock_memory, blank):
        """A blank / whitespace-only override is treated as unset, so a stray
        empty value can't wipe the extraction system prompt."""
        mock_memory.custom_fact_extraction_prompt = blank
        mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            filters={"user_id": "u1"},
            infer=True,
        )
        assert _extract_system_prompt(mock_memory) == ADDITIVE_EXTRACTION_PROMPT


# ---------------------------------------------------------------------------
# Async ``AsyncMemory`` — same contract
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCustomFactExtractionPromptAsync:
    @pytest.fixture
    def mock_async_memory(self, mocker):
        mock_llm, _ = _setup_mocks(mocker)
        mock_llm.return_value.generate_response.return_value = '{"memory": []}'

        memory = AsyncMemory()
        memory.custom_instructions = None
        memory.custom_fact_extraction_prompt = None
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        return memory

    async def test_default_behavior_unchanged(self, mock_async_memory):
        await mock_async_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            effective_filters={"user_id": "u1"},
            infer=True,
        )
        assert _extract_system_prompt(mock_async_memory) == ADDITIVE_EXTRACTION_PROMPT

    async def test_override_replaces_system_prompt(self, mock_async_memory):
        override = "You are a strict fact extractor."
        mock_async_memory.custom_fact_extraction_prompt = override

        await mock_async_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            effective_filters={"user_id": "u1"},
            infer=True,
        )

        system_prompt = _extract_system_prompt(mock_async_memory)
        assert system_prompt == override
        assert "Memory Extractor" not in system_prompt

    async def test_override_coexists_with_custom_instructions(self, mock_async_memory):
        override = "You are a strict fact extractor."
        mock_async_memory.custom_fact_extraction_prompt = override
        mock_async_memory.custom_instructions = "Never extract sports scores."

        await mock_async_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            effective_filters={"user_id": "u1"},
            infer=True,
        )

        assert _extract_system_prompt(mock_async_memory) == override
        user_prompt = _extract_user_prompt(mock_async_memory)
        assert "## Custom Instructions" in user_prompt
        assert "Never extract sports scores." in user_prompt

    async def test_override_preserves_agent_context_suffix(self, mock_async_memory):
        override = "You are a strict fact extractor."
        mock_async_memory.custom_fact_extraction_prompt = override

        await mock_async_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            effective_filters={"agent_id": "a1"},
            infer=True,
        )

        system_prompt = _extract_system_prompt(mock_async_memory)
        assert system_prompt == override + AGENT_CONTEXT_SUFFIX

    @pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
    async def test_blank_override_falls_back_to_default(self, mock_async_memory, blank):
        """Async parity: a blank / whitespace-only override is treated as unset."""
        mock_async_memory.custom_fact_extraction_prompt = blank
        await mock_async_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            effective_filters={"user_id": "u1"},
            infer=True,
        )
        assert _extract_system_prompt(mock_async_memory) == ADDITIVE_EXTRACTION_PROMPT


# ---------------------------------------------------------------------------
# ``MemoryConfig`` plumbing
# ---------------------------------------------------------------------------


class TestMemoryConfigCustomFactExtractionPrompt:
    def test_default_is_none(self):
        """Backwards-compat: default MemoryConfig has the field as None."""
        cfg = MemoryConfig()
        assert cfg.custom_fact_extraction_prompt is None

    def test_field_accepts_string(self):
        """The field is a real pydantic field, not silently dropped as
        ``extra`` (which was the bug the openmemory sub-project has been
        hitting since #4805 landed)."""
        override = "You are a strict fact extractor."
        cfg = MemoryConfig(custom_fact_extraction_prompt=override)
        assert cfg.custom_fact_extraction_prompt == override

    def test_memory_init_wires_field_from_config(self, mocker):
        """``Memory.__init__`` copies the field off MemoryConfig onto the
        instance, mirroring the existing ``custom_instructions`` wiring."""
        _setup_mocks(mocker)
        override = "You are a strict fact extractor."
        memory = Memory(MemoryConfig(custom_fact_extraction_prompt=override))
        assert memory.custom_fact_extraction_prompt == override

    def test_async_memory_init_wires_field_from_config(self, mocker):
        _setup_mocks(mocker)
        override = "You are a strict fact extractor."
        memory = AsyncMemory(MemoryConfig(custom_fact_extraction_prompt=override))
        assert memory.custom_fact_extraction_prompt == override
