"""Tests for openmemory/api/app/utils/categorization.py."""

import os

# Set dummy key before any imports that initialize the OpenAI client.
os.environ.setdefault("OPENAI_API_KEY", "dummy")

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# get_categories_for_memories  (batch)
# ---------------------------------------------------------------------------


class TestBatchCategorization:
    def test_empty_input_returns_empty_list(self):
        from app.utils.categorization import get_categories_for_memories

        assert get_categories_for_memories([]) == []

    def test_returns_correct_category_list(self):
        from app.utils.categorization import (
            BatchMemoryCategories,
            MemoryCategories,
            get_categories_for_memories,
        )

        mock_parsed = BatchMemoryCategories(
            results=[
                MemoryCategories(categories=["health", "food"]),
                MemoryCategories(categories=["tech"]),
            ]
        )
        mock_completion = MagicMock()
        mock_completion.choices[0].message.parsed = mock_parsed

        with patch("app.utils.categorization.openai_client") as mock_client:
            mock_client.beta.chat.completions.parse.return_value = mock_completion
            result = get_categories_for_memories(["I eat apples", "I code Python"])

        assert result == [["health", "food"], ["tech"]]

    def test_falls_back_to_empty_categories_on_openai_failure(self):
        """When OpenAI raises, the function returns [[], []] for each memory."""
        from app.utils.categorization import get_categories_for_memories

        with patch("app.utils.categorization.openai_client") as mock_client:
            mock_client.beta.chat.completions.parse.side_effect = Exception("API down")
            result = get_categories_for_memories(["mem1", "mem2"])

        assert result == [[], []]

    def test_response_count_mismatch_handled_gracefully(self):
        """If the response has fewer items than memories, extras are silently omitted."""
        from app.utils.categorization import (
            BatchMemoryCategories,
            MemoryCategories,
            get_categories_for_memories,
        )

        # 1 result for 3 memories
        mock_parsed = BatchMemoryCategories(
            results=[MemoryCategories(categories=["health"])]
        )
        mock_completion = MagicMock()
        mock_completion.choices[0].message.parsed = mock_parsed

        with patch("app.utils.categorization.openai_client") as mock_client:
            mock_client.beta.chat.completions.parse.return_value = mock_completion
            result = get_categories_for_memories(["mem1", "mem2", "mem3"])

        assert result == [["health"]]

    def test_duplicate_content_memories_get_independent_categories(self):
        """Two memories with identical content each get their own category list."""
        from app.utils.categorization import (
            BatchMemoryCategories,
            MemoryCategories,
            get_categories_for_memories,
        )

        mock_parsed = BatchMemoryCategories(
            results=[
                MemoryCategories(categories=["health"]),
                MemoryCategories(categories=["fitness"]),
            ]
        )
        mock_completion = MagicMock()
        mock_completion.choices[0].message.parsed = mock_parsed

        with patch("app.utils.categorization.openai_client") as mock_client:
            mock_client.beta.chat.completions.parse.return_value = mock_completion
            result = get_categories_for_memories(["same content", "same content"])

        # Both entries are preserved independently via index-based list
        assert len(result) == 2
        assert result[0] == ["health"]
        assert result[1] == ["fitness"]


# ---------------------------------------------------------------------------
# get_categories_for_memory  (single)
# ---------------------------------------------------------------------------


class TestSingleCategorization:
    def test_returns_list_of_categories(self):
        from app.utils.categorization import MemoryCategories, get_categories_for_memory

        mock_parsed = MemoryCategories(categories=["fitness", "health"])
        mock_completion = MagicMock()
        mock_completion.choices[0].message.parsed = mock_parsed

        with patch("app.utils.categorization.openai_client") as mock_client:
            mock_client.beta.chat.completions.parse.return_value = mock_completion
            result = get_categories_for_memory("I run every morning")

        assert result == ["fitness", "health"]

    def test_categories_are_stripped_and_lowercased(self):
        from app.utils.categorization import MemoryCategories, get_categories_for_memory

        mock_parsed = MemoryCategories(categories=["  TECH  ", "Science"])
        mock_completion = MagicMock()
        mock_completion.choices[0].message.parsed = mock_parsed

        with patch("app.utils.categorization.openai_client") as mock_client:
            mock_client.beta.chat.completions.parse.return_value = mock_completion
            result = get_categories_for_memory("Some memory")

        assert result == ["tech", "science"]
