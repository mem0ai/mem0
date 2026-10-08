"""Hermes host stubs for offline plugin tests."""

import contextvars
import importlib.util
import json
import sys
import threading
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def plugin(monkeypatch, tmp_path):
    def spawn(target, *, name):
        return threading.Thread(target=contextvars.copy_context().run, args=(target,), name=name)

    def atomic_write_text(path, value, *, mode):
        path.write_text(value)
        path.chmod(mode)

    modules = {
        "agent.memory_provider": {"MemoryProvider": object, "spawn_context_thread": spawn},
        "agent.secret_scope": {"get_secret": lambda key, default="": default},
        "tools.registry": {"tool_error": lambda message: json.dumps({"error": message})},
        "utils": {
            "read_json_or_empty": lambda path: json.loads(path.read_text()) if path.exists() else {},
            "atomic_json_write": lambda path, value, **kwargs: atomic_write_text(path, json.dumps(value), **kwargs),
            "atomic_write_text": atomic_write_text,
        },
        "hermes_constants": {"get_hermes_home": lambda: tmp_path},
    }
    for name, values in modules.items():
        module = types.ModuleType(name)
        module.__dict__.update(values)
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location("standalone_mem0", ROOT / "__init__.py")
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.atexit, "register", lambda *args: None)
    yield module
    for name in list(sys.modules):
        if name.startswith("standalone_mem0."):
            monkeypatch.delitem(sys.modules, name)

