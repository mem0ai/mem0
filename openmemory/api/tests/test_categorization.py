"""Tests for memory categorization using the configured LLM provider."""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
from tenacity import RetryError

from app.utils.categorization import (
    BatchMemoryCategories,
    MemoryCategories,
    _get_llm,
    get_categories_for_memories,
    get_categories_for_memory,
)
from app.utils.prompts import MEMORY_CATEGORIZATION_PROMPT


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_llm():
    """Return a mock LLM with a generate_response method."""
    llm = MagicMock()
    llm.generate_response.return_value = json.dumps({"categories": ["work", "projects"]})
    return llm


@pytest.fixture
def mock_memory_client(mock_llm):
    """Return a mock Memory client whose .llm is mock_llm."""
    client = MagicMock()
    client.llm = mock_llm
    return client


@pytest.fixture
def mock_memory_module():
    """Temporarily inject a mock for app.utils.memory into sys.modules
    so that _get_llm()'s lazy import resolves without heavy dependencies."""
    mock_mod = MagicMock()
    original = sys.modules.get("app.utils.memory")
    sys.modules["app.utils.memory"] = mock_mod
    yield mock_mod
    if original is not None:
        sys.modules["app.utils.memory"] = original
    else:
        sys.modules.pop("app.utils.memory", None)


# ---------------------------------------------------------------------------
# _get_llm
# ---------------------------------------------------------------------------

class TestGetLlm:

    def test_returns_llm_from_memory_client(self, mock_memory_module, mock_memory_client):
        mock_memory_module.get_memory_client.return_value = mock_memory_client
        llm = _get_llm()
        assert llm is mock_memory_client.llm

    def test_raises_when_client_is_none(self, mock_memory_module):
        mock_memory_module.get_memory_client.return_value = None
        with pytest.raises(RuntimeError, match="Memory client is not initialized"):
            _get_llm()


# ---------------------------------------------------------------------------
# get_categories_for_memory
# ---------------------------------------------------------------------------

class TestGetCategoriesForMemory:

    @patch("app.utils.categorization._get_llm")
    def test_returns_lowercase_trimmed_categories(self, mock_get_llm_fn, mock_llm):
        mock_llm.generate_response.return_value = json.dumps(
            {"categories": ["  Work ", " TRAVEL ", "health"]}
        )
        mock_get_llm_fn.return_value = mock_llm

        result = get_categories_for_memory("I have a meeting in Paris next week")
        assert result == ["work", "travel", "health"]

    @patch("app.utils.categorization._get_llm")
    def test_passes_correct_messages_and_format(self, mock_get_llm_fn, mock_llm):
        mock_get_llm_fn.return_value = mock_llm

        get_categories_for_memory("I love playing guitar")

        mock_llm.generate_response.assert_called_once()
        call_kwargs = mock_llm.generate_response.call_args
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
        response_format = call_kwargs.kwargs.get("response_format") or call_kwargs[1].get("response_format")

        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == MEMORY_CATEGORIZATION_PROMPT
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "I love playing guitar"
        assert response_format == {"type": "json_object"}

    @patch("app.utils.categorization._get_llm")
    def test_returns_empty_list_for_uncategorizable_memory(self, mock_get_llm_fn, mock_llm):
        mock_llm.generate_response.return_value = json.dumps({"categories": []})
        mock_get_llm_fn.return_value = mock_llm

        result = get_categories_for_memory("asdfghjkl")
        assert result == []

    @patch("app.utils.categorization._get_llm")
    def test_single_category(self, mock_get_llm_fn, mock_llm):
        mock_llm.generate_response.return_value = json.dumps({"categories": ["Finance"]})
        mock_get_llm_fn.return_value = mock_llm

        result = get_categories_for_memory("My salary is $100k")
        assert result == ["finance"]

    @patch("app.utils.categorization._get_llm")
    def test_raises_on_invalid_json(self, mock_get_llm_fn, mock_llm):
        mock_llm.generate_response.return_value = "not valid json"
        mock_get_llm_fn.return_value = mock_llm

        with pytest.raises(Exception):
            get_categories_for_memory("test memory")

    @patch("app.utils.categorization._get_llm")
    def test_raises_on_missing_categories_key(self, mock_get_llm_fn, mock_llm):
        mock_llm.generate_response.return_value = json.dumps({"wrong_key": ["work"]})
        mock_get_llm_fn.return_value = mock_llm

        with pytest.raises(Exception):
            get_categories_for_memory("test memory")

    @patch("app.utils.categorization._get_llm")
    def test_raises_after_retries_when_llm_fails(self, mock_get_llm_fn, mock_llm):
        """After 3 retry attempts, tenacity wraps the error in RetryError."""
        mock_llm.generate_response.side_effect = ConnectionError("LLM unreachable")
        mock_get_llm_fn.return_value = mock_llm

        with pytest.raises(RetryError):
            get_categories_for_memory("test memory")
        assert mock_llm.generate_response.call_count == 3

    @patch("app.utils.categorization._get_llm")
    def test_works_with_custom_categories(self, mock_get_llm_fn, mock_llm):
        """LLM can return categories not in the predefined list."""
        mock_llm.generate_response.return_value = json.dumps(
            {"categories": ["Cryptocurrency", "Blockchain"]}
        )
        mock_get_llm_fn.return_value = mock_llm

        result = get_categories_for_memory("I bought 2 BTC last month")
        assert result == ["cryptocurrency", "blockchain"]


# ---------------------------------------------------------------------------
# get_categories_for_memories (batch)
# ---------------------------------------------------------------------------

class TestGetCategoriesForMemories:

    @patch("app.utils.categorization._get_llm")
    def test_returns_list_of_lists(self, mock_get_llm_fn, mock_llm):
        mock_llm.generate_response.return_value = json.dumps({
            "results": [
                {"categories": ["Work", "Projects"]},
                {"categories": ["Travel"]},
            ]
        })
        mock_get_llm_fn.return_value = mock_llm

        result = get_categories_for_memories(["meeting tomorrow", "trip to Paris"])
        assert result == [["work", "projects"], ["travel"]]

    @patch("app.utils.categorization._get_llm")
    def test_empty_input_returns_empty(self, mock_get_llm_fn, mock_llm):
        mock_get_llm_fn.return_value = mock_llm
        result = get_categories_for_memories([])
        assert result == []
        mock_llm.generate_response.assert_not_called()

    @patch("app.utils.categorization._get_llm")
    def test_truncates_extra_results(self, mock_get_llm_fn, mock_llm):
        """If the LLM returns more results than memories, only take len(memories)."""
        mock_llm.generate_response.return_value = json.dumps({
            "results": [
                {"categories": ["work"]},
                {"categories": ["travel"]},
                {"categories": ["health"]},
            ]
        })
        mock_get_llm_fn.return_value = mock_llm

        result = get_categories_for_memories(["just one memory"])
        assert len(result) == 1
        assert result == [["work"]]

    @patch("app.utils.categorization._get_llm")
    def test_falls_back_to_empty_on_failure(self, mock_get_llm_fn, mock_llm):
        """On LLM error, returns empty lists instead of raising."""
        mock_llm.generate_response.side_effect = ConnectionError("unreachable")
        mock_get_llm_fn.return_value = mock_llm

        result = get_categories_for_memories(["mem1", "mem2"])
        assert result == [[], []]

    @patch("app.utils.categorization._get_llm")
    def test_falls_back_on_invalid_json(self, mock_get_llm_fn, mock_llm):
        mock_llm.generate_response.return_value = "not json"
        mock_get_llm_fn.return_value = mock_llm

        result = get_categories_for_memories(["mem1"])
        assert result == [[]]

    @patch("app.utils.categorization._get_llm")
    def test_passes_json_object_format(self, mock_get_llm_fn, mock_llm):
        mock_llm.generate_response.return_value = json.dumps({
            "results": [{"categories": ["work"]}]
        })
        mock_get_llm_fn.return_value = mock_llm

        get_categories_for_memories(["test"])

        call_kwargs = mock_llm.generate_response.call_args
        response_format = call_kwargs.kwargs.get("response_format") or call_kwargs[1].get("response_format")
        assert response_format == {"type": "json_object"}

    @patch("app.utils.categorization._get_llm")
    def test_single_memory_batch(self, mock_get_llm_fn, mock_llm):
        mock_llm.generate_response.return_value = json.dumps({
            "results": [{"categories": ["Finance", "Shopping"]}]
        })
        mock_get_llm_fn.return_value = mock_llm

        result = get_categories_for_memories(["bought groceries for $50"])
        assert result == [["finance", "shopping"]]


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TestMemoryCategoriesModel:

    def test_valid_categories(self):
        mc = MemoryCategories(categories=["work", "travel"])
        assert mc.categories == ["work", "travel"]

    def test_empty_categories(self):
        mc = MemoryCategories(categories=[])
        assert mc.categories == []

    def test_rejects_missing_field(self):
        with pytest.raises(Exception):
            MemoryCategories()


class TestBatchMemoryCategoriesModel:

    def test_valid_batch(self):
        bmc = BatchMemoryCategories(results=[
            MemoryCategories(categories=["work"]),
            MemoryCategories(categories=["travel", "health"]),
        ])
        assert len(bmc.results) == 2
        assert bmc.results[0].categories == ["work"]

    def test_empty_results(self):
        bmc = BatchMemoryCategories(results=[])
        assert bmc.results == []

    def test_rejects_missing_results(self):
        with pytest.raises(Exception):
            BatchMemoryCategories()
