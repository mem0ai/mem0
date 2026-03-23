"""Tests for Memory resource cleanup: close() and context manager."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def memory_instance():
    """Create a Memory instance with all dependencies mocked."""
    with (
        patch("mem0.memory.main.EmbedderFactory") as mock_embedder,
        patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
        patch("mem0.memory.main.LlmFactory") as mock_llm,
        patch("mem0.memory.telemetry.capture_event"),
        patch("mem0.memory.main.GraphStoreFactory") as mock_graph_store,
    ):
        mock_embedder.create.return_value = MagicMock()
        mock_embedder.create.return_value.config.embedding_dims = 1536
        mock_vector_store.create.return_value = MagicMock()
        mock_llm.create.return_value = MagicMock()
        mock_graph_store.create.return_value = MagicMock()

        from mem0.memory.main import Memory
        m = Memory()
        yield m


class TestMemoryClose:
    """Verify Memory.close() releases resources."""

    def test_close_shuts_down_telemetry(self, memory_instance):
        with patch("mem0.memory.telemetry.shutdown_telemetry") as mock_shutdown:
            memory_instance.close()
            mock_shutdown.assert_called_once()

    def test_close_closes_db(self, memory_instance):
        memory_instance.db = MagicMock()
        memory_instance.close()
        memory_instance.db.close.assert_called_once()

    def test_close_closes_vector_store_if_available(self, memory_instance):
        mock_vs = MagicMock(spec=["close"])
        memory_instance.vector_store = mock_vs
        memory_instance.close()
        mock_vs.close.assert_called_once()

    def test_close_skips_vector_store_without_close(self, memory_instance):
        mock_vs = MagicMock(spec=[])
        memory_instance.vector_store = mock_vs
        memory_instance.close()  # should not raise

    def test_close_is_idempotent(self, memory_instance):
        memory_instance.close()
        memory_instance.close()  # should not raise

    def test_close_continues_on_db_error(self, memory_instance):
        memory_instance.db = MagicMock()
        memory_instance.db.close.side_effect = Exception("db error")
        memory_instance.close()  # should not raise


class TestMemoryContextManager:
    """Verify Memory works as a context manager."""

    def test_enter_returns_self(self, memory_instance):
        assert memory_instance.__enter__() is memory_instance

    def test_exit_calls_close(self, memory_instance):
        memory_instance.db = MagicMock()
        with patch("mem0.memory.telemetry.shutdown_telemetry"):
            memory_instance.__exit__(None, None, None)
        memory_instance.db.close.assert_called_once()

    def test_does_not_suppress_exceptions(self, memory_instance):
        assert memory_instance.__exit__(ValueError, ValueError("x"), None) is False

    def test_with_statement(self, memory_instance):
        memory_instance.db = MagicMock()
        with patch("mem0.memory.telemetry.shutdown_telemetry"):
            with memory_instance:
                pass
        memory_instance.db.close.assert_called_once()

    def test_with_statement_on_exception(self, memory_instance):
        memory_instance.db = MagicMock()
        with patch("mem0.memory.telemetry.shutdown_telemetry"):
            with pytest.raises(RuntimeError):
                with memory_instance:
                    raise RuntimeError("boom")
        memory_instance.db.close.assert_called_once()




@pytest.fixture
def async_memory_instance():
    """Create an AsyncMemory instance with all dependencies mocked."""
    with (
        patch("mem0.memory.main.EmbedderFactory") as mock_embedder,
        patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
        patch("mem0.memory.main.LlmFactory") as mock_llm,
        patch("mem0.memory.telemetry.capture_event"),
        patch("mem0.memory.main.GraphStoreFactory") as mock_graph_store,
    ):
        mock_embedder.create.return_value = MagicMock()
        mock_embedder.create.return_value.config.embedding_dims = 1536
        mock_vector_store.create.return_value = MagicMock()
        mock_llm.create.return_value = MagicMock()
        mock_graph_store.create.return_value = MagicMock()

        from mem0.memory.main import AsyncMemory
        m = AsyncMemory()
        yield m


class TestAsyncMemoryClose:
    """Verify AsyncMemory.close() releases resources."""

    def test_close_shuts_down_telemetry(self, async_memory_instance):
        with patch("mem0.memory.telemetry.shutdown_telemetry") as mock_shutdown:
            async_memory_instance.close()
            mock_shutdown.assert_called_once()

    def test_close_closes_db(self, async_memory_instance):
        async_memory_instance.db = MagicMock()
        async_memory_instance.close()
        async_memory_instance.db.close.assert_called_once()

    def test_close_is_idempotent(self, async_memory_instance):
        async_memory_instance.close()
        async_memory_instance.close()  # should not raise


class TestAsyncMemoryContextManager:
    """Verify AsyncMemory works as an async context manager."""

    @pytest.mark.asyncio
    async def test_aenter_returns_self(self, async_memory_instance):
        result = await async_memory_instance.__aenter__()
        assert result is async_memory_instance

    @pytest.mark.asyncio
    async def test_aexit_calls_close(self, async_memory_instance):
        async_memory_instance.db = MagicMock()
        with patch("mem0.memory.telemetry.shutdown_telemetry"):
            await async_memory_instance.__aexit__(None, None, None)
        async_memory_instance.db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_with_statement(self, async_memory_instance):
        async_memory_instance.db = MagicMock()
        with patch("mem0.memory.telemetry.shutdown_telemetry"):
            async with async_memory_instance:
                pass
        async_memory_instance.db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_with_statement_on_exception(self, async_memory_instance):
        async_memory_instance.db = MagicMock()
        with patch("mem0.memory.telemetry.shutdown_telemetry"):
            with pytest.raises(RuntimeError):
                async with async_memory_instance:
                    raise RuntimeError("boom")
        async_memory_instance.db.close.assert_called_once()
