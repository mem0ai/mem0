"""Tests for mem0.memory.synaptic_bridge.SynapticBridge."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import mem0.memory.synaptic_bridge as bridge_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_system_mock() -> MagicMock:
    """Return a mock that looks like SynapticMemorySystem."""
    m = MagicMock()
    m.__aenter__ = AsyncMock(return_value=m)
    m.__aexit__ = AsyncMock(return_value=None)
    m.add_memory = AsyncMock()
    m.on_search = AsyncMock()
    return m


def _bridge_with_mock_system(system_mock: MagicMock) -> "bridge_mod.SynapticBridge":
    """Create a SynapticBridge whose _system is pre-set to system_mock.

    Bypasses _ensure() so tests are not sensitive to the module-level
    _SYNAPTIC_AVAILABLE flag.
    """
    bridge = bridge_mod.SynapticBridge.__new__(bridge_mod.SynapticBridge)
    bridge._db_dir = None
    bridge._lock = asyncio.Lock()
    bridge._system = system_mock
    return bridge


# ---------------------------------------------------------------------------
# test_bridge_disabled_when_synaptic_unavailable
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_disabled_when_synaptic_unavailable():
    """on_add and on_search are no-ops when synaptic is not importable."""
    with patch.object(bridge_mod, "_SYNAPTIC_AVAILABLE", False):
        bridge = bridge_mod.SynapticBridge()
        await bridge.on_add("mem1", "some content")

        results = [{"id": "mem1", "memory": "content"}]
        returned = await bridge.on_search("query", results)
        assert returned is results
        assert bridge._system is None


# ---------------------------------------------------------------------------
# test_bridge_on_add_calls_system
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_on_add_calls_system():
    """on_add delegates to system.add_memory with correct arguments."""
    system_mock = _make_system_mock()
    bridge = _bridge_with_mock_system(system_mock)

    ctx = [{"id": "ctx1", "memory": "ctx content"}]
    await bridge.on_add("mem-42", "hello world", context_memories=ctx)

    system_mock.add_memory.assert_awaited_once_with(
        memory_id="mem-42",
        content="hello world",
        context_memories=ctx,
    )


# ---------------------------------------------------------------------------
# test_bridge_on_search_calls_system
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_on_search_calls_system():
    """on_search delegates to system.on_search and passes results through unchanged."""
    system_mock = _make_system_mock()
    bridge = _bridge_with_mock_system(system_mock)

    results = [{"id": "r1"}, {"id": "r2"}]
    returned = await bridge.on_search("my query", results)

    system_mock.on_search.assert_awaited_once_with(query="my query", results=results)
    assert returned is results


# ---------------------------------------------------------------------------
# test_bridge_on_add_swallows_errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_on_add_swallows_errors():
    """on_add catches exceptions from the system and does not propagate them."""
    system_mock = _make_system_mock()
    system_mock.add_memory = AsyncMock(side_effect=RuntimeError("boom"))
    bridge = _bridge_with_mock_system(system_mock)

    # Must not raise
    await bridge.on_add("mem-bad", "bad content")


# ---------------------------------------------------------------------------
# test_bridge_on_search_swallows_errors
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_on_search_swallows_errors():
    """on_search catches exceptions and returns the original results."""
    system_mock = _make_system_mock()
    system_mock.on_search = AsyncMock(side_effect=RuntimeError("search boom"))
    bridge = _bridge_with_mock_system(system_mock)

    results = [{"id": "x"}]
    returned = await bridge.on_search("q", results)
    assert returned is results


# ---------------------------------------------------------------------------
# test_bridge_lazy_connect
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_lazy_connect():
    """_ensure() connects only once even when called concurrently."""
    system_mock = _make_system_mock()
    call_count = 0
    original_aenter = system_mock.__aenter__

    async def counted_aenter(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return await original_aenter(*args, **kwargs)

    system_mock.__aenter__ = counted_aenter

    with (
        patch.object(bridge_mod, "_SYNAPTIC_AVAILABLE", True),
        patch.object(bridge_mod, "SynapticMemorySystem", return_value=system_mock),
    ):
        bridge = bridge_mod.SynapticBridge()
        # Ensure _system starts as None so _ensure actually connects
        assert bridge._system is None

        await asyncio.gather(bridge._ensure(), bridge._ensure(), bridge._ensure())

        assert call_count == 1
        assert bridge._system is system_mock


# ---------------------------------------------------------------------------
# test_bridge_close
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_close():
    """close() calls __aexit__ on the system and clears _system."""
    system_mock = _make_system_mock()
    bridge = _bridge_with_mock_system(system_mock)

    await bridge.close()

    system_mock.__aexit__.assert_awaited_once_with(None, None, None)
    assert bridge._system is None


# ---------------------------------------------------------------------------
# test_bridge_close_no_op_when_not_connected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_close_no_op_when_not_connected():
    """close() is safe to call when the system was never connected."""
    bridge = bridge_mod.SynapticBridge()
    # Must not raise
    await bridge.close()


# ---------------------------------------------------------------------------
# test_bridge_on_add_empty_context
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bridge_on_add_empty_context():
    """on_add passes an empty list when context_memories is None."""
    system_mock = _make_system_mock()
    bridge = _bridge_with_mock_system(system_mock)

    await bridge.on_add("mem-no-ctx", "lone memory")

    _, kwargs = system_mock.add_memory.call_args
    assert kwargs["context_memories"] == []
