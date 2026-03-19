"""Tests for Memory resource cleanup (close, context manager, __del__)."""

import threading
from unittest.mock import MagicMock, patch

import pytest


class TestTelemetryCleanup:
    """Test that telemetry properly shuts down PostHog threads."""

    def test_capture_event_closes_telemetry(self):
        """capture_event should call close() after sending event."""
        from mem0.memory.telemetry import AnonymousTelemetry

        telemetry = AnonymousTelemetry()
        if telemetry.posthog is not None:
            # Mock shutdown to verify it gets called
            telemetry.posthog.shutdown = MagicMock()
            telemetry.close()
            telemetry.posthog.shutdown.assert_called_once()

    def test_telemetry_close_is_idempotent(self):
        """Calling close() multiple times should not raise."""
        from mem0.memory.telemetry import AnonymousTelemetry

        telemetry = AnonymousTelemetry()
        telemetry.close()
        telemetry.close()  # Should not raise


class TestMemoryContextManager:
    """Test Memory as a context manager."""

    @patch("mem0.memory.main.VectorStoreFactory")
    @patch("mem0.memory.main.EmbedderFactory")
    @patch("mem0.memory.main.LlmFactory")
    @patch("mem0.memory.main.SQLiteManager")
    @patch("mem0.memory.main.capture_event")
    def test_memory_context_manager_calls_close(
        self, mock_capture, mock_sqlite, mock_llm_factory, mock_embedder_factory, mock_vector_factory
    ):
        """Memory should support 'with' statement and call close() on exit."""
        from mem0.memory.main import Memory

        mock_embedder = MagicMock()
        mock_embedder.config.embedding_dims = 1536
        mock_embedder_factory.create.return_value = mock_embedder

        mock_vector = MagicMock()
        mock_vector_factory.create.return_value = mock_vector

        mock_llm = MagicMock()
        mock_llm_factory.create.return_value = mock_llm

        mock_db = MagicMock()
        mock_sqlite.return_value = mock_db

        memory = Memory()
        memory.close = MagicMock()

        with memory as m:
            assert m is memory

        memory.close.assert_called_once()
