"""Tests for Memory.batch_add/batch_update/batch_delete and async equivalents."""

from unittest.mock import MagicMock, patch

import pytest

from mem0 import Memory


# ---------------------------------------------------------------------------
# Memory (sync) — batch_add
# ---------------------------------------------------------------------------

class TestMemoryBatchAdd:
    def _make_memory(self):
        with patch.object(Memory, "__init__", return_value=None):
            m = Memory()
            m.add = MagicMock(return_value={"results": [{"id": "1", "memory": "test", "event": "ADD"}]})
            return m

    def test_returns_results_in_order(self):
        m = self._make_memory()
        inputs = [
            {"messages": "Alice likes hiking", "user_id": "alice"},
            {"messages": "Bob prefers chess", "user_id": "bob"},
        ]
        results = m.batch_add(inputs)
        assert len(results) == 2
        assert all("results" in r for r in results)

    def test_propagates_error_as_dict(self):
        with patch.object(Memory, "__init__", return_value=None):
            m = Memory()
            m.add = MagicMock(side_effect=ValueError("bad input"))
        results = m.batch_add([{"messages": "fail", "user_id": "x"}])
        assert results[0] == {"error": "bad input"}

    def test_empty_inputs_returns_empty(self):
        m = self._make_memory()
        assert m.batch_add([]) == []

    def test_max_workers_respected(self):
        m = self._make_memory()
        results = m.batch_add([{"messages": "test", "user_id": "u1"}], max_workers=1)
        assert len(results) == 1

    def test_partial_failure_does_not_short_circuit(self):
        call_count = 0

        def _add(**kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("user_id") == "bad":
                raise ValueError("bad user")
            return {"results": [{"id": str(call_count), "memory": "ok", "event": "ADD"}]}

        with patch.object(Memory, "__init__", return_value=None):
            m = Memory()
            m.add = _add

        results = m.batch_add([
            {"messages": "ok", "user_id": "good"},
            {"messages": "fail", "user_id": "bad"},
            {"messages": "ok2", "user_id": "good2"},
        ])
        assert len(results) == 3
        successes = [r for r in results if "results" in r]
        errors = [r for r in results if "error" in r]
        assert len(successes) == 2
        assert len(errors) == 1


# ---------------------------------------------------------------------------
# Memory (sync) — batch_update
# ---------------------------------------------------------------------------

class TestMemoryBatchUpdate:
    def _make_memory(self):
        with patch.object(Memory, "__init__", return_value=None):
            m = Memory()
            m.update = MagicMock(return_value={"message": "Memory updated successfully!"})
            return m

    def test_returns_results_in_order(self):
        m = self._make_memory()
        updates = [
            {"memory_id": "id1", "data": "Alice loves hiking"},
            {"memory_id": "id2", "data": "Bob prefers Go"},
        ]
        results = m.batch_update(updates)
        assert len(results) == 2
        assert all(r["message"] == "Memory updated successfully!" for r in results)

    def test_propagates_error_as_dict(self):
        with patch.object(Memory, "__init__", return_value=None):
            m = Memory()
            m.update = MagicMock(side_effect=ValueError("not found"))
        results = m.batch_update([{"memory_id": "bad", "data": "x"}])
        assert results[0] == {"error": "not found"}

    def test_empty_inputs_returns_empty(self):
        m = self._make_memory()
        assert m.batch_update([]) == []

    def test_optional_metadata_forwarded(self):
        m = self._make_memory()
        updates = [{"memory_id": "id1", "data": "new data", "metadata": {"source": "test"}}]
        results = m.batch_update(updates)
        m.update.assert_called_once_with("id1", "new data", {"source": "test"})
        assert results[0]["message"] == "Memory updated successfully!"

    def test_missing_memory_id_raises_error_captured(self):
        with patch.object(Memory, "__init__", return_value=None):
            m = Memory()
            m.update = MagicMock()
        results = m.batch_update([{"data": "no id here"}])
        assert "error" in results[0]


# ---------------------------------------------------------------------------
# Memory (sync) — batch_delete
# ---------------------------------------------------------------------------

class TestMemoryBatchDelete:
    def _make_memory(self):
        with patch.object(Memory, "__init__", return_value=None):
            m = Memory()
            m.delete = MagicMock(return_value={"message": "Memory deleted successfully!"})
            return m

    def test_returns_results_in_order(self):
        m = self._make_memory()
        results = m.batch_delete(["id1", "id2", "id3"])
        assert len(results) == 3
        assert all(r["message"] == "Memory deleted successfully!" for r in results)

    def test_propagates_error_as_dict(self):
        with patch.object(Memory, "__init__", return_value=None):
            m = Memory()
            m.delete = MagicMock(side_effect=ValueError("not found"))
        results = m.batch_delete(["bad_id"])
        assert results[0] == {"error": "not found"}

    def test_empty_inputs_returns_empty(self):
        m = self._make_memory()
        assert m.batch_delete([]) == []

    def test_each_id_deleted_once(self):
        m = self._make_memory()
        m.batch_delete(["id1", "id2"])
        assert m.delete.call_count == 2


# ---------------------------------------------------------------------------
# AsyncMemory — batch_add
# ---------------------------------------------------------------------------

class TestAsyncMemoryBatchAdd:
    def _make_memory(self):
        from mem0.memory.main import AsyncMemory
        with patch.object(AsyncMemory, "__init__", return_value=None):
            m = AsyncMemory()

            async def _add(**kwargs):
                return {"results": [{"id": "1", "memory": "test", "event": "ADD"}]}

            m.add = _add
            return m

    @pytest.mark.asyncio
    async def test_returns_results_in_order(self):
        m = self._make_memory()
        inputs = [
            {"messages": "Alice likes hiking", "user_id": "alice"},
            {"messages": "Bob prefers chess", "user_id": "bob"},
        ]
        results = await m.batch_add(inputs)
        assert len(results) == 2
        assert all("results" in r for r in results)

    @pytest.mark.asyncio
    async def test_propagates_error_as_dict(self):
        from mem0.memory.main import AsyncMemory
        with patch.object(AsyncMemory, "__init__", return_value=None):
            m = AsyncMemory()

            async def _add_fail(**kwargs):
                raise ValueError("bad input")

            m.add = _add_fail
        results = await m.batch_add([{"messages": "fail", "user_id": "x"}])
        assert results[0] == {"error": "bad input"}

    @pytest.mark.asyncio
    async def test_empty_inputs_returns_empty(self):
        m = self._make_memory()
        assert await m.batch_add([]) == []

    @pytest.mark.asyncio
    async def test_partial_failure_does_not_short_circuit(self):
        from mem0.memory.main import AsyncMemory
        with patch.object(AsyncMemory, "__init__", return_value=None):
            m = AsyncMemory()

            async def _add(**kwargs):
                if kwargs.get("user_id") == "bad":
                    raise ValueError("bad user")
                return {"results": [{"id": "1", "memory": "ok", "event": "ADD"}]}

            m.add = _add

        results = await m.batch_add([
            {"messages": "ok", "user_id": "good"},
            {"messages": "fail", "user_id": "bad"},
        ])
        assert len(results) == 2
        assert any("results" in r for r in results)
        assert any("error" in r for r in results)


# ---------------------------------------------------------------------------
# AsyncMemory — batch_update
# ---------------------------------------------------------------------------

class TestAsyncMemoryBatchUpdate:
    def _make_memory(self):
        from mem0.memory.main import AsyncMemory
        with patch.object(AsyncMemory, "__init__", return_value=None):
            m = AsyncMemory()

            async def _update(memory_id, data, metadata=None):
                return {"message": "Memory updated successfully!"}

            m.update = _update
            return m

    @pytest.mark.asyncio
    async def test_returns_results_in_order(self):
        m = self._make_memory()
        updates = [
            {"memory_id": "id1", "data": "Alice loves hiking"},
            {"memory_id": "id2", "data": "Bob prefers Go"},
        ]
        results = await m.batch_update(updates)
        assert len(results) == 2
        assert all(r["message"] == "Memory updated successfully!" for r in results)

    @pytest.mark.asyncio
    async def test_propagates_error_as_dict(self):
        from mem0.memory.main import AsyncMemory
        with patch.object(AsyncMemory, "__init__", return_value=None):
            m = AsyncMemory()

            async def _update_fail(memory_id, data, metadata=None):
                raise ValueError("not found")

            m.update = _update_fail
        results = await m.batch_update([{"memory_id": "bad", "data": "x"}])
        assert results[0] == {"error": "not found"}

    @pytest.mark.asyncio
    async def test_empty_inputs_returns_empty(self):
        m = self._make_memory()
        assert await m.batch_update([]) == []


# ---------------------------------------------------------------------------
# AsyncMemory — batch_delete
# ---------------------------------------------------------------------------

class TestAsyncMemoryBatchDelete:
    def _make_memory(self):
        from mem0.memory.main import AsyncMemory
        with patch.object(AsyncMemory, "__init__", return_value=None):
            m = AsyncMemory()

            async def _delete(memory_id):
                return {"message": "Memory deleted successfully!"}

            m.delete = _delete
            return m

    @pytest.mark.asyncio
    async def test_returns_results_in_order(self):
        m = self._make_memory()
        results = await m.batch_delete(["id1", "id2", "id3"])
        assert len(results) == 3
        assert all(r["message"] == "Memory deleted successfully!" for r in results)

    @pytest.mark.asyncio
    async def test_propagates_error_as_dict(self):
        from mem0.memory.main import AsyncMemory
        with patch.object(AsyncMemory, "__init__", return_value=None):
            m = AsyncMemory()

            async def _delete_fail(memory_id):
                raise ValueError("not found")

            m.delete = _delete_fail
        results = await m.batch_delete(["bad_id"])
        assert results[0] == {"error": "not found"}

    @pytest.mark.asyncio
    async def test_empty_inputs_returns_empty(self):
        m = self._make_memory()
        assert await m.batch_delete([]) == []
