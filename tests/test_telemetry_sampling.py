"""Tests for OSS telemetry sampling.

Tests target _sampling_before_send and its wiring directly. Existing tests in
test_telemetry.py cover opt-out, singleton, and lifecycle behavior and are
unaffected by sampling.
"""

from unittest.mock import patch

import pytest

import mem0.memory.telemetry as telemetry_module


class TestParseSampleRate:
    """Verify the env var parsing helper. Must never raise."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("0.0", 0.0),
            ("0.1", 0.1),
            ("0.5", 0.5),
            ("1.0", 1.0),
            ("0.05", 0.05),
        ],
    )
    def test_valid_values(self, raw, expected):
        assert telemetry_module._parse_sample_rate(raw) == expected

    @pytest.mark.parametrize("raw", ["abc", "", "5.0", "-1", "-0.5", "1.5", "2", "nan"])
    def test_invalid_values_fall_back_to_default(self, raw):
        assert telemetry_module._parse_sample_rate(raw) == telemetry_module._DEFAULT_SAMPLE_RATE

    def test_none_falls_back(self):
        assert telemetry_module._parse_sample_rate(None) == telemetry_module._DEFAULT_SAMPLE_RATE


class TestSamplingBeforeSend:
    """Verify _sampling_before_send: the PostHog hook that drops/keeps events."""

    def _msg(self, event_name, properties=None):
        return {"event": event_name, "properties": properties or {}}

    def test_lifecycle_event_passes_through_at_high_random(self):
        """Lifecycle events always fire even when random is near 1.0."""
        with patch("mem0.memory.telemetry.random.random", return_value=0.999):
            for event in ("mem0.init", "mem0.reset", "mem0._create_procedural_memory"):
                result = telemetry_module._sampling_before_send(self._msg(event))
                assert result is not None
                assert result["properties"]["sample_rate"] == 1.0

    def test_hot_path_event_dropped_when_random_above_rate(self):
        """At default rate 0.1, random=0.99 should drop the event."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY_SAMPLE_RATE", 0.1):
            with patch("mem0.memory.telemetry.random.random", return_value=0.99):
                assert telemetry_module._sampling_before_send(self._msg("mem0.add")) is None

    def test_hot_path_event_passes_when_random_below_rate(self):
        """At default rate 0.1, random=0.05 should pass the event through."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY_SAMPLE_RATE", 0.1):
            with patch("mem0.memory.telemetry.random.random", return_value=0.05):
                result = telemetry_module._sampling_before_send(self._msg("mem0.add"))
                assert result is not None
                assert result["properties"]["sample_rate"] == 0.1

    def test_hot_path_annotates_sample_rate(self):
        with patch.object(telemetry_module, "MEM0_TELEMETRY_SAMPLE_RATE", 0.1):
            with patch("mem0.memory.telemetry.random.random", return_value=0.0):
                result = telemetry_module._sampling_before_send(self._msg("mem0.search"))
                assert result["properties"]["sample_rate"] == 0.1

    def test_lifecycle_annotates_sample_rate_one(self):
        result = telemetry_module._sampling_before_send(self._msg("mem0.init"))
        assert result["properties"]["sample_rate"] == 1.0

    def test_rate_zero_drops_all_hot_path(self):
        with patch.object(telemetry_module, "MEM0_TELEMETRY_SAMPLE_RATE", 0.0):
            # Gate is `random >= rate`, so 0.0 >= 0.0 → drop. random ∈ [0, 1) means
            # rate=0 drops every event.
            with patch("mem0.memory.telemetry.random.random", return_value=0.0):
                assert telemetry_module._sampling_before_send(self._msg("mem0.add")) is None

    def test_rate_zero_still_passes_lifecycle(self):
        with patch.object(telemetry_module, "MEM0_TELEMETRY_SAMPLE_RATE", 0.0):
            with patch("mem0.memory.telemetry.random.random", return_value=0.999):
                assert telemetry_module._sampling_before_send(self._msg("mem0.init")) is not None

    def test_rate_one_passes_all_events(self):
        with patch.object(telemetry_module, "MEM0_TELEMETRY_SAMPLE_RATE", 1.0):
            with patch("mem0.memory.telemetry.random.random", return_value=0.999):
                # 0.999 > 1.0 is False, so the gate never trips
                assert telemetry_module._sampling_before_send(self._msg("mem0.add")) is not None

    def test_does_not_override_caller_supplied_sample_rate_for_hot_path(self):
        """If a caller pre-populates sample_rate, our value still wins (we're authoritative)."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY_SAMPLE_RATE", 0.1):
            with patch("mem0.memory.telemetry.random.random", return_value=0.0):
                msg = self._msg("mem0.add", {"sample_rate": 0.99, "other": "x"})
                result = telemetry_module._sampling_before_send(msg)
                assert result["properties"]["sample_rate"] == 0.1
                assert result["properties"]["other"] == "x"

    def test_handles_missing_properties_dict(self):
        """If a msg arrives without a properties key, we create it before annotating."""
        msg = {"event": "mem0.init"}  # no properties
        result = telemetry_module._sampling_before_send(msg)
        assert result is not None
        assert result["properties"]["sample_rate"] == 1.0

    def test_handles_missing_event_field(self):
        """Defensive: a msg with no event field is treated as a hot-path event (gets sampled)."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY_SAMPLE_RATE", 0.1):
            with patch("mem0.memory.telemetry.random.random", return_value=0.99):
                # event is missing -> treated as hot-path -> dropped at high random
                assert telemetry_module._sampling_before_send({"properties": {}}) is None

    def test_handles_non_dict_input(self):
        """Defensive: if PostHog ever passes us a non-dict, we drop the event."""
        assert telemetry_module._sampling_before_send("not a dict") is None
        assert telemetry_module._sampling_before_send(None) is None
        assert telemetry_module._sampling_before_send(42) is None
        assert telemetry_module._sampling_before_send(["list"]) is None


class TestBeforeSendWiring:
    """Verify the hook is wired into the OSS singleton but NOT client_telemetry."""

    def setup_method(self):
        telemetry_module._oss_telemetry_instance = None
        telemetry_module._oss_telemetry_shutting_down = False

    def teardown_method(self):
        telemetry_module._oss_telemetry_instance = None
        telemetry_module._oss_telemetry_shutting_down = False

    def test_oss_singleton_constructed_with_before_send_hook(self):
        """_get_oss_telemetry() should pass _sampling_before_send to AnonymousTelemetry."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    with patch("atexit.register"):
                        telemetry_module._get_oss_telemetry()
                        # Verify Posthog() was constructed with before_send=_sampling_before_send
                        _, kwargs = mock_posthog_cls.call_args
                        assert kwargs.get("before_send") is telemetry_module._sampling_before_send

    def test_client_telemetry_constructed_without_before_send(self):
        """The module-level client_telemetry must NOT receive before_send.

        client_telemetry is created at import time, so this test verifies the
        existing instance has no sampling hook attached to its underlying Posthog.
        """
        # client_telemetry is created at module import time. We verify the
        # construction call site by re-constructing AnonymousTelemetry() the
        # same way and checking the kwargs.
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    telemetry_module.AnonymousTelemetry()  # mirrors client_telemetry construction
                    _, kwargs = mock_posthog_cls.call_args
                    # before_send is None (default), not _sampling_before_send
                    assert kwargs.get("before_send") is None

    def test_anonymous_telemetry_falls_back_when_posthog_rejects_before_send(self):
        """If posthog (older version) rejects before_send, construction still succeeds."""
        with patch.object(telemetry_module, "MEM0_TELEMETRY", True):
            with patch("mem0.memory.telemetry.Posthog") as mock_posthog_cls:
                with patch("mem0.memory.telemetry.get_or_create_user_id", return_value="u"):
                    # First call (with before_send) raises TypeError; second call succeeds.
                    mock_posthog_cls.side_effect = [TypeError("unexpected kwarg before_send"), object()]
                    at = telemetry_module.AnonymousTelemetry(before_send=telemetry_module._sampling_before_send)
                    # Constructor was called twice: once with before_send, once without
                    assert mock_posthog_cls.call_count == 2
                    assert at.posthog is not None


class TestSamplingDoesNotBreakExistingBehavior:
    """Regression checks: sampling must be invisible above the SDK boundary."""

    def setup_method(self):
        telemetry_module._oss_telemetry_instance = None
        telemetry_module._oss_telemetry_shutting_down = False

    def teardown_method(self):
        telemetry_module._oss_telemetry_instance = None
        telemetry_module._oss_telemetry_shutting_down = False

    def test_capture_event_signature_unchanged(self):
        """The public capture_event() function still accepts the same args."""
        from inspect import signature

        params = list(signature(telemetry_module.capture_event).parameters)
        assert params == ["event_name", "memory_instance", "additional_data"]

    def test_capture_client_event_signature_unchanged(self):
        from inspect import signature

        params = list(signature(telemetry_module.capture_client_event).parameters)
        assert params == ["event_name", "instance", "additional_data"]

    def test_default_sample_rate_is_ten_percent(self):
        """Module loads with the documented default."""
        # We can't assert MEM0_TELEMETRY_SAMPLE_RATE directly because the user
        # may have set the env var, so assert the default constant instead.
        assert telemetry_module._DEFAULT_SAMPLE_RATE == 0.1
