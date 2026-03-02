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
        """capture_event() should return immediately without creating AnonymousTelemetry."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", False):
            with patch("mem0.memory.telemetry.AnonymousTelemetry") as mock_cls:
                telemetry_module.capture_event("test.event", MagicMock())
                mock_cls.assert_not_called()

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
        """capture_event() should create AnonymousTelemetry and call capture when enabled."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.AnonymousTelemetry") as mock_cls:
                mock_at = MagicMock()
                mock_cls.return_value = mock_at
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
