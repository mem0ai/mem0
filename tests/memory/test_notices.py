import asyncio
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
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


def temporal_payload(copy="Temporal CTA", enabled=True, notice_type="error"):
    payload = {
        "notices": {
            "temporal_stub": {
                "enabled": enabled,
                "notice_type": notice_type,
            }
        }
    }
    if copy is not None:
        payload["notices"]["temporal_stub"]["copy"] = copy
    return payload


def decay_payload(copy="Decay CTA", enabled=True, notice_type="error"):
    payload = {
        "notices": {
            "decay_stub": {
                "enabled": enabled,
                "notice_type": notice_type,
            }
        }
    }
    if copy is not None:
        payload["notices"]["decay_stub"]["copy"] = copy
    return payload


def temporal_usage_payload(copy="Temporal usage CTA", enabled=True, notice_type="log_line"):
    payload = {
        "notices": {
            "temporal_usage": {
                "enabled": enabled,
                "notice_type": notice_type,
            }
        }
    }
    if copy is not None:
        payload["notices"]["temporal_usage"]["copy"] = copy
    return payload


def scale_payload(
    top_k_copy="Scale top {top_k}",
    memory_count_copy="Scale count {memory_count}",
    enabled=True,
    notice_type="log_line",
):
    payload = {
        "notices": {
            "scale_threshold": {
                "enabled": enabled,
                "notice_type": notice_type,
                "copies": {},
            }
        }
    }
    copies = payload["notices"]["scale_threshold"]["copies"]
    if top_k_copy is not None:
        copies["top_k"] = top_k_copy
    if memory_count_copy is not None:
        copies["memory_count"] = memory_count_copy
    return payload


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


def test_temporal_feature_displayed_returns_payload_copy_and_captures_event(notice_harness, capsys):
    _, telemetry = notice_harness
    flags = configure_flag(telemetry, "displayed", temporal_payload())

    message = notices.get_temporal_feature_error_message("sync", "add", "timestamp")

    assert message == "Temporal CTA"
    assert capsys.readouterr().err == ""
    telemetry.posthog.evaluate_flags.assert_called_once_with("oss-user", flag_keys=[notices.FLAG_KEY])
    telemetry.capture_event.assert_called_once()
    event_name, props = telemetry.capture_event.call_args.args
    assert event_name == notices.NOTICE_EVENT
    assert props["notice_id"] == "temporal_stub"
    assert props["notice_type"] == "error"
    assert props["variant"] == "displayed"
    assert props["displayed"] is True
    assert props["payload"] == "Temporal CTA"
    assert props["bypass_reason"] is None
    assert props["disabled_reason"] is None
    assert props["notice_config_found"] is True
    assert props["sync_type"] == "sync"
    assert props["trigger_function"] == "add"
    assert props["trigger_parameter"] == "timestamp"
    assert telemetry.capture_event.call_args.kwargs["flags"] is flags


def test_temporal_feature_holdout_returns_payload_copy_and_captures_event(notice_harness, capsys):
    _, telemetry = notice_harness
    configure_flag(telemetry, "holdout", temporal_payload())

    message = notices.get_temporal_feature_error_message("sync", "search", "reference_date")

    assert message == "Temporal CTA"
    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is True
    assert props["bypass_reason"] is None
    assert props["trigger_function"] == "search"
    assert props["trigger_parameter"] == "reference_date"


@pytest.mark.parametrize(
    ("payload", "expected_reason", "expected_found"),
    [
        ({}, "missing_notice_config", False),
        ({"notices": {}}, "missing_notice_config", False),
        ({"notices": "not-an-object"}, "missing_notice_config", False),
        (temporal_payload(copy=None), "missing_copy", True),
        (temporal_payload(enabled=False, copy="hidden"), "payload_disabled", True),
    ],
)
def test_temporal_feature_bad_or_disabled_payload_returns_plain_error(
    notice_harness, payload, expected_reason, expected_found, capsys
):
    _, telemetry = notice_harness
    configure_flag(telemetry, "displayed", payload)

    message = notices.get_temporal_feature_error_message("sync", "add", "timestamp")

    assert message == notices.TEMPORAL_FEATURE_ERROR_MESSAGES["timestamp"]
    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is False
    assert props["bypass_reason"] == expected_reason
    assert props["notice_config_found"] is expected_found


@pytest.mark.parametrize("variant", [None, False])
def test_temporal_feature_blunt_flag_disable_returns_plain_error_without_event(
    notice_harness, variant, capsys
):
    _, telemetry = notice_harness
    configure_flag(telemetry, variant, temporal_payload())

    message = notices.get_temporal_feature_error_message("sync", "add", "timestamp")

    assert message == notices.TEMPORAL_FEATURE_ERROR_MESSAGES["timestamp"]
    assert capsys.readouterr().err == ""
    telemetry.capture_event.assert_not_called()


def test_temporal_feature_telemetry_disabled_does_not_touch_posthog(monkeypatch, capsys):
    get_telemetry = MagicMock()

    monkeypatch.setattr(notices.telemetry_module, "MEM0_TELEMETRY", False)
    monkeypatch.setattr(notices.telemetry_module, "_get_oss_telemetry", get_telemetry)

    message = notices.get_temporal_feature_error_message("sync", "add", "timestamp")

    assert message == notices.TEMPORAL_FEATURE_ERROR_MESSAGES["timestamp"]
    get_telemetry.assert_not_called()
    assert capsys.readouterr().err == ""


def test_temporal_feature_posthog_failure_returns_plain_error(notice_harness, capsys):
    _, telemetry = notice_harness
    telemetry.posthog.evaluate_flags.side_effect = RuntimeError("network unavailable")

    message = notices.get_temporal_feature_error_message("sync", "add", "timestamp")

    assert message == notices.TEMPORAL_FEATURE_ERROR_MESSAGES["timestamp"]
    telemetry.capture_event.assert_not_called()
    assert capsys.readouterr().err == ""


def test_async_temporal_feature_wrapper_uses_shared_helper(monkeypatch):
    calls = []

    def get_error(sync_type, trigger_function, trigger_parameter):
        calls.append((sync_type, trigger_function, trigger_parameter))
        return "blocked"

    monkeypatch.setattr(notices, "get_temporal_feature_error_message", get_error)

    message = asyncio.run(
        notices.get_temporal_feature_error_message_async("async", "search", "reference_date")
    )

    assert message == "blocked"
    assert calls == [("async", "search", "reference_date")]


def test_decay_feature_displayed_returns_payload_copy_and_captures_event(notice_harness, capsys):
    _, telemetry = notice_harness
    flags = configure_flag(telemetry, "displayed", decay_payload())

    message = notices.get_decay_feature_error_message("sync", "project.update", "decay")

    assert message == "Decay CTA"
    assert capsys.readouterr().err == ""
    telemetry.posthog.evaluate_flags.assert_called_once_with("oss-user", flag_keys=[notices.FLAG_KEY])
    telemetry.capture_event.assert_called_once()
    event_name, props = telemetry.capture_event.call_args.args
    assert event_name == notices.NOTICE_EVENT
    assert props["notice_id"] == "decay_stub"
    assert props["notice_type"] == "error"
    assert props["variant"] == "displayed"
    assert props["displayed"] is True
    assert props["payload"] == "Decay CTA"
    assert props["bypass_reason"] is None
    assert props["disabled_reason"] is None
    assert props["notice_config_found"] is True
    assert props["sync_type"] == "sync"
    assert props["trigger_function"] == "project.update"
    assert props["trigger_parameter"] == "decay"
    assert telemetry.capture_event.call_args.kwargs["flags"] is flags


def test_decay_feature_holdout_returns_payload_copy_and_captures_event(notice_harness, capsys):
    _, telemetry = notice_harness
    configure_flag(telemetry, "holdout", decay_payload())

    message = notices.get_decay_feature_error_message("sync", "project.update", "decay")

    assert message == "Decay CTA"
    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is True
    assert props["bypass_reason"] is None
    assert props["variant"] == "holdout"


@pytest.mark.parametrize(
    ("payload", "expected_reason", "expected_found"),
    [
        ({}, "missing_notice_config", False),
        ({"notices": {}}, "missing_notice_config", False),
        ({"notices": "not-an-object"}, "missing_notice_config", False),
        (decay_payload(copy=None), "missing_copy", True),
        (decay_payload(enabled=False, copy="hidden"), "payload_disabled", True),
    ],
)
def test_decay_feature_bad_or_disabled_payload_returns_plain_error(
    notice_harness, payload, expected_reason, expected_found, capsys
):
    _, telemetry = notice_harness
    configure_flag(telemetry, "displayed", payload)

    message = notices.get_decay_feature_error_message("sync", "project.update", "decay")

    assert message == notices.DECAY_FEATURE_ERROR_MESSAGE
    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is False
    assert props["bypass_reason"] == expected_reason
    assert props["notice_config_found"] is expected_found


@pytest.mark.parametrize("variant", [None, False])
def test_decay_feature_blunt_flag_disable_returns_plain_error_without_event(
    notice_harness, variant, capsys
):
    _, telemetry = notice_harness
    configure_flag(telemetry, variant, decay_payload())

    message = notices.get_decay_feature_error_message("sync", "project.update", "decay")

    assert message == notices.DECAY_FEATURE_ERROR_MESSAGE
    assert capsys.readouterr().err == ""
    telemetry.capture_event.assert_not_called()


def test_decay_feature_telemetry_disabled_does_not_touch_posthog(monkeypatch, capsys):
    get_telemetry = MagicMock()

    monkeypatch.setattr(notices.telemetry_module, "MEM0_TELEMETRY", False)
    monkeypatch.setattr(notices.telemetry_module, "_get_oss_telemetry", get_telemetry)

    message = notices.get_decay_feature_error_message("sync", "project.update", "decay")

    assert message == notices.DECAY_FEATURE_ERROR_MESSAGE
    get_telemetry.assert_not_called()
    assert capsys.readouterr().err == ""


def test_decay_feature_posthog_failure_returns_plain_error(notice_harness, capsys):
    _, telemetry = notice_harness
    telemetry.posthog.evaluate_flags.side_effect = RuntimeError("network unavailable")

    message = notices.get_decay_feature_error_message("sync", "project.update", "decay")

    assert message == notices.DECAY_FEATURE_ERROR_MESSAGE
    telemetry.capture_event.assert_not_called()
    assert capsys.readouterr().err == ""


def test_async_decay_feature_wrapper_uses_shared_helper(monkeypatch):
    calls = []

    def get_error(sync_type, trigger_function, trigger_parameter):
        calls.append((sync_type, trigger_function, trigger_parameter))
        return "blocked"

    monkeypatch.setattr(notices, "get_decay_feature_error_message", get_error)

    message = asyncio.run(
        notices.get_decay_feature_error_message_async("async", "project.update", "decay")
    )

    assert message == "blocked"
    assert calls == [("async", "project.update", "decay")]


def test_temporal_usage_query_detection_is_conservative():
    assert notices.detect_temporal_usage_from_search("what happened last week?", None) == (
        "query",
        "relative_phrase",
    )
    assert notices.detect_temporal_usage_from_search("notes from 2025-04-09", None) == (
        "query",
        "date_like_query",
    )
    assert notices.detect_temporal_usage_from_search("favorite drink", None) is None


def test_temporal_usage_metadata_detection():
    assert notices.detect_temporal_usage_from_metadata({"event_date": "2025-04-09"}) == (
        "metadata",
        "date_like_metadata",
    )
    assert notices.detect_temporal_usage_from_metadata({"timestamp": 1778112000}) == (
        "metadata",
        "date_like_metadata",
    )
    assert notices.detect_temporal_usage_from_metadata({"nested": {"started_at": datetime.now(timezone.utc)}}) == (
        "metadata",
        "date_like_metadata",
    )
    assert notices.detect_temporal_usage_from_metadata({"category": "planning"}) is None


def test_temporal_usage_filter_detection():
    filters = {"AND": [{"user_id": "u1"}, {"created_at": {"gte": "2025-04-01"}}]}
    assert notices.detect_temporal_usage_from_search("favorite drink", filters) == (
        "filter",
        "date_range_filter",
    )
    assert notices.detect_temporal_usage_from_search("favorite drink", {"score": {"gte": 0.5}}) is None


def test_temporal_usage_displayed_logs_and_captures_event(notice_harness, capsys):
    config, telemetry = notice_harness
    flags = configure_flag(telemetry, "displayed", temporal_usage_payload())

    notices.display_temporal_usage_notice(MagicMock(), "sync", "search", "query", "relative_phrase")

    assert capsys.readouterr().err == "Temporal usage CTA\n"
    telemetry.posthog.evaluate_flags.assert_called_once_with("oss-user", flag_keys=[notices.FLAG_KEY])
    telemetry.capture_event.assert_called_once()
    event_name, props = telemetry.capture_event.call_args.args
    assert event_name == notices.NOTICE_EVENT
    assert props["notice_id"] == "temporal_usage"
    assert props["notice_type"] == "log_line"
    assert props["variant"] == "displayed"
    assert props["displayed"] is True
    assert props["payload"] == "Temporal usage CTA"
    assert props["bypass_reason"] is None
    assert props["disabled_reason"] is None
    assert props["notice_config_found"] is True
    assert props["sync_type"] == "sync"
    assert props["trigger_function"] == "search"
    assert props["trigger_source"] == "query"
    assert props["trigger_reason"] == "relative_phrase"
    assert telemetry.capture_event.call_args.kwargs["flags"] is flags
    assert len(config["notice_state"]["temporal_usage"]["events"]) == 1


def test_temporal_usage_holdout_is_silent_but_captures_event(notice_harness, capsys):
    _, telemetry = notice_harness
    configure_flag(telemetry, "holdout", temporal_usage_payload())

    notices.display_temporal_usage_notice(MagicMock(), "sync", "add", "metadata", "date_like_metadata")

    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is False
    assert props["bypass_reason"] == "holdout"
    assert props["trigger_source"] == "metadata"
    assert props["trigger_reason"] == "date_like_metadata"


@pytest.mark.parametrize(
    ("payload", "expected_reason", "expected_found"),
    [
        ({}, "missing_notice_config", False),
        ({"notices": {}}, "missing_notice_config", False),
        ({"notices": "not-an-object"}, "missing_notice_config", False),
        (temporal_usage_payload(copy=None), "missing_copy", True),
        (temporal_usage_payload(enabled=False, copy="hidden"), "payload_disabled", True),
    ],
)
def test_temporal_usage_bad_or_disabled_payload_is_silent_and_safe(
    notice_harness, payload, expected_reason, expected_found, capsys
):
    _, telemetry = notice_harness
    configure_flag(telemetry, "displayed", payload)

    notices.display_temporal_usage_notice(MagicMock(), "sync", "search", "query", "relative_phrase")

    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is False
    assert props["bypass_reason"] == expected_reason
    assert props["notice_config_found"] is expected_found


@pytest.mark.parametrize("variant", [None, False])
def test_temporal_usage_blunt_flag_disable_does_not_capture_or_consume(
    notice_harness, variant, capsys
):
    config, telemetry = notice_harness
    configure_flag(telemetry, variant, temporal_usage_payload())

    notices.display_temporal_usage_notice(MagicMock(), "sync", "search", "query", "relative_phrase")

    assert capsys.readouterr().err == ""
    telemetry.capture_event.assert_not_called()
    assert config.get("notice_state") is None


def test_temporal_usage_telemetry_disabled_does_not_touch_posthog_or_state(monkeypatch, capsys):
    load_config = MagicMock(return_value={})
    write_config = MagicMock()
    get_telemetry = MagicMock()

    monkeypatch.setattr(notices, "_load_config", load_config)
    monkeypatch.setattr(notices, "_write_config", write_config)
    monkeypatch.setattr(notices.telemetry_module, "MEM0_TELEMETRY", False)
    monkeypatch.setattr(notices.telemetry_module, "_get_oss_telemetry", get_telemetry)

    notices.display_temporal_usage_notice(MagicMock(), "sync", "search", "query", "relative_phrase")

    load_config.assert_not_called()
    write_config.assert_not_called()
    get_telemetry.assert_not_called()
    assert capsys.readouterr().err == ""


def test_temporal_usage_cap_blocks_before_posthog_eval(notice_harness, capsys):
    config, telemetry = notice_harness
    configure_flag(telemetry, "displayed", temporal_usage_payload())

    for _ in range(notices.TEMPORAL_USAGE_CAP):
        notices.display_temporal_usage_notice(MagicMock(), "sync", "search", "query", "relative_phrase")

    notices.display_temporal_usage_notice(MagicMock(), "sync", "search", "query", "relative_phrase")

    assert capsys.readouterr().err == "Temporal usage CTA\n" * notices.TEMPORAL_USAGE_CAP
    assert telemetry.posthog.evaluate_flags.call_count == notices.TEMPORAL_USAGE_CAP
    assert telemetry.capture_event.call_count == notices.TEMPORAL_USAGE_CAP
    assert len(config["notice_state"]["temporal_usage"]["events"]) == notices.TEMPORAL_USAGE_CAP


def test_temporal_usage_cap_ignores_old_entries(notice_harness, capsys):
    config, telemetry = notice_harness
    old_time = datetime.now(timezone.utc) - notices.TEMPORAL_USAGE_WINDOW - timedelta(days=1)
    config["notice_state"] = {
        "temporal_usage": {
            "events": [
                {"evaluated_at": old_time.isoformat(), "variant": "displayed"}
                for _ in range(notices.TEMPORAL_USAGE_CAP)
            ]
        }
    }
    configure_flag(telemetry, "displayed", temporal_usage_payload())

    notices.display_temporal_usage_notice(MagicMock(), "sync", "search", "query", "relative_phrase")

    assert capsys.readouterr().err == "Temporal usage CTA\n"
    assert telemetry.capture_event.call_count == 1
    assert len(config["notice_state"]["temporal_usage"]["events"]) == 1


def test_temporal_usage_props_do_not_include_raw_user_inputs(notice_harness):
    _, telemetry = notice_harness
    configure_flag(telemetry, "displayed", temporal_usage_payload(copy="safe copy"))

    notices.display_temporal_usage_notice(MagicMock(), "sync", "search", "query", "relative_phrase")

    props = telemetry.capture_event.call_args.args[1]
    assert "what happened last week" not in str(props)
    assert "2025-04-09" not in str(props)
    assert date.today().isoformat() not in str(props)


def test_scale_threshold_top_k_detection():
    assert notices.detect_scale_threshold_from_top_k(49) is None
    assert notices.detect_scale_threshold_from_top_k(50) == (
        "top_k",
        "high_top_k",
        50,
        None,
        notices.SCALE_TOP_K_THRESHOLD,
    )


def test_scale_threshold_displayed_logs_and_captures_event(notice_harness, capsys):
    config, telemetry = notice_harness
    flags = configure_flag(telemetry, "displayed", scale_payload())

    notices.display_scale_threshold_notice(
        MagicMock(),
        "sync",
        "search",
        "top_k",
        "high_top_k",
        top_k=50,
        threshold=notices.SCALE_TOP_K_THRESHOLD,
    )

    assert capsys.readouterr().err == "Scale top 50\n"
    telemetry.posthog.evaluate_flags.assert_called_once_with("oss-user", flag_keys=[notices.FLAG_KEY])
    telemetry.capture_event.assert_called_once()
    event_name, props = telemetry.capture_event.call_args.args
    assert event_name == notices.NOTICE_EVENT
    assert props["notice_id"] == "scale_threshold"
    assert props["notice_type"] == "log_line"
    assert props["variant"] == "displayed"
    assert props["displayed"] is True
    assert props["payload"] == "Scale top 50"
    assert props["bypass_reason"] is None
    assert props["disabled_reason"] is None
    assert props["notice_config_found"] is True
    assert props["sync_type"] == "sync"
    assert props["trigger_function"] == "search"
    assert props["trigger_source"] == "top_k"
    assert props["trigger_reason"] == "high_top_k"
    assert props["top_k"] == 50
    assert props["memory_count"] is None
    assert props["threshold"] == notices.SCALE_TOP_K_THRESHOLD
    assert telemetry.capture_event.call_args.kwargs["flags"] is flags
    assert len(config["notice_state"]["scale_threshold"]["events"]) == 1


def test_scale_threshold_holdout_is_silent_but_captures_event(notice_harness, capsys):
    _, telemetry = notice_harness
    configure_flag(telemetry, "holdout", scale_payload())

    notices.display_scale_threshold_notice(
        MagicMock(),
        "sync",
        "get_all",
        "top_k",
        "high_top_k",
        top_k=50,
        threshold=notices.SCALE_TOP_K_THRESHOLD,
    )

    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is False
    assert props["bypass_reason"] == "holdout"
    assert props["trigger_function"] == "get_all"


@pytest.mark.parametrize(
    ("payload", "expected_reason", "expected_found"),
    [
        ({}, "missing_notice_config", False),
        ({"notices": {}}, "missing_notice_config", False),
        ({"notices": "not-an-object"}, "missing_notice_config", False),
        (scale_payload(top_k_copy=None), "missing_copy", True),
        (scale_payload(enabled=False, top_k_copy="hidden"), "payload_disabled", True),
    ],
)
def test_scale_threshold_bad_or_disabled_payload_is_silent_and_safe(
    notice_harness, payload, expected_reason, expected_found, capsys
):
    _, telemetry = notice_harness
    configure_flag(telemetry, "displayed", payload)

    notices.display_scale_threshold_notice(
        MagicMock(),
        "sync",
        "search",
        "top_k",
        "high_top_k",
        top_k=50,
        threshold=notices.SCALE_TOP_K_THRESHOLD,
    )

    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is False
    assert props["bypass_reason"] == expected_reason
    assert props["notice_config_found"] is expected_found


@pytest.mark.parametrize("variant", [None, False])
def test_scale_threshold_blunt_flag_disable_does_not_capture_or_consume(
    notice_harness, variant, capsys
):
    config, telemetry = notice_harness
    configure_flag(telemetry, variant, scale_payload())

    notices.display_scale_threshold_notice(
        MagicMock(),
        "sync",
        "search",
        "top_k",
        "high_top_k",
        top_k=50,
        threshold=notices.SCALE_TOP_K_THRESHOLD,
    )

    assert capsys.readouterr().err == ""
    telemetry.capture_event.assert_not_called()
    assert config.get("notice_state") is None


def test_scale_threshold_telemetry_disabled_does_not_touch_posthog_or_state(monkeypatch, capsys):
    load_config = MagicMock(return_value={})
    write_config = MagicMock()
    get_telemetry = MagicMock()

    monkeypatch.setattr(notices, "_load_config", load_config)
    monkeypatch.setattr(notices, "_write_config", write_config)
    monkeypatch.setattr(notices.telemetry_module, "MEM0_TELEMETRY", False)
    monkeypatch.setattr(notices.telemetry_module, "_get_oss_telemetry", get_telemetry)

    notices.display_scale_threshold_notice(
        MagicMock(),
        "sync",
        "search",
        "top_k",
        "high_top_k",
        top_k=50,
        threshold=notices.SCALE_TOP_K_THRESHOLD,
    )

    load_config.assert_not_called()
    write_config.assert_not_called()
    get_telemetry.assert_not_called()
    assert capsys.readouterr().err == ""


def test_scale_threshold_posthog_failure_does_not_consume_cap(notice_harness, capsys):
    config, telemetry = notice_harness
    telemetry.posthog.evaluate_flags.side_effect = RuntimeError("network unavailable")

    notices.display_scale_threshold_notice(
        MagicMock(),
        "sync",
        "search",
        "top_k",
        "high_top_k",
        top_k=50,
        threshold=notices.SCALE_TOP_K_THRESHOLD,
    )

    assert capsys.readouterr().err == ""
    telemetry.capture_event.assert_not_called()
    assert config.get("notice_state") is None


def test_scale_threshold_cap_blocks_before_posthog_eval(notice_harness, capsys):
    config, telemetry = notice_harness
    configure_flag(telemetry, "displayed", scale_payload())

    for _ in range(notices.SCALE_THRESHOLD_CAP):
        notices.display_scale_threshold_notice(
            MagicMock(),
            "sync",
            "search",
            "top_k",
            "high_top_k",
            top_k=50,
            threshold=notices.SCALE_TOP_K_THRESHOLD,
        )

    notices.display_scale_threshold_notice(
        MagicMock(),
        "sync",
        "search",
        "top_k",
        "high_top_k",
        top_k=50,
        threshold=notices.SCALE_TOP_K_THRESHOLD,
    )

    assert capsys.readouterr().err == "Scale top 50\n" * notices.SCALE_THRESHOLD_CAP
    assert telemetry.posthog.evaluate_flags.call_count == notices.SCALE_THRESHOLD_CAP
    assert telemetry.capture_event.call_count == notices.SCALE_THRESHOLD_CAP
    assert len(config["notice_state"]["scale_threshold"]["events"]) == notices.SCALE_THRESHOLD_CAP


def test_scale_threshold_cap_ignores_old_entries(notice_harness, capsys):
    config, telemetry = notice_harness
    old_time = datetime.now(timezone.utc) - notices.SCALE_THRESHOLD_WINDOW - timedelta(days=1)
    config["notice_state"] = {
        "scale_threshold": {
            "events": [
                {"evaluated_at": old_time.isoformat(), "variant": "displayed"}
                for _ in range(notices.SCALE_THRESHOLD_CAP)
            ]
        }
    }
    configure_flag(telemetry, "displayed", scale_payload())

    notices.display_scale_threshold_notice(
        MagicMock(),
        "sync",
        "search",
        "top_k",
        "high_top_k",
        top_k=50,
        threshold=notices.SCALE_TOP_K_THRESHOLD,
    )

    assert capsys.readouterr().err == "Scale top 50\n"
    assert telemetry.capture_event.call_count == 1
    assert len(config["notice_state"]["scale_threshold"]["events"]) == 1


def test_scale_threshold_add_counter_counts_only_add_events(notice_harness):
    config, _ = notice_harness
    config["notice_state"] = {"scale_threshold": {"local_add_count": 1999}}
    memory = MagicMock()
    memory.vector_store = object()

    notice = notices.detect_scale_threshold_from_add_result(
        memory,
        [{"event": "UPDATE"}, {"event": "ADD"}, {"event": "DELETE"}],
    )

    assert notice == (
        "memory_count",
        "memory_count_threshold",
        None,
        notices.SCALE_MEMORY_COUNT_THRESHOLD,
        notices.SCALE_MEMORY_COUNT_THRESHOLD,
    )
    assert config["notice_state"]["scale_threshold"]["local_add_count"] == 2000


def test_scale_threshold_memory_count_event_marks_threshold_evaluated(notice_harness, capsys):
    config, telemetry = notice_harness
    configure_flag(telemetry, "displayed", scale_payload())

    notices.display_scale_threshold_notice(
        MagicMock(),
        "sync",
        "add",
        "memory_count",
        "memory_count_threshold",
        memory_count=2000,
        threshold=notices.SCALE_MEMORY_COUNT_THRESHOLD,
    )

    assert capsys.readouterr().err == "Scale count 2000\n"
    assert config["notice_state"]["scale_threshold"]["memory_count_threshold_evaluated"] is True
    props = telemetry.capture_event.call_args.args[1]
    assert props["memory_count"] == 2000
    assert props["threshold"] == notices.SCALE_MEMORY_COUNT_THRESHOLD


def test_scale_threshold_provider_count_helpers_are_safe():
    class Info:
        points_count = 2200

    class CountStore:
        def count(self):
            return 2100

    class FallbackStore:
        def count(self):
            raise RuntimeError("count unavailable")

        def col_info(self):
            return {"count": 2300}

    memory = MagicMock()
    memory.vector_store = CountStore()
    assert notices._get_provider_memory_count(memory) == 2100

    memory.vector_store = FallbackStore()
    assert notices._get_provider_memory_count(memory) == 2300

    assert notices._extract_count({"points_count": 2400}) == 2400
    assert notices._extract_count(Info()) == 2200
    assert notices._extract_count({"count": -1}) is None


def test_scale_threshold_props_do_not_include_raw_user_inputs(notice_harness):
    _, telemetry = notice_harness
    configure_flag(telemetry, "displayed", scale_payload(top_k_copy="safe copy {top_k}"))

    notices.display_scale_threshold_notice(
        MagicMock(),
        "sync",
        "search",
        "top_k",
        "high_top_k",
        top_k=50,
        threshold=notices.SCALE_TOP_K_THRESHOLD,
    )

    props = telemetry.capture_event.call_args.args[1]
    assert "favorite drink" not in str(props)
    assert "user_id" not in str(props)
    assert "green tea" not in str(props)


def test_async_scale_threshold_wrapper_uses_shared_helper(monkeypatch):
    calls = []

    def display(memory_instance, sync_type, trigger_function, trigger_source, trigger_reason, top_k, memory_count, threshold):
        calls.append(
            (memory_instance, sync_type, trigger_function, trigger_source, trigger_reason, top_k, memory_count, threshold)
        )

    memory = MagicMock()
    monkeypatch.setattr(notices, "display_scale_threshold_notice", display)

    asyncio.run(
        notices.display_scale_threshold_notice_async(
            memory,
            "async",
            "search",
            "top_k",
            "high_top_k",
            top_k=50,
            threshold=notices.SCALE_TOP_K_THRESHOLD,
        )
    )

    assert calls == [
        (
            memory,
            "async",
            "search",
            "top_k",
            "high_top_k",
            50,
            None,
            notices.SCALE_TOP_K_THRESHOLD,
        )
    ]


def test_notice_priority_temporal_usage_beats_scale_and_first_run(monkeypatch):
    from mem0.memory import main as memory_main

    memory = memory_main.Memory.__new__(memory_main.Memory)
    memory.api_version = "v1.1"
    memory.reranker = None
    memory._search_vector_store = MagicMock(return_value=[])
    calls = []

    monkeypatch.setattr(memory_main, "capture_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", lambda *args: calls.append("temporal"))
    monkeypatch.setattr(memory_main, "display_scale_threshold_notice", lambda *args: calls.append("scale"))
    monkeypatch.setattr(memory_main, "display_first_run_notice", lambda *args: calls.append("first_run"))

    memory_main.Memory.search(
        memory,
        "what happened last week?",
        top_k=50,
        filters={"user_id": "u1"},
    )

    assert calls == ["temporal"]


def test_notice_priority_scale_beats_first_run(monkeypatch):
    from mem0.memory import main as memory_main

    memory = memory_main.Memory.__new__(memory_main.Memory)
    memory.api_version = "v1.1"
    memory.reranker = None
    memory._search_vector_store = MagicMock(return_value=[])
    calls = []

    monkeypatch.setattr(memory_main, "capture_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(memory_main, "display_scale_threshold_notice", lambda *args: calls.append("scale"))
    monkeypatch.setattr(memory_main, "display_first_run_notice", lambda *args: calls.append("first_run"))

    memory_main.Memory.search(
        memory,
        "favorite drink",
        top_k=50,
        filters={"user_id": "u1"},
    )

    assert calls == ["scale"]
