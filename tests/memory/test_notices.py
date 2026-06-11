import asyncio
from copy import deepcopy
from unittest.mock import MagicMock

import pytest

from mem0.memory import notices
from mem0.memory import telemetry as telemetry_module


class FakeFlags:
    def __init__(self, variant, payload):
        self.variant = variant
        self.payload = payload

    def get_flag(self, key):
        assert key == notices.FLAG_KEY
        return self.variant

    def get_flag_payload(self, key):
        assert key == notices.FLAG_KEY
        return self.payload


@pytest.fixture(autouse=True)
def reset_notice_process_state():
    notices._first_run_claimed_in_process = False
    yield
    notices._first_run_claimed_in_process = False


@pytest.fixture
def notice_harness(monkeypatch):
    config = {}
    telemetry = MagicMock()
    telemetry.user_id = "oss-user"

    def write_config(updated):
        saved = deepcopy(updated)
        config.clear()
        config.update(saved)

    monkeypatch.setattr(notices, "_load_config", lambda: config)
    monkeypatch.setattr(notices, "_write_config", write_config)
    monkeypatch.setattr(notices.telemetry_module, "MEM0_TELEMETRY", True)
    monkeypatch.setattr(notices.telemetry_module, "_get_oss_telemetry", lambda: telemetry)

    return config, telemetry


def configure_flag(telemetry, variant, payload):
    flags = FakeFlags(variant, payload)
    telemetry.posthog.evaluate_flags.return_value = flags
    return flags


def display_notice(notice_harness, variant="displayed", payload=None):
    config, telemetry = notice_harness
    if payload is None:
        payload = {
            "notices": {
                "first_run": {
                    "enabled": True,
                    "notice_type": "log_line",
                    "copy": "Mem0 OSS notice",
                }
            }
        }
    flags = configure_flag(telemetry, variant, payload)
    notices.display_first_run_notice(MagicMock(), "sync", "add")
    return config, telemetry, flags


def test_displayed_notice_logs_once_and_captures_event(notice_harness, capsys):
    config, telemetry, flags = display_notice(notice_harness)

    assert capsys.readouterr().err == "Mem0 OSS notice\n"
    telemetry.posthog.evaluate_flags.assert_called_once_with("oss-user", flag_keys=[notices.FLAG_KEY])
    telemetry.capture_event.assert_called_once()
    event_name, props = telemetry.capture_event.call_args.args
    assert event_name == notices.NOTICE_EVENT
    assert props["notice_id"] == "first_run"
    assert props["notice_type"] == "log_line"
    assert props["variant"] == "displayed"
    assert props["displayed"] is True
    assert props["payload"] == "Mem0 OSS notice"
    assert props["bypass_reason"] is None
    assert props["notice_config_found"] is True
    assert props["sync_type"] == "sync"
    assert props["trigger_function"] == "add"
    assert telemetry.capture_event.call_args.kwargs["flags"] is flags
    assert config["notice_state"]["first_run"]["consumed"] is True
    assert config["notice_state"]["first_run"]["variant"] == "displayed"

    notices.display_first_run_notice(MagicMock(), "sync", "search")
    assert capsys.readouterr().err == ""
    assert telemetry.capture_event.call_count == 1


def test_holdout_notice_is_silent_but_captures_event(notice_harness, capsys):
    _, telemetry, _ = display_notice(notice_harness, variant="holdout")

    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is False
    assert props["bypass_reason"] == "holdout"
    assert props["disabled_reason"] is None


@pytest.mark.parametrize(
    ("payload", "expected_reason", "expected_found"),
    [
        ({}, "missing_notice_config", False),
        ({"notices": {}}, "missing_notice_config", False),
        ({"notices": "not-an-object"}, "missing_notice_config", False),
        ({"notices": {"first_run": {"enabled": True, "notice_type": "log_line"}}}, "missing_copy", True),
        (
            {"notices": {"first_run": {"enabled": False, "notice_type": "log_line", "copy": "hidden"}}},
            "payload_disabled",
            True,
        ),
    ],
)
def test_bad_or_disabled_payload_is_silent_and_safe(
    notice_harness, payload, expected_reason, expected_found, capsys
):
    _, telemetry, _ = display_notice(notice_harness, payload=payload)

    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is False
    assert props["bypass_reason"] == expected_reason
    assert props["notice_config_found"] is expected_found


def test_telemetry_disabled_does_not_touch_posthog_or_state(monkeypatch, capsys):
    load_config = MagicMock(return_value={})
    write_config = MagicMock()
    get_telemetry = MagicMock()

    monkeypatch.setattr(notices, "_load_config", load_config)
    monkeypatch.setattr(notices, "_write_config", write_config)
    monkeypatch.setattr(notices.telemetry_module, "MEM0_TELEMETRY", False)
    monkeypatch.setattr(notices.telemetry_module, "_get_oss_telemetry", get_telemetry)

    notices.display_first_run_notice(MagicMock(), "sync", "add")

    load_config.assert_not_called()
    write_config.assert_not_called()
    get_telemetry.assert_not_called()
    assert capsys.readouterr().err == ""


def test_posthog_failure_is_silent_and_consumes_first_run(notice_harness, capsys):
    config, telemetry = notice_harness
    telemetry.posthog.evaluate_flags.side_effect = RuntimeError("network unavailable")

    notices.display_first_run_notice(MagicMock(), "sync", "add")

    assert capsys.readouterr().err == ""
    telemetry.capture_event.assert_not_called()
    assert config["notice_state"]["first_run"]["consumed"] is True


def test_notice_event_bypasses_sampling():
    assert notices.NOTICE_EVENT in telemetry_module._LIFECYCLE_EVENTS


def test_async_notice_wrapper_uses_shared_helper(monkeypatch):
    calls = []

    def display(memory_instance, sync_type, trigger_function):
        calls.append((memory_instance, sync_type, trigger_function))

    memory = MagicMock()
    monkeypatch.setattr(notices, "display_first_run_notice", display)

    asyncio.run(notices.display_first_run_notice_async(memory, "async", "search"))

    assert calls == [(memory, "async", "search")]
