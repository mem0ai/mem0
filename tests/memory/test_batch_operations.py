"""Tests for Memory/AsyncMemory batch_add / batch_update / batch_delete.

Regression guard for the ``NameError`` that sank an earlier attempt: these methods
annotate with ``List``, so ``mem0/memory/main.py`` must import it. ``test_list_is_imported``
fails if that import is ever dropped again.
"""

import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory


def _setup_mocks(mocker):
    """Wire up a Memory/AsyncMemory whose add/update/delete are pure mocks."""
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mock_vector_store.return_value.list.return_value = ([], None)
    # AsyncMemory constructs more than Memory, so return the same mock on every call
    mocker.patch("mem0.utils.factory.VectorStoreFactory.create", side_effect=lambda *a, **k: mock_vector_store.return_value)

    mocker.patch("mem0.utils.factory.LlmFactory.create", mocker.MagicMock())
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

    mocker.patch("mem0.memory.main.display_first_run_notice")
    mocker.patch("mem0.memory.main.display_first_run_notice_async")

    memory = Memory()
    memory.db = mocker.MagicMock()
    memory.db.get_last_messages = MagicMock(return_value=[])
    memory.add = MagicMock(return_value={"results": [{"id": "mem-new", "memory": "x"}]})
    memory.update = MagicMock(return_value={"message": "Memory updated successfully!"})
    memory.delete = MagicMock(return_value=None)
    return memory


@pytest.fixture
def memory(mocker):
    return _setup_mocks(mocker)


def _make_async(mocker):
    am = AsyncMemory()

    async def _fake_add(*args, **kwargs):
        return {"results": [{"id": "mem-new", "memory": "x"}]}

    async def _fake_update(*args, **kwargs):
        return {"message": "Memory updated successfully!"}

    async def _fake_delete(*args, **kwargs):
        return None

    am.add = MagicMock(side_effect=_fake_add)
    am.update = MagicMock(side_effect=_fake_update)
    am.delete = MagicMock(side_effect=_fake_delete)
    return am


@pytest.fixture
def amemory(mocker):
    _setup_mocks(mocker)  # patch the factories AsyncMemory() pulls from
    return _make_async(mocker)


def test_list_is_imported():
    """The batch signatures annotate with List - an unimported List bricks the whole SDK."""
    import mem0.memory.main as main_module

    assert main_module.List is not None


class TestBatchAdd:
    def test_returns_one_result_per_item_in_input_order(self, memory):
        memory.add.side_effect = lambda messages, **kw: {"echo": messages}

        results = memory.batch_add(
            [{"messages": "one"}, {"messages": "two"}, {"messages": "three"}], user_id="alice"
        )

        assert [r["status"] for r in results] == ["success"] * 3
        # order must follow the input, not completion order
        assert [r["result"]["echo"] for r in results] == ["one", "two", "three"]
        for result in results:
            assert result["result"]  # payload surfaced

    def test_batch_metadata_merged_under_per_item_metadata(self, memory):
        memory.batch_add(
            [
                {"messages": "a", "metadata": {"topic": "per-item"}},
                {"messages": "b"},
            ],
            user_id="alice",
            metadata={"source": "batch"},
        )

        calls = memory.add.call_args_list
        assert calls[0].kwargs["metadata"] == {"source": "batch", "topic": "per-item"}
        assert calls[1].kwargs["metadata"] == {"source": "batch"}

    def test_default_metadata_not_mutated_across_items(self, memory):
        shared = {"source": "batch"}
        memory.batch_add(
            [{"messages": "a", "metadata": {"topic": "x"}}, {"messages": "b", "metadata": {"topic": "y"}}],
            metadata=shared,
        )
        # the caller's dict must survive the batch untouched
        assert shared == {"source": "batch"}

    def test_forwards_add_kwargs(self, memory):
        memory.batch_add(
            [{"messages": "a"}],
            user_id="u",
            agent_id="ag",
            run_id="r",
            infer=False,
            memory_type="procedural_memory",
            prompt="custom",
        )
        kwargs = memory.add.call_args.kwargs
        assert kwargs["user_id"] == "u"
        assert kwargs["agent_id"] == "ag"
        assert kwargs["run_id"] == "r"
        assert kwargs["infer"] is False
        assert kwargs["memory_type"] == "procedural_memory"
        assert kwargs["prompt"] == "custom"

    def test_single_failure_does_not_kill_the_batch(self, memory):
        def flaky(messages, **kw):
            if messages == "boom":
                raise RuntimeError("llm unavailable")
            return {"echo": messages}

        memory.add.side_effect = flaky

        results = memory.batch_add([{"messages": "ok"}, {"messages": "boom"}, {"messages": "ok2"}])

        assert [r["status"] for r in results] == ["success", "error", "success"]
        assert "llm unavailable" in results[1]["error"]
        assert results[0]["result"]["echo"] == "ok"
        assert results[2]["result"]["echo"] == "ok2"

    def test_rejects_non_list(self, memory):
        with pytest.raises(TypeError, match="batch_data must be a list"):
            memory.batch_add({"messages": "not-a-list"})
        assert memory.add.call_count == 0

    def test_rejects_empty_list(self, memory):
        with pytest.raises(ValueError, match="at least one item"):
            memory.batch_add([])
        assert memory.add.call_count == 0

    def test_runs_items_concurrently(self, memory):
        """Barrier of N proves all items are in flight at once.

        A serial loop would block on the first call until the barrier times out and
        raise BrokenBarrierError, so a clean pass is real evidence of concurrency.
        """
        items = [{"messages": f"m{i}"} for i in range(4)]
        barrier = threading.Barrier(len(items), timeout=5)

        def concur(messages, **kw):
            barrier.wait()
            return {"echo": messages}

        memory.add.side_effect = concur

        results = memory.batch_add(items)

        assert all(r["status"] == "success" for r in results)


class TestBatchUpdate:
    def test_forwards_update_kwargs(self, memory):
        memory.batch_update([{"memory_id": "m1", "text": "new", "metadata": {"lang": "en"}}])

        memory.update.assert_called_once()
        args, kwargs = memory.update.call_args
        assert args[0] == "m1"
        assert kwargs["text"] == "new"
        assert kwargs["metadata"] == {"lang": "en"}

    def test_preserves_input_order(self, memory):
        memory.update.side_effect = lambda memory_id, **kw: {"id": memory_id}

        results = memory.batch_update(
            [{"memory_id": "a", "text": "x"}, {"memory_id": "b", "text": "y"}, {"memory_id": "c", "text": "z"}]
        )

        assert [r["result"]["id"] for r in results] == ["a", "b", "c"]

    def test_failure_isolated_and_labelled(self, memory):
        def flaky(memory_id, **kw):
            if memory_id == "bad":
                raise ValueError("Memory with id bad not found.")
            return {"message": "Memory updated successfully!"}

        memory.update.side_effect = flaky

        results = memory.batch_update(
            [{"memory_id": "ok", "text": "x"}, {"memory_id": "bad", "text": "y"}]
        )

        assert results[0]["status"] == "success"
        assert results[1]["status"] == "error"
        assert results[1]["memory_id"] == "bad"
        assert "not found" in results[1]["error"]

    def test_duplicate_ids_stay_aligned(self, memory):
        memory.update.return_value = {"message": "Memory updated successfully!"}

        results = memory.batch_update(
            [{"memory_id": "same", "text": "a"}, {"memory_id": "same", "text": "b"}]
        )

        assert [r["status"] for r in results] == ["success", "success"]
        assert memory.update.call_count == 2

    def test_rejects_non_list_and_empty(self, memory):
        with pytest.raises(TypeError, match="updates must be a list"):
            memory.batch_update("nope")
        with pytest.raises(ValueError, match="at least one item"):
            memory.batch_update([])
        assert memory.update.call_count == 0


class TestBatchDelete:
    def test_reports_every_id(self, memory):
        result = memory.batch_delete(["m1", "m2", "m3"])

        assert result["successful"] == ["m1", "m2", "m3"]
        assert result["failed"] == []
        assert result["errors"] == []
        assert result["summary"] == "Deleted 3/3 memories"
        assert memory.delete.call_count == 3

    def test_failure_isolated_and_summary_accurate(self, memory):
        def flaky(memory_id):
            if memory_id == "m2":
                raise ValueError("Memory with id m2 not found.")

        memory.delete.side_effect = flaky

        result = memory.batch_delete(["m1", "m2", "m3"])

        assert result["successful"] == ["m1", "m3"]
        assert result["failed"] == ["m2"]
        assert "not found" in result["errors"][0]["error"]
        assert result["summary"] == "Deleted 2/3 memories"

    def test_rejects_non_list_and_empty(self, memory):
        with pytest.raises(TypeError, match="memory_ids must be a list"):
            memory.batch_delete("m1")
        with pytest.raises(ValueError, match="at least one id"):
            memory.batch_delete([])
        assert memory.delete.call_count == 0


class TestConcurrencyKnob:
    """max_workers/max_concurrency exists because an embedded vector store
    (in-process Qdrant) is not thread-safe - serialising fixes 'cannot commit
    - no transaction is active'."""

    def test_max_workers_zero_is_rejected(self, memory):
        with pytest.raises(ValueError, match="max_workers must be at least 1"):
            memory.batch_add([{"messages": "a"}], max_workers=0)

    def test_max_workers_one_runs_sequentially(self, memory):
        """With max_workers=1 only one item may be in flight at a time."""
        inflight = 0
        lock = threading.Lock()

        def serial(messages, **kw):
            nonlocal inflight
            with lock:
                inflight += 1
                concurrent = inflight > 1
            try:
                if concurrent:
                    raise AssertionError("concurrent execution observed with max_workers=1")
                return {"echo": messages}
            finally:
                with lock:
                    inflight -= 1

        memory.add.side_effect = serial
        results = memory.batch_add([{"messages": f"m{i}"} for i in range(4)], max_workers=1)

        assert all(r["status"] == "success" for r in results)
        assert [r["result"]["echo"] for r in results] == ["m0", "m1", "m2", "m3"]

    def test_max_workers_reaches_all_items(self, memory):
        memory.batch_add([{"messages": f"m{i}"} for i in range(5)], max_workers=2)
        assert memory.add.call_count == 5

    def test_update_and_delete_accept_max_workers(self, memory):
        memory.batch_update([{"memory_id": f"m{i}", "text": "x"} for i in range(3)], max_workers=1)
        memory.batch_delete([f"m{i}" for i in range(3)], max_workers=1)
        assert memory.update.call_count == 3
        assert memory.delete.call_count == 3

    @pytest.mark.asyncio
    async def test_async_max_concurrency_rejected_below_one(self, amemory):
        with pytest.raises(ValueError, match="max_concurrency must be at least 1"):
            await amemory.batch_add([{"messages": "a"}], max_concurrency=0)

    @pytest.mark.asyncio
    async def test_async_max_concurrency_reaches_all_items(self, amemory):
        results = await amemory.batch_add(
            [{"messages": f"m{i}"} for i in range(4)], max_concurrency=2
        )
        assert all(r["status"] == "success" for r in results)
        assert amemory.add.call_count == 4

    @pytest.mark.asyncio
    async def test_async_update_delete_accept_max_concurrency(self, amemory):
        await amemory.batch_update([{"memory_id": f"m{i}", "text": "x"} for i in range(3)], max_concurrency=1)
        await amemory.batch_delete([f"m{i}" for i in range(3)], max_concurrency=1)
        assert amemory.update.call_count == 3
        assert amemory.delete.call_count == 3


class TestAsyncBatch:
    @pytest.mark.asyncio
    async def test_batch_add_order_and_isolation(self, amemory):
        async def flaky(messages, **kw):
            if messages == "boom":
                raise RuntimeError("nope")
            return {"echo": messages}

        amemory.add = MagicMock(side_effect=flaky)

        results = await amemory.batch_add([{"messages": "a"}, {"messages": "boom"}, {"messages": "c"}])

        assert [r["status"] for r in results] == ["success", "error", "success"]
        assert [r["result"]["echo"] for r in results if r["status"] == "success"] == ["a", "c"]

    @pytest.mark.asyncio
    async def test_batch_add_runs_concurrently(self, amemory):
        """All items must be in flight together - a serial await would time out."""
        items = [{"messages": f"m{i}"} for i in range(3)]
        barrier = asyncio.Barrier(len(items)) if hasattr(asyncio, "Barrier") else None

        if barrier is None:  # Python < 3.11 has no asyncio.Barrier
            pendings = []

            async def fake_add(messages, **kw):
                pendings.append(messages)
                if len(pendings) < len(items):
                    await asyncio.sleep(0.01)
                return {"echo": messages}

            amemory.add = MagicMock(side_effect=fake_add)
            results = await amemory.batch_add(items, )
            assert len(pendings) == len(items)
        else:
            async def fake_add(messages, **kw):
                await barrier.wait()
                return {"echo": messages}

            amemory.add = MagicMock(side_effect=fake_add)
            results = await amemory.batch_add(items)
            assert all(r["status"] == "success" for r in results)

    @pytest.mark.asyncio
    async def test_batch_update_order_and_forwarding(self, amemory):
        async def fake_update(memory_id, **kw):
            return {"id": memory_id, "text": kw.get("text")}

        amemory.update = MagicMock(side_effect=fake_update)

        results = await amemory.batch_update(
            [{"memory_id": "a", "text": "1"}, {"memory_id": "b", "text": "2"}]
        )

        assert [r["result"]["id"] for r in results] == ["a", "b"]
        assert [r["result"]["text"] for r in results] == ["1", "2"]

    @pytest.mark.asyncio
    async def test_batch_delete_summary(self, amemory):
        async def fake_delete(memory_id, **kw):
            if memory_id == "b":
                raise ValueError("not found")
            return None

        amemory.delete = MagicMock(side_effect=fake_delete)

        result = await amemory.batch_delete(["a", "b", "c"])

        assert result["successful"] == ["a", "c"]
        assert result["failed"] == ["b"]
        assert result["summary"] == "Deleted 2/3 memories"

    @pytest.mark.asyncio
    async def test_batch_add_validates(self, amemory):
        with pytest.raises(TypeError):
            await amemory.batch_add("nope")
        with pytest.raises(ValueError):
            await amemory.batch_add([])
