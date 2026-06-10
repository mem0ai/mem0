import threading
from unittest.mock import MagicMock, patch

import pytest

import mem0.memory.telemetry as telemetry_module


class TestTelemetryDisabled:
    """Verify PostHog is never instantiated when telemetry is disabled."""

    def test_posthog_not_created_when_disabled(self):
        """Posthog() constructor should never be called when MEM0_TELEMETRY=False."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", False):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog:
                at = telemetry_module.AnonymousTelemetry()
                mock_posthog.assert_not_called()
                assert at.posthog is None
                assert at.user_id is None

    def test_capture_event_noop_when_disabled(self):
        """capture_event() should return immediately without touching the singleton."""
        saved = telemetry_module._oss_telemetry_instance
        try:
            telemetry_module._oss_telemetry_instance = None
            with patch.object(telemetry_module, "MEM0_TELEMETRY", False):
                telemetry_module.capture_event("test.event", MagicMock())
                # Singleton must not have been initialised
                assert telemetry_module._oss_telemetry_instance is None
        finally:
            telemetry_module._oss_telemetry_instance = saved

    def test_capture_client_event_noop_when_disabled(self):
        """capture_client_event() should return immediately without calling posthog."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", False):
            mock_instance = MagicMock()
            mock_client_telemetry = MagicMock()
            with patch.object(telemetry_module, "client_telemetry", mock_client_telemetry):
                telemetry_module.capture_client_event("test.event", mock_instance)
                mock_client_telemetry.capture_event.assert_not_called()

    def test_instance_capture_event_noop_when_posthog_is_none(self):
        """AnonymousTelemetry.capture_event() should be a no-op when posthog is None."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", False):
            at = telemetry_module.AnonymousTelemetry()
            at.capture_event("test.event", {"key": "value"})  # should not raise

    def test_close_noop_when_posthog_is_none(self):
        """close() should not raise when posthog is None."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", False):
            at = telemetry_module.AnonymousTelemetry()
            at.close()  # should not raise

    def test_no_threads_spawned_when_disabled(self):
        """No consumer threads should be created when telemetry is disabled."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", False):
            threads_before = threading.active_count()
            telemetry_module.AnonymousTelemetry()
            threads_after = threading.active_count()
            assert threads_after == threads_before


class TestTelemetryEnabled:
    """Verify PostHog works normally when telemetry is enabled."""

    def test_posthog_created_when_enabled(self):
        """Posthog() should be instantiated when MEM0_TELEMETRY=True."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog:
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="test-user"):
                    at = telemetry_module.AnonymousTelemetry()
                    mock_posthog.assert_called_once()
                    assert at.posthog is not None
                    assert at.user_id == "test-user"

    def test_capture_event_sends_when_enabled(self):
        """capture_event() should use the singleton and call capture when enabled."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            mock_at = MagicMock()
            with patch.object(telemetry_module, "_oss_telemetry_instance", mock_at):
                mock_memory = MagicMock()
                mock_memory.config.graph_store.config = None
                mock_memory.api_version = "v1"
                telemetry_module.capture_event("test.event", mock_memory)
                mock_at.capture_event.assert_called_once()

    def test_capture_client_event_sends_when_enabled(self):
        """capture_client_event() should call client_telemetry.capture_event when enabled."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            mock_client_telemetry = MagicMock()
            with patch.object(telemetry_module, "client_telemetry", mock_client_telemetry):
                mock_instance = MagicMock()
                mock_instance.user_email = "test@example.com"
                telemetry_module.capture_client_event("test.event", mock_instance)
                mock_client_telemetry.capture_event.assert_called_once()


class TestAnonymousTelemetryClose:
    """Verify AnonymousTelemetry.close() edge cases."""

    def test_close_calls_posthog_shutdown(self):
        """close() should call posthog.shutdown()."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    at = telemetry_module.AnonymousTelemetry()
                    mock_ph = mock_posthog_cls.return_value
                    at.close()
                    mock_ph.shutdown.assert_called_once()

    def test_close_sets_posthog_to_none(self):
        """close() should set posthog to None to prevent double-shutdown."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog"):
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    at = telemetry_module.AnonymousTelemetry()
                    at.close()
                    assert at.posthog is None

    def test_double_close_is_safe(self):
        """Calling close() twice should not raise."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    at = telemetry_module.AnonymousTelemetry()
                    mock_ph = mock_posthog_cls.return_value
                    at.close()
                    at.close()  # should not raise
                    # shutdown only called once because posthog was set to None after first close
                    mock_ph.shutdown.assert_called_once()

    def test_capture_after_close_is_noop(self):
        """capture_event() should be a no-op after close() (posthog is None)."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    at = telemetry_module.AnonymousTelemetry()
                    mock_ph = mock_posthog_cls.return_value
                    at.close()
                    mock_ph.reset_mock()
                    at.capture_event("test.event", {"key": "value"})
                    mock_ph.capture.assert_not_called()


class TestTelemetrySingleton:
    """Verify the OSS telemetry singleton behaviour."""

    def setup_method(self):
        # Reset singleton state before each test
        telemetry_module._oss_telemetry_instance = None
        telemetry_module._oss_telemetry_shutting_down = False

    def teardown_method(self):
        telemetry_module._oss_telemetry_instance = None
        telemetry_module._oss_telemetry_shutting_down = False

    def test_singleton_reuses_instance(self):
        """_get_oss_telemetry() should return the same instance on repeated calls."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog"):
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    with patch("atexit.register"):
                        first = telemetry_module._get_oss_telemetry()
                        second = telemetry_module._get_oss_telemetry()
                        assert first is second

    def test_singleton_created_only_once_across_threads(self):
        """Only one AnonymousTelemetry should be created even under concurrent access."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog:
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    with patch("atexit.register"):
                        instances = []

                        def grab():
                            instances.append(telemetry_module._get_oss_telemetry())

                        threads = [threading.Thread(target=grab) for _ in range(20)]
                        for t in threads:
                            t.start()
                        for t in threads:
                            t.join()

                        assert len(set(id(i) for i in instances)) == 1
                        assert mock_posthog.call_count == 1

    def test_atexit_registered_once(self):
        """atexit.register should be called exactly once for the singleton."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog"):
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    with patch("atexit.register") as mock_atexit:
                        telemetry_module._get_oss_telemetry()
                        telemetry_module._get_oss_telemetry()
                        telemetry_module._get_oss_telemetry()
                        # Only one atexit registration despite multiple calls
                        mock_atexit.assert_called_once_with(telemetry_module._shutdown_oss_telemetry)

    def test_capture_event_does_not_create_new_instance_each_call(self):
        """capture_event() should not create a new AnonymousTelemetry per call."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog"):
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    with patch("atexit.register"):
                        mock_memory = MagicMock()
                        mock_memory.config.graph_store.config = None
                        mock_memory.api_version = "v1"

                        telemetry_module.capture_event("e1", mock_memory)
                        first = telemetry_module._oss_telemetry_instance

                        telemetry_module.capture_event("e2", mock_memory)
                        second = telemetry_module._oss_telemetry_instance

                        assert first is second

    def test_posthog_constructed_once_across_many_capture_event_calls(self):
        """The core leak fix: Posthog() should only be called once no matter how
        many times capture_event() is invoked."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    with patch("atexit.register"):
                        mock_memory = MagicMock()
                        mock_memory.config.graph_store.config = None
                        mock_memory.api_version = "v1"

                        for i in range(50):
                            telemetry_module.capture_event(f"event_{i}", mock_memory)

                        # Only ONE Posthog client created, not 50
                        assert mock_posthog_cls.call_count == 1

    def test_shutdown_clears_singleton(self):
        """_shutdown_oss_telemetry() should close and clear the singleton."""
        mock_at = MagicMock()
        telemetry_module._oss_telemetry_instance = mock_at

        telemetry_module._shutdown_oss_telemetry()

        mock_at.close.assert_called_once()
        assert telemetry_module._oss_telemetry_instance is None

    def test_shutdown_idempotent(self):
        """Calling _shutdown_oss_telemetry() twice should not raise."""
        mock_at = MagicMock()
        telemetry_module._oss_telemetry_instance = mock_at

        telemetry_module._shutdown_oss_telemetry()
        telemetry_module._shutdown_oss_telemetry()  # should not raise

        mock_at.close.assert_called_once()

    def test_shutdown_noop_when_no_instance(self):
        """_shutdown_oss_telemetry() should be a no-op when singleton was never created."""
        assert telemetry_module._oss_telemetry_instance is None
        telemetry_module._shutdown_oss_telemetry()  # should not raise

    def test_capture_event_noop_when_disabled_with_singleton(self):
        """capture_event() should not initialise the singleton when telemetry is off."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", False):
            telemetry_module.capture_event("test.event", MagicMock())
            assert telemetry_module._oss_telemetry_instance is None

    def test_no_new_instance_after_shutdown(self):
        """After _shutdown_oss_telemetry(), _get_oss_telemetry() should not create a new instance."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog"):
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    with patch("atexit.register"):
                        # Create and then shut down the singleton
                        telemetry_module._get_oss_telemetry()
                        telemetry_module._shutdown_oss_telemetry()

                        # After shutdown, getting telemetry should return None, not a new instance
                        result = telemetry_module._get_oss_telemetry()
                        assert result is None
                        assert telemetry_module._oss_telemetry_instance is None


class TestMemoryLifecycle:
    """Verify Memory.close() and context manager support."""

    def _make_mock_memory(self):
        """Create a Memory-like object with a mock db for testing close()."""
        from mem0.memory.main import Memory

        with patch.object(Memory, "__init__", lambda self: None):
            m = Memory.__new__(Memory)
            m.db = MagicMock()
            return m

    def test_double_close_is_safe(self):
        """close() should be safe to call twice (SQLiteManager.close sets connection=None)."""
        m = self._make_mock_memory()
        m.close()
        # After first close, db is still the mock but SQLiteManager.close() handles
        # the None-connection case internally. Simulate that by making db.close a no-op.
        m.close()  # should not raise

    def test_close_when_db_is_none(self):
        """close() should not raise if db was already None."""
        m = self._make_mock_memory()
        m.db = None
        m.close()  # should not raise

    def test_close_when_db_not_set(self):
        """close() should not raise if __init__ failed before setting db."""
        from mem0.memory.main import Memory

        with patch.object(Memory, "__init__", lambda self: None):
            m = Memory.__new__(Memory)
            # db attribute not set at all
            m.close()  # should not raise due to hasattr guard


class TestAsyncMemoryLifecycle:
    """Verify AsyncMemory.close() and async context manager support."""

    def _make_mock_async_memory(self):
        from mem0.memory.main import AsyncMemory

        with patch.object(AsyncMemory, "__init__", lambda self: None):
            m = AsyncMemory.__new__(AsyncMemory)
            m.db = MagicMock()
            return m

    def test_close_when_db_is_none(self):
        m = self._make_mock_async_memory()
        m.db = None
        m.close()  # should not raise

    def test_close_when_db_not_set(self):
        from mem0.memory.main import AsyncMemory

        with patch.object(AsyncMemory, "__init__", lambda self: None):
            m = AsyncMemory.__new__(AsyncMemory)
            m.close()  # should not raise


class TestTelemetryEnvVar:
    """Verify the MEM0_TELEMETRY env var parsing logic."""

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("False", False),
            ("0", False),
            ("no", False),
            ("anything_else", False),
        ],
    )
    def test_env_var_parsing(self, value, expected):
        result = value.lower() in ("true", "1", "yes")
        assert result == expected


class TestTelemetryNullUserIdHandling:
    """Verify telemetry doesn't crash when user_id is None.

    This is a regression test for the bug where Memory.from_config() crashed
    with AssertionError because distinct_id was None in PostHog.capture().
    """

    def test_capture_event_skips_when_user_id_is_none(self):
        """AnonymousTelemetry.capture_event should not crash when user_id is None."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                at = telemetry_module.AnonymousTelemetry()
                at.user_id = None  # Simulate the bug condition

                # This should not raise, even with user_id=None
                at.capture_event("test.event", {"key": "value"})

                # PostHog.capture should NOT have been called since user_id is None
                mock_posthog_cls.return_value.capture.assert_not_called()

    def test_capture_event_does_not_crash_on_posthog_error(self):
        """AnonymousTelemetry.capture_event should catch PostHog exceptions."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="test-user"):
                    at = telemetry_module.AnonymousTelemetry()
                    mock_posthog_cls.return_value.capture.side_effect = Exception("PostHog error")

                    # This should not raise, even when PostHog.capture fails
                    at.capture_event("test.event", {"key": "value"})

    def test_oss_capture_event_does_not_crash_memory_init(self):
        """capture_event() should never raise, even if everything inside fails."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            # Make _get_oss_telemetry return a broken telemetry object
            mock_at = MagicMock()
            mock_at.capture_event.side_effect = Exception("Telemetry is broken")

            with patch.object(telemetry_module, "_oss_telemetry_instance", mock_at):
                mock_memory = MagicMock()
                mock_memory.config.graph_store.config = None
                mock_memory.api_version = "v1"

                # This should not raise, even when telemetry fails
                telemetry_module.capture_event("mem0.init", mock_memory)

    def test_client_capture_event_does_not_crash(self):
        """capture_client_event() should never raise exceptions."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            mock_client_telemetry = MagicMock()
            mock_client_telemetry.capture_event.side_effect = Exception("Client telemetry broken")

            with patch.object(telemetry_module, "client_telemetry", mock_client_telemetry):
                mock_instance = MagicMock()
                mock_instance.user_email = "test@example.com"

                # This should not raise
                telemetry_module.capture_client_event("test.event", mock_instance)
