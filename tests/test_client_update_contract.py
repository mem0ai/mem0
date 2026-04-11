import importlib
import inspect
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _load_client_classes():
    repo_root = Path(__file__).resolve().parents[1]
    mem0_root = repo_root / "mem0"

    mem0_pkg = ModuleType("mem0")
    mem0_pkg.__path__ = [str(mem0_root)]

    client_pkg = ModuleType("mem0.client")
    client_pkg.__path__ = [str(mem0_root / "client")]

    memory_pkg = ModuleType("mem0.memory")
    memory_pkg.__path__ = [str(mem0_root / "memory")]

    project_module = ModuleType("mem0.client.project")
    project_module.Project = type("Project", (), {})
    project_module.AsyncProject = type("AsyncProject", (), {})

    setup_module = ModuleType("mem0.memory.setup")
    setup_module.get_user_id = lambda: "user"
    setup_module.setup_config = lambda: None

    telemetry_module = ModuleType("mem0.memory.telemetry")
    telemetry_module.capture_client_event = lambda *args, **kwargs: None

    modules = {
        "mem0": mem0_pkg,
        "mem0.client": client_pkg,
        "mem0.memory": memory_pkg,
        "mem0.client.project": project_module,
        "mem0.memory.setup": setup_module,
        "mem0.memory.telemetry": telemetry_module,
    }

    with patch.dict(sys.modules, modules):
        sys.modules.pop("mem0.client.main", None)
        client_main = importlib.import_module("mem0.client.main")
        return client_main.AsyncMemoryClient, client_main.MemoryClient, client_main


def test_sync_update_signature_drops_timestamp():
    _, MemoryClient, _ = _load_client_classes()
    assert "timestamp" not in inspect.signature(MemoryClient.update).parameters


def test_sync_update_metadata_only_payload():
    _, MemoryClient, client_main = _load_client_classes()
    client = object.__new__(MemoryClient)
    client.client = Mock()
    client._prepare_params = Mock(return_value={})

    response = Mock()
    response.json.return_value = {"message": "Memory updated"}
    client.client.put.return_value = response

    with patch.object(client_main, "capture_client_event"):
        result = MemoryClient.update(client, "mem-1", metadata={"category": "sports"})

    client.client.put.assert_called_once_with(
        "/v1/memories/mem-1/",
        json={"metadata": {"category": "sports"}},
        params={},
    )
    assert result == {"message": "Memory updated"}


def test_sync_update_requires_text_or_metadata():
    _, MemoryClient, _ = _load_client_classes()
    client = object.__new__(MemoryClient)

    with pytest.raises(ValueError, match="At least one of text or metadata must be provided for update."):
        MemoryClient.update(client, "mem-1")


def test_async_update_signature_drops_timestamp():
    AsyncMemoryClient, _, _ = _load_client_classes()
    assert "timestamp" not in inspect.signature(AsyncMemoryClient.update).parameters


@pytest.mark.asyncio
async def test_async_update_metadata_only_payload():
    AsyncMemoryClient, _, client_main = _load_client_classes()
    client = object.__new__(AsyncMemoryClient)
    client.async_client = AsyncMock()
    client._prepare_params = Mock(return_value={})

    response = Mock()
    response.json.return_value = {"message": "Memory updated"}
    client.async_client.put.return_value = response

    with patch.object(client_main, "capture_client_event"):
        result = await AsyncMemoryClient.update(client, "mem-1", metadata={"category": "sports"})

    client.async_client.put.assert_awaited_once_with(
        "/v1/memories/mem-1/",
        json={"metadata": {"category": "sports"}},
        params={},
    )
    assert result == {"message": "Memory updated"}


@pytest.mark.asyncio
async def test_async_update_requires_text_or_metadata():
    AsyncMemoryClient, _, _ = _load_client_classes()
    client = object.__new__(AsyncMemoryClient)

    with pytest.raises(ValueError, match="At least one of text or metadata must be provided for update."):
        await AsyncMemoryClient.update(client, "mem-1")
