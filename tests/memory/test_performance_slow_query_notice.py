from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock

import pytest

from mem0.memory import notices
from mem0.memory import main as memory_main
from mem0.memory.main import AsyncMemory, Memory


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
    notices._performance_slow_query_capacity_reached_in_process = False
    yield
    notices._performance_slow_query_capacity_reached_in_process = False


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


def performance_payload(copy="Performance CTA", enabled=True, notice_type="log_line"):
    payload = {
        "notices": {
            "performance_slow_query": {
                "enabled": enabled,
                "notice_type": notice_type,
            }
        }
    }
    if copy is not None:
        payload["notices"]["performance_slow_query"]["copy"] = copy
    return payload


def make_sync_memory(search_results=None):
    memory = Memory.__new__(Memory)
    memory.api_version = "v1.1"
    memory.reranker = None
    memory._search_vector_store = MagicMock(return_value=search_results or [])
    return memory


def make_async_memory(search_results=None):
    memory = AsyncMemory.__new__(AsyncMemory)
    memory.api_version = "v1.1"
    memory.reranker = None
    memory._search_vector_store = AsyncMock(return_value=search_results or [])
    return memory


def test_sync_slow_search_triggers_performance_notice_after_success(monkeypatch):
    results = [{"id": "m1"}, {"id": "m2"}]
    memory = make_sync_memory(search_results=results)
    performance_notice = MagicMock()
    temporal_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 102.1]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    result = Memory.search(memory, "favorite drink", filters={"user_id": "u1"}, top_k=3)

    assert result == {"results": results}
    memory._search_vector_store.assert_called_once()
    performance_notice.assert_called_once_with(memory, "sync", "search", pytest.approx(2.1), 3, 2)
    temporal_notice.assert_not_called()
    first_run_notice.assert_not_called()


def test_sync_fast_search_uses_first_run_notice(monkeypatch):
    memory = make_sync_memory()
    performance_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 101.0]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", MagicMock())
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    Memory.search(memory, "favorite drink", filters={"user_id": "u1"})

    performance_notice.assert_not_called()
    first_run_notice.assert_called_once_with(memory, "sync", "search")


def test_sync_failed_search_does_not_trigger_performance_notice(monkeypatch):
    memory = make_sync_memory()
    memory._search_vector_store.side_effect = RuntimeError("search failure")
    performance_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(return_value=100.0))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", MagicMock())
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    with pytest.raises(RuntimeError, match="search failure"):
        Memory.search(memory, "favorite drink", filters={"user_id": "u1"})

    performance_notice.assert_not_called()
    first_run_notice.assert_not_called()


def test_sync_temporal_usage_takes_precedence_over_slow_search(monkeypatch):
    memory = make_sync_memory()
    performance_notice = MagicMock()
    temporal_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 102.1]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    Memory.search(memory, "what happened last week?", filters={"user_id": "u1"})

    temporal_notice.assert_called_once_with(memory, "sync", "search", "query", "relative_phrase")
    performance_notice.assert_not_called()
    first_run_notice.assert_not_called()


def test_sync_scale_takes_precedence_over_slow_search(monkeypatch):
    memory = make_sync_memory()
    performance_notice = MagicMock()
    scale_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 102.1]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice", performance_notice)
    monkeypatch.setattr(memory_main, "display_scale_threshold_notice", scale_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    Memory.search(memory, "favorite drink", filters={"user_id": "u1"}, top_k=50)

    scale_notice.assert_called_once_with(
        memory,
        "sync",
        "search",
        "top_k",
        "high_top_k",
        50,
        None,
        notices.SCALE_TOP_K_THRESHOLD,
    )
    performance_notice.assert_not_called()
    first_run_notice.assert_not_called()


@pytest.mark.asyncio
async def test_async_slow_search_triggers_performance_notice_after_success(monkeypatch):
    results = [{"id": "m1"}]
    memory = make_async_memory(search_results=results)
    performance_notice = AsyncMock()
    temporal_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 102.1]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice_async", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice_async", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    result = await AsyncMemory.search(memory, "favorite drink", filters={"user_id": "u1"}, top_k=4)

    assert result == {"results": results}
    memory._search_vector_store.assert_awaited_once()
    performance_notice.assert_awaited_once_with(memory, "async", "search", pytest.approx(2.1), 4, 1)
    temporal_notice.assert_not_awaited()
    first_run_notice.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_fast_search_uses_first_run_notice(monkeypatch):
    memory = make_async_memory()
    performance_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 101.0]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice_async", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice_async", AsyncMock())
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    await AsyncMemory.search(memory, "favorite drink", filters={"user_id": "u1"})

    performance_notice.assert_not_awaited()
    first_run_notice.assert_awaited_once_with(memory, "async", "search")


@pytest.mark.asyncio
async def test_async_failed_search_does_not_trigger_performance_notice(monkeypatch):
    memory = make_async_memory()
    memory._search_vector_store.side_effect = RuntimeError("search failure")
    performance_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(return_value=100.0))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice_async", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice_async", AsyncMock())
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    with pytest.raises(RuntimeError, match="search failure"):
        await AsyncMemory.search(memory, "favorite drink", filters={"user_id": "u1"})

    performance_notice.assert_not_awaited()
    first_run_notice.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_temporal_usage_takes_precedence_over_slow_search(monkeypatch):
    memory = make_async_memory()
    performance_notice = AsyncMock()
    temporal_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 102.1]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice_async", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice_async", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    await AsyncMemory.search(memory, "what happened last week?", filters={"user_id": "u1"})

    temporal_notice.assert_awaited_once_with(memory, "async", "search", "query", "relative_phrase")
    performance_notice.assert_not_awaited()
    first_run_notice.assert_not_awaited()


def test_performance_slow_query_displayed_logs_and_captures_event(notice_harness, capsys):
    config, telemetry = notice_harness
    flags = configure_flag(telemetry, "displayed", performance_payload())

    notices.display_performance_slow_query_notice(
        MagicMock(),
        "sync",
        "search",
        elapsed_seconds=2.345,
        top_k=20,
        result_count=7,
    )

    assert capsys.readouterr().err == "Performance CTA\n"
    telemetry.posthog.evaluate_flags.assert_called_once_with("oss-user", flag_keys=[notices.FLAG_KEY])
    telemetry.capture_event.assert_called_once()
    event_name, props = telemetry.capture_event.call_args.args
    assert event_name == notices.NOTICE_EVENT
    assert props["notice_id"] == "performance_slow_query"
    assert props["notice_type"] == "log_line"
    assert props["variant"] == "displayed"
    assert props["displayed"] is True
    assert props["payload"] == "Performance CTA"
    assert props["bypass_reason"] is None
    assert props["disabled_reason"] is None
    assert props["notice_config_found"] is True
    assert props["sync_type"] == "sync"
    assert props["trigger_function"] == "search"
    assert props["trigger_reason"] == "slow_query"
    assert props["elapsed_ms"] == 2345
    assert props["threshold_ms"] == 2000
    assert props["top_k"] == 20
    assert props["result_count"] == 7
    assert telemetry.capture_event.call_args.kwargs["flags"] is flags
    assert len(config["notice_state"]["performance_slow_query"]["events"]) == 1


def test_performance_slow_query_holdout_is_silent_but_captures_event(notice_harness, capsys):
    _, telemetry = notice_harness
    configure_flag(telemetry, "holdout", performance_payload())

    notices.display_performance_slow_query_notice(
        MagicMock(),
        "sync",
        "search",
        elapsed_seconds=2.1,
        top_k=10,
        result_count=2,
    )

    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is False
    assert props["bypass_reason"] == "holdout"
    assert props["trigger_reason"] == "slow_query"


@pytest.mark.parametrize(
    ("payload", "expected_reason", "expected_found"),
    [
        ({}, "missing_notice_config", False),
        ({"notices": {}}, "missing_notice_config", False),
        ({"notices": "not-an-object"}, "missing_notice_config", False),
        (performance_payload(copy=None), "missing_copy", True),
        (performance_payload(enabled=False, copy="hidden"), "payload_disabled", True),
    ],
)
def test_performance_slow_query_bad_or_disabled_payload_is_silent_and_safe(
    notice_harness, payload, expected_reason, expected_found, capsys
):
    _, telemetry = notice_harness
    configure_flag(telemetry, "displayed", payload)

    notices.display_performance_slow_query_notice(
        MagicMock(),
        "sync",
        "search",
        elapsed_seconds=2.1,
        top_k=10,
        result_count=2,
    )

    assert capsys.readouterr().err == ""
    props = telemetry.capture_event.call_args.args[1]
    assert props["displayed"] is False
    assert props["bypass_reason"] == expected_reason
    assert props["notice_config_found"] is expected_found


@pytest.mark.parametrize("variant", [None, False])
def test_performance_slow_query_blunt_flag_disable_does_not_capture_or_consume(
    notice_harness, variant, capsys
):
    config, telemetry = notice_harness
    configure_flag(telemetry, variant, performance_payload())

    notices.display_performance_slow_query_notice(
        MagicMock(),
        "sync",
        "search",
        elapsed_seconds=2.1,
        top_k=10,
        result_count=2,
    )

    assert capsys.readouterr().err == ""
    telemetry.capture_event.assert_not_called()
    assert config.get("notice_state") is None


def test_performance_slow_query_telemetry_disabled_does_not_touch_posthog_or_state(
    monkeypatch, capsys
):
    load_config = MagicMock(return_value={})
    write_config = MagicMock()
    get_telemetry = MagicMock()

    monkeypatch.setattr(notices, "_load_config", load_config)
    monkeypatch.setattr(notices, "_write_config", write_config)
    monkeypatch.setattr(notices.telemetry_module, "MEM0_TELEMETRY", False)
    monkeypatch.setattr(notices.telemetry_module, "_get_oss_telemetry", get_telemetry)

    notices.display_performance_slow_query_notice(
        MagicMock(),
        "sync",
        "search",
        elapsed_seconds=2.1,
        top_k=10,
        result_count=2,
    )

    load_config.assert_not_called()
    write_config.assert_not_called()
    get_telemetry.assert_not_called()
    assert capsys.readouterr().err == ""


def test_performance_slow_query_cap_blocks_before_posthog_eval(notice_harness, capsys):
    config, telemetry = notice_harness
    configure_flag(telemetry, "displayed", performance_payload())

    for _ in range(notices.PERFORMANCE_SLOW_QUERY_CAP):
        notices.display_performance_slow_query_notice(
            MagicMock(),
            "sync",
            "search",
            elapsed_seconds=2.1,
            top_k=10,
            result_count=2,
        )

    notices.display_performance_slow_query_notice(
        MagicMock(),
        "sync",
        "search",
        elapsed_seconds=2.1,
        top_k=10,
        result_count=2,
    )

    assert capsys.readouterr().err == "Performance CTA\n" * notices.PERFORMANCE_SLOW_QUERY_CAP
    assert telemetry.posthog.evaluate_flags.call_count == notices.PERFORMANCE_SLOW_QUERY_CAP
    assert telemetry.capture_event.call_count == notices.PERFORMANCE_SLOW_QUERY_CAP
    assert len(config["notice_state"]["performance_slow_query"]["events"]) == notices.PERFORMANCE_SLOW_QUERY_CAP


def test_performance_slow_query_props_do_not_include_raw_user_inputs(notice_harness):
    _, telemetry = notice_harness
    configure_flag(telemetry, "displayed", performance_payload(copy="safe copy"))

    notices.display_performance_slow_query_notice(
        MagicMock(),
        "sync",
        "search",
        elapsed_seconds=2.1,
        top_k=10,
        result_count=2,
    )

    props = telemetry.capture_event.call_args.args[1]
    assert "favorite drink" not in str(props)
    assert "user_id" not in str(props)
    assert "green tea" not in str(props)
