import datetime as _dt
from unittest.mock import Mock

import pytest

import mem0.configs.prompts as prompts_mod
from mem0.configs.prompts import (
    AGENT_MEMORY_EXTRACTION_PROMPT,
    CURRENT_DATE_PLACEHOLDER,
    FACT_RETRIEVAL_PROMPT,
    USER_MEMORY_EXTRACTION_PROMPT,
)
from mem0.memory.utils import (
    get_fact_retrieval_messages,
    get_fact_retrieval_messages_legacy,
    parse_messages,
    parse_vision_messages,
    remove_spaces_from_entities,
    sanitize_relationship_for_cypher,
)


class TestParseMessages:
    def test_skips_message_without_content_key(self):
        # Reproduces #5067: a FunctionCalling assistant message carries
        # `tool_calls` but no `content` key -> used to raise KeyError.
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "tool_calls": [{"id": "1", "function": {"name": "search"}}]},
            {"role": "assistant", "content": "done"},
        ]
        result = parse_messages(messages)
        assert result == "user: hi\nassistant: done\n"

    def test_skips_explicit_none_content(self):
        messages = [{"role": "assistant", "content": None}, {"role": "user", "content": "ok"}]
        assert parse_messages(messages) == "user: ok\n"

    def test_plain_roles_pass_through(self):
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "u"},
            {"role": "assistant", "content": "a"},
        ]
        assert parse_messages(messages) == "system: sys\nuser: u\nassistant: a\n"


class TestParseVisionMessages:
    def test_skips_message_without_content_key(self):
        # Reproduces #5067 for the vision parser path.
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "tool_calls": [{"id": "1", "function": {"name": "search"}}]},
        ]
        result = parse_vision_messages(messages, llm=None)
        assert len(result) == 1
        assert result[0] == {"role": "user", "content": "hi"}

    def test_multimodal_list_without_llm_extracts_text(self):
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "What is this?"},
                {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
            ]},
        ]
        result = parse_vision_messages(messages, llm=None)
        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "What is this?"

    def test_image_dict_without_llm_is_skipped(self):
        messages = [
            {"role": "user", "content": {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}}},
            {"role": "user", "content": "hello"},
        ]
        result = parse_vision_messages(messages, llm=None)
        assert len(result) == 1
        assert result[0]["content"] == "hello"

    def test_multimodal_with_llm_calls_generate_response(self):
        mock_llm = Mock()
        mock_llm.generate_response.return_value = "A photo of a cat"
        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": "Describe this"},
                {"type": "image_url", "image_url": {"url": "https://example.com/cat.png"}},
            ]},
        ]
        result = parse_vision_messages(messages, llm=mock_llm, vision_details="auto")
        assert result[0]["content"] == "A photo of a cat"
        mock_llm.generate_response.assert_called_once()

    def test_image_only_list_without_llm_is_skipped(self):
        messages = [
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
            ]},
        ]
        result = parse_vision_messages(messages, llm=None)
        assert result == []

    def test_plain_text_messages_pass_through(self):
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]
        result = parse_vision_messages(messages, llm=None)
        assert result == messages

    def test_malformed_image_dict_raises_value_error(self):
        # A malformed image part (missing the nested url) used to raise an
        # uncaught KeyError that aborted add(); it should raise a clear ValueError.
        mock_llm = Mock()
        messages = [{"role": "user", "content": {"type": "image_url", "image_url": {}}}]
        with pytest.raises(ValueError, match=r"missing image_url\.url"):
            parse_vision_messages(messages, llm=mock_llm)
        mock_llm.generate_response.assert_not_called()

    def test_none_image_url_raises_value_error(self):
        # image_url present but None (or any non-dict) must also raise the clear
        # ValueError, not an AttributeError from calling .get() on None.
        mock_llm = Mock()
        messages = [{"role": "user", "content": {"type": "image_url", "image_url": None}}]
        with pytest.raises(ValueError, match=r"missing image_url\.url"):
            parse_vision_messages(messages, llm=mock_llm)
        mock_llm.generate_response.assert_not_called()


class TestRemoveSpacesFromEntities:
    """
    Covers behavior used by Neo4j, Memgraph (sanitize_relationship=True),
    Kuzu, and Neptune (sanitize_relationship=False). All backends delegate here.
    """

    @pytest.mark.parametrize(
        "sanitize",
        [True, False],
        ids=["cypher_sanitized", "plain"],
    )
    def test_filters_empty_and_incomplete_dicts(self, sanitize):
        mixed = [
            {},
            {"source": "a"},
            {"source": "a", "relationship": "r"},
            {"source": "x", "relationship": "rel", "destination": "y"},
        ]
        out = remove_spaces_from_entities(mixed, sanitize_relationship=sanitize)
        assert len(out) == 1
        assert out[0]["source"] == "x"
        assert out[0]["destination"] == "y"

    @pytest.mark.parametrize("sanitize", [True, False])
    def test_all_empty_returns_empty(self, sanitize):
        assert remove_spaces_from_entities([{}, {}, {}], sanitize_relationship=sanitize) == []

    def test_skips_non_dict_entries(self):
        assert remove_spaces_from_entities([None, "not-a-dict", 123, {"source": "a", "relationship": "r", "destination": "b"}]) == [
            {"source": "a", "relationship": "r", "destination": "b"}
        ]

    def test_sanitize_true_relationship_uses_sanitizer(self):
        """Neo4j / Memgraph path: special characters mapped via sanitize_relationship_for_cypher."""
        entities = [{"source": "A", "relationship": "x/y", "destination": "B"}]
        out = remove_spaces_from_entities(entities, sanitize_relationship=True)
        assert out[0]["relationship"] == sanitize_relationship_for_cypher("x/y".lower().replace(" ", "_"))

    def test_sanitize_false_relationship_plain_only(self):
        """Kuzu / Neptune path: only lowercase and spaces to underscores."""
        entities = [{"source": "A", "relationship": "Works At", "destination": "B Co"}]
        out = remove_spaces_from_entities(entities, sanitize_relationship=False)
        assert out[0]["relationship"] == "works_at"
        assert out[0]["source"] == "a"
        assert out[0]["destination"] == "b_co"

    def test_sanitize_true_vs_false_slash_in_relationship(self):
        """Slash is rewritten when sanitizing (Cypher path); kept as-is for plain path."""
        base = {"source": "s", "relationship": "a/b", "destination": "d"}
        t = remove_spaces_from_entities([dict(base)], sanitize_relationship=True)[0]["relationship"]
        f = remove_spaces_from_entities([dict(base)], sanitize_relationship=False)[0]["relationship"]
        assert t == sanitize_relationship_for_cypher("a/b")
        assert f == "a/b"


class _FrozenDateTime:
    """Stand-in for datetime whose now() returns a settable fixed value."""

    fixed = _dt.datetime(2020, 1, 1)

    @classmethod
    def now(cls, tz=None):
        return cls.fixed


class TestCurrentDateInjection:
    """The extraction prompts must use the real date at call time, not a date
    frozen when the module was imported (long-running processes would otherwise
    report a stale date on every extraction after their start day)."""

    def test_prompts_carry_placeholder_not_a_baked_date(self):
        # The module-level prompts must hold the placeholder, so the date is
        # injected later rather than evaluated once at import.
        for prompt in (FACT_RETRIEVAL_PROMPT, USER_MEMORY_EXTRACTION_PROMPT, AGENT_MEMORY_EXTRACTION_PROMPT):
            assert CURRENT_DATE_PLACEHOLDER in prompt

    def test_date_injected_at_call_time(self, monkeypatch):
        monkeypatch.setattr(prompts_mod, "datetime", _FrozenDateTime)
        _FrozenDateTime.fixed = _dt.datetime(2020, 1, 1)
        system, _ = get_fact_retrieval_messages("hello")
        assert "Today's date is 2020-01-01." in system
        # The placeholder must be fully resolved, never leaked to the model.
        assert CURRENT_DATE_PLACEHOLDER not in system

    def test_date_refreshes_across_days(self, monkeypatch):
        # The heart of the bug: the same process must not keep returning the date
        # from the day it was started.
        monkeypatch.setattr(prompts_mod, "datetime", _FrozenDateTime)
        _FrozenDateTime.fixed = _dt.datetime(2020, 1, 1)
        day1, _ = get_fact_retrieval_messages("hello")
        _FrozenDateTime.fixed = _dt.datetime(2020, 6, 15)
        day2, _ = get_fact_retrieval_messages("hello")
        assert "Today's date is 2020-01-01." in day1
        assert "Today's date is 2020-06-15." in day2

    def test_agent_and_legacy_paths_also_inject(self, monkeypatch):
        monkeypatch.setattr(prompts_mod, "datetime", _FrozenDateTime)
        _FrozenDateTime.fixed = _dt.datetime(2022, 12, 25)
        agent_system, _ = get_fact_retrieval_messages("hi", is_agent_memory=True)
        legacy_system, _ = get_fact_retrieval_messages_legacy("hi")
        assert "Today's date is 2022-12-25." in agent_system
        assert "Today's date is 2022-12-25." in legacy_system
