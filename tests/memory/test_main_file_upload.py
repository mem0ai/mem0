"""Tests for file path detection in mem0.memory.main.Memory.add()."""

import os
import tempfile
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_RESULT = {"id": "aaaaaaaa-0000-0000-0000-000000000001", "memory": "Test content.", "event": "ADD"}


def _make_memory():
    """Return a Memory instance that bypasses __init__."""
    from mem0.memory.main import Memory

    mem = Memory.__new__(Memory)
    mem.config = MagicMock()
    mem.config.llm.config.get.return_value = False  # disable vision
    mem.enable_graph = False
    return mem


def _stack_internals(stack, mem, vector_results=None):
    """Register patches for the internal methods that touch vector / LLM."""
    if vector_results is None:
        vector_results = [FAKE_RESULT]

    mock_vs = stack.enter_context(
        patch.object(mem, "_add_to_vector_store", return_value=vector_results)
    )
    stack.enter_context(patch.object(mem, "_add_to_graph", return_value=[]))
    stack.enter_context(
        patch(
            "mem0.memory.main.parse_vision_messages",
            side_effect=lambda msgs, *a, **kw: msgs,
        )
    )
    stack.enter_context(
        patch(
            "mem0.memory.main._build_filters_and_metadata",
            return_value=({"user_id": "u1"}, {"user_id": "u1"}),
        )
    )
    return mock_vs


def _write_tmp(suffix: str, content: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=suffix, mode="w", delete=False) as f:
        f.write(content)
        return f.name


# ---------------------------------------------------------------------------
# Sync Memory tests
# ---------------------------------------------------------------------------


class TestMemoryAddFileDetectionSync:
    def test_txt_file_triggers_extraction(self):
        """Passing a .txt path to add() triggers extraction and returns results."""
        tmp = _write_tmp(".txt", "Single sentence about Python.")
        try:
            mem = _make_memory()
            with ExitStack() as stack:
                mock_vs = _stack_internals(stack, mem)
                result = mem.add(tmp, user_id="u1")

            assert "results" in result
            assert len(result["results"]) >= 1
            assert mock_vs.call_count >= 1
        finally:
            os.unlink(tmp)

    def test_each_chunk_adds_separately(self):
        """Multiple chunks each produce a separate recursive add() call."""
        # ~5 000 chars → two chunks at the default 4 000-char limit
        long_text = ("Word " * 50 + ".\n\n") * 25
        tmp = _write_tmp(".txt", long_text)

        try:
            mem = _make_memory()
            call_count = {"n": 0}

            def fake_vs(messages, metadata, filters, infer):
                call_count["n"] += 1
                return [
                    {
                        "id": f"id{call_count['n']}",
                        "memory": f"chunk{call_count['n']}",
                        "event": "ADD",
                    }
                ]

            with ExitStack() as stack:
                stack.enter_context(
                    patch(
                        "mem0.memory.main._build_filters_and_metadata",
                        return_value=({"user_id": "u1"}, {"user_id": "u1"}),
                    )
                )
                stack.enter_context(
                    patch.object(mem, "_add_to_vector_store", side_effect=fake_vs)
                )
                stack.enter_context(patch.object(mem, "_add_to_graph", return_value=[]))
                stack.enter_context(
                    patch(
                        "mem0.memory.main.parse_vision_messages",
                        side_effect=lambda msgs, *a, **kw: msgs,
                    )
                )
                result = mem.add(tmp, user_id="u1")

            # All chunk results merged into a single list
            assert len(result["results"]) == call_count["n"]
            assert call_count["n"] >= 2
        finally:
            os.unlink(tmp)

    def test_unsupported_extension_falls_through_to_plain_text(self):
        """A .csv file that exists on disk is NOT treated as a file — processed as text."""
        tmp = _write_tmp(".csv", "a,b,c")
        try:
            mem = _make_memory()
            with ExitStack() as stack:
                mock_vs = _stack_internals(stack, mem)
                mem.add(tmp, user_id="u1")

            # Plain-text path → exactly one call to the vector store
            assert mock_vs.call_count == 1
            # The messages passed to the vector store contain the file path string
            messages_arg = mock_vs.call_args[0][0]
            assert any(tmp in msg.get("content", "") for msg in messages_arg if isinstance(msg, dict))
        finally:
            os.unlink(tmp)

    def test_nonexistent_path_string_is_plain_text(self):
        """A string that looks like a path but does not exist is treated as plain text."""
        mem = _make_memory()
        fake_path = "/nonexistent/path/file.txt"

        with ExitStack() as stack:
            mock_vs = _stack_internals(stack, mem)
            result = mem.add(fake_path, user_id="u1")

        assert mock_vs.call_count == 1
        assert "results" in result

    def test_results_merged_across_chunks(self):
        """Return value is a flat dict with all chunk results merged under 'results'."""
        chunks = ["Chunk one.", "Chunk two.", "Chunk three."]
        tmp = _write_tmp(".txt", "\n\n".join(chunks))

        try:
            mem = _make_memory()
            chunk_idx = {"i": 0}

            def fake_vs(messages, metadata, filters, infer):
                chunk_idx["i"] += 1
                return [{"id": f"id{chunk_idx['i']}", "memory": f"m{chunk_idx['i']}", "event": "ADD"}]

            with ExitStack() as stack:
                stack.enter_context(
                    patch(
                        "mem0.memory.main._build_filters_and_metadata",
                        return_value=({"user_id": "u1"}, {"user_id": "u1"}),
                    )
                )
                stack.enter_context(
                    patch.object(mem, "_add_to_vector_store", side_effect=fake_vs)
                )
                stack.enter_context(patch.object(mem, "_add_to_graph", return_value=[]))
                stack.enter_context(
                    patch(
                        "mem0.memory.main.parse_vision_messages",
                        side_effect=lambda msgs, *a, **kw: msgs,
                    )
                )
                result = mem.add(tmp, user_id="u1")

            assert isinstance(result, dict)
            assert "results" in result
            assert len(result["results"]) == chunk_idx["i"]
        finally:
            os.unlink(tmp)


# ---------------------------------------------------------------------------
# Async Memory test
# ---------------------------------------------------------------------------


class TestMemoryAddFileDetectionAsync:
    @pytest.mark.asyncio
    async def test_async_add_detects_file_path(self):
        """AsyncMemory.add() calls extract_text_from_file for .txt paths."""
        try:
            from mem0.memory.main import AsyncMemory
        except ImportError:
            pytest.skip("AsyncMemory not available in this version")

        tmp = _write_tmp(".txt", "Async sentence.")
        try:
            amem = AsyncMemory.__new__(AsyncMemory)
            amem.config = MagicMock()
            amem.config.llm.config.get.return_value = False
            amem.enable_graph = False

            original_add = AsyncMemory.add

            async def intercepting_add(self_inner, messages, **kwargs):
                # First call is the file path — let it run through real logic.
                # Recursive calls for individual chunks return a mock result.
                if isinstance(messages, str) and os.path.isfile(messages):
                    return await original_add(self_inner, messages, **kwargs)
                return {"results": [FAKE_RESULT]}

            with patch(
                "mem0.memory.main._build_filters_and_metadata",
                return_value=({"user_id": "u1"}, {"user_id": "u1"}),
            ):
                with patch(
                    "mem0.memory.file_utils.extract_text_from_file",
                    return_value="Async sentence.",
                ) as mock_extract:
                    with patch(
                        "mem0.memory.file_utils.chunk_text",
                        return_value=["Async sentence."],
                    ):
                        with patch.object(AsyncMemory, "add", intercepting_add):
                            result = await amem.add(tmp, user_id="u1")

            mock_extract.assert_called_once_with(tmp)
            assert "results" in result
            assert len(result["results"]) >= 1
        finally:
            os.unlink(tmp)
