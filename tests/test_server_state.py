import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch


class FakeMemory:
    @staticmethod
    def from_config(config):
        return object()


def load_server_state():
    path = Path(__file__).resolve().parents[1] / "server" / "server_state.py"
    spec = importlib.util.spec_from_file_location("server_state_for_tests", path)
    module = importlib.util.module_from_spec(spec)
    original_mem0 = sys.modules.get("mem0")
    sys.modules["mem0"] = types.SimpleNamespace(Memory=FakeMemory)
    try:
        spec.loader.exec_module(module)
    finally:
        if original_mem0 is None:
            sys.modules.pop("mem0", None)
        else:
            sys.modules["mem0"] = original_mem0
    return module


def test_initialize_state_uses_env_key_over_database_key(monkeypatch):
    server_state = load_server_state()
    default_config = {
        "llm": {"provider": "openai", "config": {"api_key": "openai-key", "model": "gpt"}},
        "embedder": {"provider": "openai", "config": {"api_key": "openai-key", "model": "embed"}},
    }
    overrides = {
        "llm": {"provider": "gemini", "config": {"api_key": "stale-openai", "model": "gemini-2.0-flash"}},
        "embedder": {
            "provider": "gemini",
            "config": {"api_key": "stale-openai", "model": "models/gemini-embedding-001"},
        },
    }
    monkeypatch.setenv("GOOGLE_API_KEY", "valid-google-key")
    monkeypatch.setattr(server_state, "_load_overrides", lambda: overrides)

    with patch.object(server_state.Memory, "from_config") as from_config:
        server_state.initialize_state(default_config)

    config = server_state.get_current_config()
    assert config["llm"]["config"]["api_key"] == "valid-google-key"
    assert config["embedder"]["config"]["api_key"] == "valid-google-key"
    from_config.assert_called_once_with(config)


def test_update_config_uses_env_key_for_runtime_config(monkeypatch):
    server_state = load_server_state()
    monkeypatch.setenv("GOOGLE_API_KEY", "valid-google-key")
    monkeypatch.setattr(server_state, "_load_overrides", lambda: {})
    monkeypatch.setattr(server_state, "_save_overrides", lambda overrides: None)

    with patch.object(server_state.Memory, "from_config"):
        server_state.initialize_state({"llm": {"provider": "openai", "config": {"api_key": "openai-key"}}})
        config = server_state.update_config(
            {"llm": {"provider": "gemini", "config": {"api_key": "openai-key", "model": "gemini-2.0-flash"}}}
        )

    assert config["llm"]["config"]["api_key"] == "valid-google-key"


def test_provider_change_without_env_drops_previous_provider_key(monkeypatch):
    server_state = load_server_state()
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(server_state, "_load_overrides", lambda: {})
    monkeypatch.setattr(server_state, "_save_overrides", lambda overrides: None)

    with patch.object(server_state.Memory, "from_config"):
        server_state.initialize_state({"llm": {"provider": "openai", "config": {"api_key": "openai-key"}}})
        config = server_state.update_config(
            {"llm": {"provider": "gemini", "config": {"api_key": "openai-key", "model": "gemini-2.0-flash"}}}
        )

    assert config["llm"]["config"] == {"model": "gemini-2.0-flash"}


def test_provider_change_keeps_new_key_entered_by_user(monkeypatch):
    server_state = load_server_state()
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(server_state, "_load_overrides", lambda: {})
    monkeypatch.setattr(server_state, "_save_overrides", lambda overrides: None)

    with patch.object(server_state.Memory, "from_config"):
        server_state.initialize_state({"llm": {"provider": "openai", "config": {"api_key": "openai-key"}}})
        config = server_state.update_config(
            {"llm": {"provider": "gemini", "config": {"api_key": "gemini-key", "model": "gemini-2.0-flash"}}}
        )

    assert config["llm"]["config"]["api_key"] == "gemini-key"
