import pytest

from mem0.memory import main as memory_main
from mem0.memory.main import AsyncMemory, Memory


def test_sync_project_update_decay_true_raises_with_notice_message(monkeypatch):
    calls = []

    def get_error(sync_type, trigger_function, trigger_parameter):
        calls.append((sync_type, trigger_function, trigger_parameter))
        return "blocked decay"

    monkeypatch.setattr(memory_main, "get_decay_feature_error_message", get_error)

    with pytest.raises(ValueError, match="blocked decay"):
        Memory.__new__(Memory).project.update(decay=True)

    assert calls == [("sync", "project.update", "decay")]


@pytest.mark.asyncio
async def test_async_project_update_decay_true_raises_with_notice_message(monkeypatch):
    calls = []

    async def get_error(sync_type, trigger_function, trigger_parameter):
        calls.append((sync_type, trigger_function, trigger_parameter))
        return "blocked async decay"

    monkeypatch.setattr(memory_main, "get_decay_feature_error_message_async", get_error)

    with pytest.raises(ValueError, match="blocked async decay"):
        await AsyncMemory.__new__(AsyncMemory).project.update(decay=True)

    assert calls == [("async", "project.update", "decay")]


@pytest.mark.parametrize("kwargs", [{}, {"decay": False}])
def test_sync_project_update_non_trigger_raises_plain_error_without_notice(monkeypatch, kwargs):
    monkeypatch.setattr(
        memory_main,
        "get_decay_feature_error_message",
        lambda *args: pytest.fail("decay feature notice should not run"),
    )

    with pytest.raises(ValueError, match="Project updates are not supported by the OSS Memory SDK."):
        Memory.__new__(Memory).project.update(**kwargs)


@pytest.mark.asyncio
@pytest.mark.parametrize("kwargs", [{}, {"decay": False}])
async def test_async_project_update_non_trigger_raises_plain_error_without_notice(monkeypatch, kwargs):
    monkeypatch.setattr(
        memory_main,
        "get_decay_feature_error_message_async",
        lambda *args: pytest.fail("decay feature notice should not run"),
    )

    with pytest.raises(ValueError, match="Project updates are not supported by the OSS Memory SDK."):
        await AsyncMemory.__new__(AsyncMemory).project.update(**kwargs)
