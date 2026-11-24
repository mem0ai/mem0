"""Regression tests: Memory()/AsyncMemory() must not share one default MemoryConfig.

A default of ``config=MemoryConfig()`` is evaluated once at import time, so every
instance created without an explicit config received the *same* object, and a change
made through one instance's ``.config`` leaked into every later instance.
"""

from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import pytest

from mem0.memory.main import AsyncMemory, Memory


@pytest.fixture
def mocked_providers():
    targets = {
        "mem0.memory.main.EmbedderFactory.create": MagicMock(),
        "mem0.memory.main.VectorStoreFactory.create": MagicMock(),
        "mem0.memory.main.LlmFactory.create": MagicMock(),
        "mem0.memory.main.SQLiteManager": MagicMock(),
        "mem0.memory.main.capture_event": MagicMock(),
        "mem0.memory.main.MEM0_TELEMETRY": False,
    }
    with ExitStack() as stack:
        for target, value in targets.items():
            stack.enter_context(patch(target, value))
        yield


@pytest.mark.parametrize("memory_cls", [Memory, AsyncMemory])
def test_default_config_is_not_shared_between_instances(mocked_providers, memory_cls):
    first = memory_cls()
    second = memory_cls()

    assert first.config is not second.config


@pytest.mark.parametrize("memory_cls", [Memory, AsyncMemory])
def test_mutating_one_instance_config_does_not_leak(mocked_providers, memory_cls):
    first = memory_cls()
    first.config.custom_instructions = "only remember food preferences"

    second = memory_cls()

    assert second.config.custom_instructions is None
    assert second.custom_instructions is None
