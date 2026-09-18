"""Offline contracts for the native Hermes provider and legacy configuration."""

import contextvars
import importlib.util
import json
import sys
import threading
import types
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def plugin(monkeypatch, tmp_path):
    def spawn(target, *, name):
        context = contextvars.copy_context()
        return threading.Thread(target=context.run, args=(target,), name=name)

    modules = {
        "agent": {},
        "agent.memory_provider": {"MemoryProvider": object, "spawn_context_thread": spawn},
        "agent.secret_scope": {"get_secret": lambda key, default="": default},
        "tools": {},
        "tools.registry": {"tool_error": lambda text: json.dumps({"error": text})},
        "utils": {
            "read_json_or_empty": lambda p: json.loads(p.read_text()) if p.exists() else {},
            "atomic_json_write": lambda p, value, **kw: p.write_text(json.dumps(value)),
        },
        "hermes_constants": {"get_hermes_home": lambda: tmp_path},
    }
    for name, values in modules.items():
        module = types.ModuleType(name)
        module.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, module)
    name = "hermes_test_mem0"
    spec = importlib.util.spec_from_file_location(name, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.atexit, "register", lambda *args: None)
    return module


def provider(plugin, monkeypatch, config=None, **identity):
    backend = Mock()
    backend.add.return_value = {"event_id": "event-1"}
    backend.search.return_value = []
    monkeypatch.setattr(plugin, "_load_config", lambda: config or {})
    monkeypatch.setattr(plugin.Mem0MemoryProvider, "_create_backend", lambda self: backend)
    instance = plugin.Mem0MemoryProvider()
    instance.initialize("session-1", **identity)
    return instance, backend


def test_long_turns_preserve_tail_and_redact_before_chunking(plugin, monkeypatch):
    instance, backend = provider(plugin, monkeypatch, {"sync_max_chars": 450})
    text = "Opening. " + "x" * 1100 + " api_key=secret-value lasting preference at the end."
    instance.sync_turn(text, "Noted.", session_id="turn-session")
    instance.shutdown()
    messages = [m for call in backend.add.call_args_list for m in call.args[0]]
    assert "".join(m["content"] for m in messages if m["role"] == "user") == plugin.redact(text)
    assert all(len(m["content"]) <= 450 for m in messages)
    assert "secret-value" not in repr(backend.add.call_args_list)
    assert all(call.kwargs["run_id"] == "turn-session" for call in backend.add.call_args_list)


def test_busy_capture_queues_each_turn_with_its_profile_context(plugin, monkeypatch):
    instance, backend = provider(plugin, monkeypatch)
    started, release = threading.Event(), threading.Event()
    profile = contextvars.ContextVar("profile", default="first")
    seen = []

    def add(messages, **kwargs):
        if not seen:
            started.set()
            assert release.wait(3)
        seen.append((messages[0]["content"], profile.get()))
        return {}

    backend.add.side_effect = add
    instance.sync_turn("first turn", "reply")
    assert started.wait(3)
    token = profile.set("second")
    try:
        instance.sync_turn("second turn", "reply")
    finally:
        profile.reset(token)
        release.set()
    instance.shutdown()
    assert seen == [("first turn", "first"), ("second turn", "second")]
    backend.close.assert_called_once()


@pytest.mark.parametrize(
    "configured,gateway,expected",
    [
        (None, "telegram-42", "telegram-42"),
        ("hermes-user", "telegram-42", "telegram-42"),
        ("existing-account", "telegram-42", "existing-account"),
        (None, None, "hermes-user"),
    ],
)
def test_legacy_identity_and_tool_contract(plugin, monkeypatch, configured, gateway, expected):
    instance, backend = provider(plugin, monkeypatch, {"user_id": configured}, user_id=gateway)
    assert instance.name == "mem0"
    assert {s["name"] for s in instance.get_tool_schemas()} == {"mem0_search", "mem0_add", "mem0_update", "mem0_delete"}
    instance.handle_tool_call("mem0_search", {"query": "api_key=secret-value"})
    assert backend.search.call_args.kwargs["filters"] == {"user_id": expected}
    assert backend.search.call_args.args[0] == "api_key=[REDACTED]"
    instance.handle_tool_call("mem0_add", {"content": "password=secret-value"})
    assert backend.add.call_args.kwargs["infer"] is False
    assert backend.add.call_args.args[0][0]["content"] == "password=[REDACTED]"
    instance.handle_tool_call("mem0_update", {"memory_id": "old-id", "text": "password=secret-value"})
    backend.update.assert_called_once_with("old-id", "password=[REDACTED]")
    instance.shutdown()


def test_config_keeps_legacy_file_over_env_precedence(plugin, monkeypatch, tmp_path):
    env = {"MEM0_API_KEY": "env-key", "MEM0_USER_ID": "env-user", "MEM0_HOST": "http://localhost:8888"}
    monkeypatch.setattr(plugin, "get_secret", lambda key, default="": env.get(key, default))
    (tmp_path / "mem0.json").write_text(json.dumps({"user_id": "existing-user", "rerank": True}))
    cfg = plugin._load_config()
    assert (cfg["api_key"], cfg["user_id"], cfg["host"], cfg["rerank"]) == (
        "env-key",
        "existing-user",
        "http://localhost:8888",
        True,
    )


def test_prefetch_respects_rerank_and_redacts_recalled_context(plugin, monkeypatch):
    instance, backend = provider(plugin, monkeypatch, {"rerank": True})
    backend.search.return_value = [{"memory": "password=old-secret"}]
    assert "old-secret" not in instance.prefetch("preference")
    assert backend.search.call_args.kwargs["rerank"] is True
    instance.shutdown()


def test_session_switch_updates_writes_without_narrowing_recall(plugin, monkeypatch):
    instance, backend = provider(plugin, monkeypatch)
    instance.on_session_switch("resumed-session")
    instance.handle_tool_call("mem0_add", {"content": "fact"})
    assert backend.add.call_args.kwargs["run_id"] == "resumed-session"
    instance.handle_tool_call("mem0_search", {"query": "fact"})
    assert backend.search.call_args.kwargs["filters"] == {"user_id": "hermes-user"}
    instance.shutdown()


def test_invalid_tool_input_never_reaches_backend_or_trips_breaker(plugin, monkeypatch):
    instance, backend = provider(plugin, monkeypatch)
    for args in ({"query": []}, {"query": "fact", "top_k": "not-a-number"}, None):
        assert "error" in json.loads(instance.handle_tool_call("mem0_search", args))
    backend.search.assert_not_called()
    assert instance._consecutive_failures == 0
    instance.shutdown()


def test_setup_writes_private_env_and_preserves_existing_values(plugin, tmp_path):
    import importlib

    setup = importlib.import_module(f"{plugin.__name__}._setup")
    path = tmp_path / ".env"
    path.write_text("EXISTING=value\nMEM0_API_KEY=old\n")
    setup._write_env(path, {"MEM0_API_KEY": "new"})
    assert path.read_text() == "EXISTING=value\nMEM0_API_KEY=new\n"
    assert path.stat().st_mode & 0o777 == 0o600


def test_redaction_marker_split_at_chunk_boundary_is_lossless(plugin, monkeypatch):
    instance, backend = provider(plugin, monkeypatch, {"sync_max_chars": 450})
    text = "x" * 438 + " password=secret-value tail"
    instance.sync_turn(text, "")
    instance.shutdown()
    stored = "".join(m["content"] for call in backend.add.call_args_list for m in call.args[0])
    assert stored == plugin.redact(text)


def test_sync_queue_stops_network_calls_when_breaker_opens(plugin, monkeypatch, caplog):
    instance, backend = provider(plugin, monkeypatch)
    started, release = threading.Event(), threading.Event()

    def unavailable(messages, **kwargs):
        started.set()
        assert release.wait(3)
        raise RuntimeError("server unavailable")

    backend.add.side_effect = unavailable
    instance.sync_turn("first turn", "reply")
    assert started.wait(3)
    try:
        for number in range(9):
            instance.sync_turn(f"queued turn {number}", "reply")
    finally:
        release.set()
    instance.shutdown()
    assert backend.add.call_count == plugin._BREAKER_THRESHOLD
    assert any("not synced" in record.message.lower() for record in caplog.records)


def test_shutdown_is_bounded_and_defers_close_until_sync_finishes(plugin, monkeypatch, caplog):
    instance, backend = provider(plugin, monkeypatch)
    started, release = threading.Event(), threading.Event()
    monkeypatch.setattr(plugin, "_SHUTDOWN_WAIT_SECS", 0.01)

    def add(*args, **kwargs):
        started.set()
        assert release.wait(3)
        return {}

    backend.add.side_effect = add
    instance.sync_turn("fact", "reply")
    assert started.wait(3)
    worker = instance._sync_thread
    try:
        instance.shutdown()
        backend.close.assert_not_called()
        assert "shutdown timed out" in caplog.text
    finally:
        release.set()
        worker.join(timeout=3)
    backend.close.assert_called_once()
