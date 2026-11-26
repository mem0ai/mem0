"""Cancellation at provider boundaries with real disk Qdrant and SQLite.

Only model SDK responses and provider response timing are controlled. No Mem0
method is mocked; worker Futures finish before stores are closed or reopened.
"""

import asyncio
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from openai.resources.chat.completions import Completions
from openai.resources.embeddings import Embeddings

from mem0 import AsyncMemory


class Workers(ThreadPoolExecutor):
    def __init__(self):
        super().__init__(max_workers=4)
        self.jobs = []

    def submit(self, fn, /, *args, **kwargs):
        future = super().submit(fn, *args, **kwargs)
        self.jobs.append(future)
        return future

    async def drain(self):
        await asyncio.wait_for(asyncio.gather(*(asyncio.shield(asyncio.wrap_future(f)) for f in tuple(self.jobs))), 15)


@pytest.fixture
def memory_config(tmp_path, monkeypatch):
    monkeypatch.setenv("MEM0_TELEMETRY", "false")

    def embed(_sdk, **kwargs):
        return SimpleNamespace(
            data=[SimpleNamespace(index=i, embedding=[1.0] + [0.0] * 7) for i, _ in enumerate(kwargs["input"])]
        )

    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=json.dumps({"memory": [{"text": "new fact"}, {"text": "second fact"}]}))
            )
        ]
    )
    monkeypatch.setattr(Embeddings, "create", embed)
    monkeypatch.setattr(Completions, "create", lambda *a, **kw: response)
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "cancel",
                "embedding_model_dims": 8,
                "path": str(tmp_path / "qdrant"),
                "on_disk": True,
            },
        },
        "embedder": {"provider": "openai", "config": {"api_key": "test-only", "embedding_dims": 8}},
        "llm": {"provider": "openai", "config": {"api_key": "test-only"}},
        "history_db_path": str(tmp_path / "history.sqlite"),
    }


def close(memory):
    memory.db.close()
    memory.vector_store.client.close()
    memory.embedding_model.client.close()
    memory.llm.client.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["raw_add", "inferred_add", "update", "delete"])
@pytest.mark.parametrize("cancel", [False, True], ids=["control", "cancelled"])
async def test_started_mutation_drains_history(memory_config, monkeypatch, operation, cancel):
    memory = AsyncMemory.from_config(memory_config)
    loop = asyncio.get_running_loop()
    previous = loop._default_executor
    workers = Workers()
    loop.set_default_executor(workers)
    committed, release = threading.Event(), threading.Event()
    task = None
    try:
        mid = None
        if operation in ("update", "delete"):
            mid = (await memory.add("old fact", user_id="test", infer=False))["results"][0]["id"]
        method = "delete" if operation == "delete" else "upsert"
        original = getattr(memory.vector_store.client, method)

        def gated(*args, **kwargs):
            result = original(*args, **kwargs)
            committed.set()
            if not release.wait(10):
                raise TimeoutError("SDK response gate exceeded")
            return result

        monkeypatch.setattr(memory.vector_store.client, method, gated)
        if operation == "raw_add":
            work = memory.add(
                [
                    {"role": "user", "content": "new fact"},
                    {"role": "user", "content": "second fact"},
                ],
                user_id="test",
                infer=False,
            )
        elif operation == "inferred_add":
            work = memory.add("input", user_id="test")
        elif operation == "update":
            work = memory.update(mid, text="new fact")
        else:
            work = memory.delete(mid)
        task = asyncio.create_task(work)
        assert await asyncio.to_thread(committed.wait, 5)
        if cancel:
            for _ in range(2):
                task.cancel()
                await asyncio.sleep(0)
                await asyncio.sleep(0)
                assert not task.done(), "caller must not exit while its store worker is running"
        release.set()
        if cancel:
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await task
        await workers.drain()
        close(memory)

        memory = AsyncMemory.from_config(memory_config)
        if mid is None:
            rows = (await memory.get_all(filters={"user_id": "test"}))["results"]
            assert len(rows) == (1 if operation == "raw_add" and cancel else 2)
            for row in rows:
                assert [h["event"] for h in await memory.history(row["id"])] == ["ADD"]
            mid = rows[0]["id"]
            expected = ["ADD"]
        elif operation == "update":
            assert (await memory.get(mid))["memory"] == "new fact"
            expected = ["ADD", "UPDATE"]
        else:
            assert await memory.get(mid) is None
            expected = ["ADD", "DELETE"]
        assert [h["event"] for h in await memory.history(mid)] == expected
    finally:
        release.set()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        await workers.drain()
        close(memory)
        if previous is not None:
            loop.set_default_executor(previous)
        workers.shutdown(wait=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("infer", [False, True])
async def test_cancel_during_embedding_does_not_write(memory_config, monkeypatch, infer):
    memory = AsyncMemory.from_config(memory_config)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = Embeddings.create
    task = None

    def gated(*args, **kwargs):
        entered.set()
        try:
            if not release.wait(10):
                raise TimeoutError("embedding gate exceeded")
            return original(*args, **kwargs)
        finally:
            finished.set()

    monkeypatch.setattr(Embeddings, "create", gated)
    try:
        task = asyncio.create_task(memory.add("fact", user_id="test", infer=infer))
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        assert await asyncio.to_thread(finished.wait, 5)
        assert (await memory.get_all(filters={"user_id": "test"}))["results"] == []
    finally:
        release.set()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        # Explicitly wait until SDK use ends before closing its HTTP client.
        if entered.is_set():
            assert await asyncio.to_thread(finished.wait, 5)
        close(memory)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
@pytest.mark.parametrize("failure", ["provider", "history"])
async def test_failure_remains_observable(memory_config, monkeypatch, caplog, cancel, failure):
    memory = AsyncMemory.from_config(memory_config)
    entered, release = threading.Event(), threading.Event()
    task = None
    original = memory.vector_store.client.upsert

    def gated(*args, **kwargs):
        entered.set()
        if not release.wait(10):
            raise TimeoutError("failure gate exceeded")
        if failure == "provider":
            raise RuntimeError("synthetic provider failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(memory.vector_store.client, "upsert", gated)
    if failure == "history":
        memory.db.connection.set_authorizer(
            lambda action, table, *_: (
                sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_INSERT and table == "history" else sqlite3.SQLITE_OK
            )
        )
    try:
        task = asyncio.create_task(memory.add("fact", user_id="test", infer=False))
        assert await asyncio.to_thread(entered.wait, 5)
        if cancel:
            task.cancel()
            await asyncio.sleep(0)
        release.set()
        expected = RuntimeError if failure == "provider" else sqlite3.DatabaseError
        if cancel:
            with pytest.raises(asyncio.CancelledError) as caught:
                await task
            assert isinstance(caught.value.__cause__, expected)
            assert "Persistence failed while draining" in caplog.text
        else:
            with pytest.raises(expected):
                await task
    finally:
        release.set()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        close(memory)


@pytest.mark.asyncio
async def test_cancelled_inferred_batch_drains_partial_fallback(memory_config, monkeypatch):
    memory = AsyncMemory.from_config(memory_config)
    entered, release = threading.Event(), threading.Event()
    original = memory.vector_store.client.upsert
    calls = 0
    task = None

    def partial(*args, **kwargs):
        nonlocal calls
        calls += 1
        # Batch fails, first individual record succeeds, second fails.
        if calls != 2:
            raise RuntimeError("synthetic insert failure")
        result = original(*args, **kwargs)
        entered.set()
        if not release.wait(10):
            raise TimeoutError("fallback gate exceeded")
        return result

    monkeypatch.setattr(memory.vector_store.client, "upsert", partial)
    try:
        task = asyncio.create_task(memory.add("input", user_id="test"))
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        close(memory)
        memory = AsyncMemory.from_config(memory_config)
        rows = (await memory.get_all(filters={"user_id": "test"}))["results"]
        assert len(rows) == 1
        assert [h["event"] for h in await memory.history(rows[0]["id"])] == ["ADD"]
        assert calls == 3
    finally:
        release.set()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        close(memory)
