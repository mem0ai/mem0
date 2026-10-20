"""Regression tests for https://github.com/mem0ai/mem0/issues/7677.

`import mem0` must not import `qdrant_client`. The heavy provider import was
triggered at import time by the `MemoryConfig()` default argument of
`Memory.__init__` / `AsyncMemory.__init__`: default arguments are evaluated
once, when `mem0.memory.main` is imported, and building that default config
validates the default `qdrant` vector-store provider, whose config module
imports `qdrant_client` at class-body level. The default config is now built
lazily inside `__init__`.
"""

import os
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

from mem0 import AsyncMemory, Memory
from mem0.configs.base import MemoryConfig


@pytest.fixture(autouse=True)
def _dummy_openai_key():
    # Default configs use the OpenAI provider; client construction needs a key
    # present (no network calls are made).
    os.environ["OPENAI_API_KEY"] = "123"


def test_import_mem0_does_not_import_qdrant_client():
    """A bare `import mem0` must leave qdrant_client out of sys.modules."""
    code = "import sys, mem0; print('qdrant_client' in sys.modules)"
    env = {**os.environ, "MEM0_TELEMETRY": "False"}
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        timeout=180,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "False"


def _construct_without_config(cls):
    # Patch the names as used in mem0.memory.main (from-imports), and keep
    # the test hermetic: no vector-store connections, no sqlite file, no
    # telemetry directories.
    with (
        patch("mem0.memory.main.EmbedderFactory") as mock_embedder,
        patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
        patch("mem0.memory.main.LlmFactory") as mock_llm,
        patch("mem0.memory.main.SQLiteManager"),
        patch("mem0.memory.main.MEM0_TELEMETRY", False),
        patch("mem0.memory.telemetry.capture_event"),
    ):
        mock_embedder.create.return_value = Mock()
        mock_vector_store.create.return_value = Mock()
        mock_llm.create.return_value = Mock()
        return cls()


def test_memory_builds_default_config_lazily():
    """Memory() with no args still gets the default (qdrant) config."""
    m = _construct_without_config(Memory)
    assert isinstance(m.config, MemoryConfig)
    assert m.config.vector_store.provider == "qdrant"


def test_async_memory_builds_default_config_lazily():
    """AsyncMemory() with no args still gets the default (qdrant) config."""
    m = _construct_without_config(AsyncMemory)
    assert isinstance(m.config, MemoryConfig)
    assert m.config.vector_store.provider == "qdrant"
