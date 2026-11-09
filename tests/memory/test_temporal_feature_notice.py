import pytest

from mem0.memory import main as memory_main
from mem0.memory.main import AsyncMemory, Memory


def test_sync_add_timestamp_raises_before_validation(monkeypatch):
    calls = []

    def get_error(sync_type, trigger_function, trigger_parameter):
        calls.append((sync_type, trigger_function, trigger_parameter))
        return "blocked timestamp"

    monkeypatch.setattr(memory_main, "get_temporal_feature_error_message", get_error)

    with pytest.raises(ValueError, match="blocked timestamp"):
        Memory.add(Memory.__new__(Memory), "hello", timestamp=123)

    assert calls == [("sync", "add", "timestamp")]


def test_sync_search_reference_date_raises_before_validation(monkeypatch):
    calls = []

    def get_error(sync_type, trigger_function, trigger_parameter):
        calls.append((sync_type, trigger_function, trigger_parameter))
        return "blocked reference date"

    monkeypatch.setattr(memory_main, "get_temporal_feature_error_message", get_error)

    with pytest.raises(ValueError, match="blocked reference date"):
        Memory.search(Memory.__new__(Memory), "what happened last week?", reference_date="2025-03-21")

    assert calls == [("sync", "search", "reference_date")]


@pytest.mark.asyncio
async def test_async_add_timestamp_raises_before_validation(monkeypatch):
    calls = []

    async def get_error(sync_type, trigger_function, trigger_parameter):
        calls.append((sync_type, trigger_function, trigger_parameter))
        return "blocked async timestamp"

    monkeypatch.setattr(memory_main, "get_temporal_feature_error_message_async", get_error)

    with pytest.raises(ValueError, match="blocked async timestamp"):
        await AsyncMemory.add(AsyncMemory.__new__(AsyncMemory), "hello", timestamp=123)

    assert calls == [("async", "add", "timestamp")]


@pytest.mark.asyncio
async def test_async_search_reference_date_raises_before_validation(monkeypatch):
    calls = []

    async def get_error(sync_type, trigger_function, trigger_parameter):
        calls.append((sync_type, trigger_function, trigger_parameter))
        return "blocked async reference date"

    monkeypatch.setattr(memory_main, "get_temporal_feature_error_message_async", get_error)

    with pytest.raises(ValueError, match="blocked async reference date"):
        await AsyncMemory.search(
            AsyncMemory.__new__(AsyncMemory),
            "what happened last week?",
            reference_date="2025-03-21",
        )

    assert calls == [("async", "search", "reference_date")]


def test_sync_add_without_timestamp_does_not_call_temporal_feature_notice(monkeypatch):
    get_error = monkeypatch.setattr(
        memory_main,
        "get_temporal_feature_error_message",
        lambda *args: pytest.fail("temporal feature notice should not run"),
    )

    with pytest.raises(Exception, match="At least one of 'user_id', 'agent_id', or 'run_id'"):
        Memory.add(Memory.__new__(Memory), "hello")

    assert get_error is None


def test_sync_search_without_reference_date_does_not_call_temporal_feature_notice(monkeypatch):
    get_error = monkeypatch.setattr(
        memory_main,
        "get_temporal_feature_error_message",
        lambda *args: pytest.fail("temporal feature notice should not run"),
    )

    with pytest.raises(ValueError, match="filters must contain"):
        Memory.search(Memory.__new__(Memory), "hello")

    assert get_error is None
