"""Tests for MEM0_CONFIG_PATH env var support in server_state._load_yaml_config_path."""
import os
import textwrap

import pytest


# ---------------------------------------------------------------------------
# Helper: import the function under test without touching mem0 itself.
# We patch `mem0.Memory` at the module level before importing server_state so
# that the module-level `Memory` reference doesn't require a real mem0 install.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_mem0(monkeypatch):
    """Stub out mem0.Memory so server_state can be imported without credentials."""
    import sys
    import types

    # Build a minimal fake mem0 package
    fake_mem0 = types.ModuleType("mem0")

    class _FakeMemory:
        def __init__(self, config=None):
            self._config = config

        @classmethod
        def from_config(cls, config):
            return cls(config)

    fake_mem0.Memory = _FakeMemory
    monkeypatch.setitem(sys.modules, "mem0", fake_mem0)

    # Remove any cached import of server_state so each test gets a fresh module
    sys.modules.pop("server_state", None)
    yield
    sys.modules.pop("server_state", None)


# ---------------------------------------------------------------------------
# Tests for _load_yaml_config_path
# ---------------------------------------------------------------------------


def test_unset_env_var_returns_empty_dict(monkeypatch):
    """When MEM0_CONFIG_PATH is not set, the helper returns {} (no-op)."""
    monkeypatch.delenv("MEM0_CONFIG_PATH", raising=False)
    from server_state import _load_yaml_config_path

    result = _load_yaml_config_path()
    assert result == {}


def test_empty_env_var_returns_empty_dict(monkeypatch):
    """When MEM0_CONFIG_PATH is set to an empty string, the helper returns {}."""
    monkeypatch.setenv("MEM0_CONFIG_PATH", "")
    from server_state import _load_yaml_config_path

    result = _load_yaml_config_path()
    assert result == {}


def test_valid_yaml_file_returns_parsed_dict(monkeypatch, tmp_path):
    """When MEM0_CONFIG_PATH points to valid YAML, the dict is returned."""
    config_yaml = textwrap.dedent("""\
        vector_store:
          provider: qdrant
          config:
            host: qdrant-svc
            port: 6333
            collection_name: memories
            embedding_model_dims: 1536
        embedder:
          provider: openai
          config:
            model: text-embedding-3-small
        llm:
          provider: anthropic
          config:
            model: claude-haiku-4-5
            temperature: 0.2
        history_db_path: /app/history/history.db
    """)
    cfg_file = tmp_path / "mem0_config.yaml"
    cfg_file.write_text(config_yaml)
    monkeypatch.setenv("MEM0_CONFIG_PATH", str(cfg_file))

    from server_state import _load_yaml_config_path

    result = _load_yaml_config_path()

    assert result["vector_store"]["provider"] == "qdrant"
    assert result["vector_store"]["config"]["host"] == "qdrant-svc"
    assert result["vector_store"]["config"]["port"] == 6333
    assert result["embedder"]["provider"] == "openai"
    assert result["llm"]["provider"] == "anthropic"
    assert result["llm"]["config"]["model"] == "claude-haiku-4-5"
    assert result["history_db_path"] == "/app/history/history.db"


def test_missing_file_logs_error_and_returns_empty_dict(monkeypatch, tmp_path, caplog):
    """When MEM0_CONFIG_PATH points to a non-existent file, log error + return {}."""
    missing = str(tmp_path / "does_not_exist.yaml")
    monkeypatch.setenv("MEM0_CONFIG_PATH", missing)

    import logging

    from server_state import _load_yaml_config_path

    with caplog.at_level(logging.ERROR, logger="root"):
        result = _load_yaml_config_path()

    assert result == {}
    assert any("does not exist" in record.message for record in caplog.records)


def test_invalid_yaml_logs_error_and_returns_empty_dict(monkeypatch, tmp_path, caplog):
    """When MEM0_CONFIG_PATH points to invalid YAML, log error + return {}."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("key: [unclosed bracket\n")
    monkeypatch.setenv("MEM0_CONFIG_PATH", str(bad_yaml))

    import logging

    from server_state import _load_yaml_config_path

    with caplog.at_level(logging.ERROR, logger="root"):
        result = _load_yaml_config_path()

    assert result == {}
    assert any("invalid YAML" in record.message for record in caplog.records)


def test_non_mapping_yaml_logs_error_and_returns_empty_dict(monkeypatch, tmp_path, caplog):
    """When YAML top level is a list (not a mapping), log error + return {}."""
    list_yaml = tmp_path / "list.yaml"
    list_yaml.write_text("- item1\n- item2\n")
    monkeypatch.setenv("MEM0_CONFIG_PATH", str(list_yaml))

    import logging

    from server_state import _load_yaml_config_path

    with caplog.at_level(logging.ERROR, logger="root"):
        result = _load_yaml_config_path()

    assert result == {}
    assert any("YAML mapping" in record.message for record in caplog.records)


# ---------------------------------------------------------------------------
# Integration test: initialize_state merges YAML config into default config
# ---------------------------------------------------------------------------


def test_initialize_state_applies_yaml_config(monkeypatch, tmp_path):
    """initialize_state merges YAML overrides on top of the default config."""
    config_yaml = textwrap.dedent("""\
        vector_store:
          provider: qdrant
          config:
            host: qdrant-svc
            port: 6333
        llm:
          provider: anthropic
          config:
            model: claude-haiku-4-5
    """)
    cfg_file = tmp_path / "mem0_config.yaml"
    cfg_file.write_text(config_yaml)
    monkeypatch.setenv("MEM0_CONFIG_PATH", str(cfg_file))

    from server_state import get_current_config, initialize_state, set_session_factory

    # No DB session — overrides table is skipped gracefully
    set_session_factory(None)

    default_config = {
        "vector_store": {"provider": "pgvector", "config": {"host": "postgres"}},
        "llm": {"provider": "openai", "config": {"model": "gpt-4o"}},
        "history_db_path": "/tmp/history.db",
    }
    initialize_state(default_config)

    current = get_current_config()
    # YAML overrides should win
    assert current["vector_store"]["provider"] == "qdrant"
    assert current["vector_store"]["config"]["host"] == "qdrant-svc"
    assert current["llm"]["provider"] == "anthropic"
    assert current["llm"]["config"]["model"] == "claude-haiku-4-5"
    # Keys not in YAML should be preserved from default
    assert current["history_db_path"] == "/tmp/history.db"


def test_initialize_state_unchanged_without_env_var(monkeypatch):
    """initialize_state is unchanged from upstream when MEM0_CONFIG_PATH is unset."""
    monkeypatch.delenv("MEM0_CONFIG_PATH", raising=False)

    from server_state import get_current_config, initialize_state, set_session_factory

    set_session_factory(None)

    default_config = {
        "vector_store": {"provider": "pgvector", "config": {"host": "postgres"}},
        "llm": {"provider": "openai", "config": {"model": "gpt-4o"}},
    }
    initialize_state(default_config)

    current = get_current_config()
    # Exactly the default config — no YAML applied
    assert current["vector_store"]["provider"] == "pgvector"
    assert current["llm"]["provider"] == "openai"
    assert current["llm"]["config"]["model"] == "gpt-4o"
