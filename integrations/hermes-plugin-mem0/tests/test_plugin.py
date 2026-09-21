"""Offline regressions for the standalone Hermes plugin."""

import contextvars
import importlib
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


def test_dimension_mismatch_preserves_qdrant_collection(plugin, monkeypatch):
    backend = importlib.import_module(f"{plugin.__name__}._backend")
    client = Mock()
    client.collection_exists.return_value = True
    client.get_collection.return_value.config.params.vectors = types.SimpleNamespace(size=1536)
    monkeypatch.setitem(sys.modules, "qdrant_client", types.SimpleNamespace(QdrantClient=Mock(return_value=client)))
    with pytest.raises(ValueError, match="1536.*768"):
        backend.OSSBackend._reject_dimension_mismatch("qdrant", {"path": "/unused"}, 768)
    client.delete_collection.assert_not_called()
    client.close.assert_called_once()


def test_dimension_mismatch_preserves_pgvector_table(plugin, monkeypatch):
    backend = importlib.import_module(f"{plugin.__name__}._backend")
    cursor, connection = Mock(), Mock()
    cursor.fetchone.return_value = (1536,)
    connection.cursor.return_value = cursor
    driver = types.SimpleNamespace(connect=Mock(return_value=connection), sql=Mock())
    monkeypatch.setitem(sys.modules, "psycopg2", driver)
    with pytest.raises(ValueError, match="1536.*768"):
        backend.OSSBackend._reject_dimension_mismatch("pgvector", {"user": "test"}, 768)
    assert cursor.execute.call_count == 1
    assert cursor.execute.call_args.args[0].startswith("SELECT")
    connection.close.assert_called_once()


def test_setup_keeps_credentials_private_and_preserves_existing_values(plugin, tmp_path):
    setup = importlib.import_module(f"{plugin.__name__}._setup")
    path = tmp_path / ".env"
    path.write_text("EXISTING=value\nMEM0_API_KEY=old\n")
    path.chmod(0o644)
    setup._write_env(path, {"MEM0_API_KEY": "new"})
    assert path.read_text() == "EXISTING=value\nMEM0_API_KEY=new\n"
    assert path.stat().st_mode & 0o777 == 0o600


def test_oss_setup_keeps_database_password_private(plugin, tmp_path, monkeypatch):
    setup = importlib.import_module(f"{plugin.__name__}._setup")
    for name in ("_install_provider_deps", "_activate_provider", "_run_connectivity_checks"):
        monkeypatch.setattr(setup, name, Mock())
    config = {"llm": {"provider": "openai", "config": {}}, "embedder": {"provider": "openai", "config": {}},
              "vector_store": {"provider": "pgvector", "config": {"password": "test-password"}}}
    setup._finish_oss(str(tmp_path), {}, config, {}, "existing-user", "hermes")
    path = tmp_path / "mem0.json"
    assert json.loads(path.read_text())["user_id"] == "existing-user"
    assert path.stat().st_mode & 0o777 == 0o600


def test_optional_server_key_and_prefetch_rerank(plugin, monkeypatch):
    monkeypatch.setattr(plugin, "_load_config", lambda: {"host": "http://localhost:8888", "rerank": True})
    provider = plugin.Mem0MemoryProvider()
    assert not next(field for field in provider.get_config_schema() if field["key"] == "api_key")["required"]
    backend = Mock()
    backend.search.return_value = [{"memory": "Prefers Python"}]
    monkeypatch.setattr(provider, "_create_backend", lambda: backend)
    provider.initialize("test-session")
    try:
        assert "Prefers Python" in provider.prefetch("language")
        assert backend.search.call_args.kwargs["rerank"] is True
    finally:
        provider.shutdown()


def test_invalid_tool_arguments_never_reach_backend(plugin, monkeypatch):
    provider = plugin.Mem0MemoryProvider()
    provider._backend = Mock()
    for args in (None, {"query": []}, {"query": " "}, {"query": "fact", "top_k": "invalid"}):
        assert "error" in json.loads(provider.handle_tool_call("mem0_search", args))
    provider._backend.search.assert_not_called()
    assert provider._consecutive_failures == 0


def test_selfhosted_http_auth_and_tool_routes(plugin):
    import httpx

    backend = importlib.import_module(f"{plugin.__name__}._backend")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"results": [{"id": "existing", "memory": "Prefers Python"}]})

    client = backend.SelfHostedBackend("test-key", "http://localhost:8888", transport=httpx.MockTransport(respond))
    try:
        client.add([], user_id="existing-user", agent_id="hermes", infer=True)
        assert requests[-1].headers["X-API-Key"] == "test-key"
        assert json.loads(requests[-1].content)["user_id"] == "existing-user"
        assert client.search("language", filters={"user_id": "existing-user"})[0]["id"] == "existing"
        assert json.loads(requests[-1].content)["filters"] == {"user_id": "existing-user"}
        client.update("existing", "Prefers Rust")
        assert json.loads(requests[-1].content) == {"text": "Prefers Rust"}
        client.delete("existing")
        assert [(r.method, r.url.path) for r in requests] == [
            ("POST", "/memories"), ("POST", "/search"), ("PUT", "/memories/existing"), ("DELETE", "/memories/existing")
        ]
    finally:
        client.close()


@pytest.mark.parametrize("mode", ["platform", "selfhosted"])
def test_setup_rotates_legacy_file_key(plugin, monkeypatch, tmp_path, mode):
    setup = importlib.import_module(f"{plugin.__name__}._setup")
    (tmp_path / "mem0.json").write_text(json.dumps({"api_key": "old-key", "user_id": "existing-user"}))
    monkeypatch.setattr(setup, "_activate_provider", Mock())
    monkeypatch.setattr(setup, "_check_selfhosted_server", Mock())
    monkeypatch.setattr(setup, "_prompt", lambda label, default=None, **kwargs: default or "")
    monkeypatch.setattr(setup, "_curses_select", lambda *args, **kwargs: 0)
    setup._MODE_HANDLERS[mode](str(tmp_path), {}, {"api_key": "new-key", "host": "http://localhost:8888"})
    monkeypatch.setattr(plugin, "get_secret", lambda key, default="": "new-key" if key == "MEM0_API_KEY" else default)
    assert plugin._load_config()["api_key"] == "new-key"
    assert "old-key" not in (tmp_path / "mem0.json").read_text()
    assert "MEM0_API_KEY=new-key" in (tmp_path / ".env").read_text()


def test_platform_setup_honors_user_id_flag(plugin, monkeypatch, tmp_path):
    setup = importlib.import_module(f"{plugin.__name__}._setup")
    monkeypatch.setattr(setup, "_activate_provider", Mock())
    monkeypatch.setattr(setup, "_prompt", lambda label, default=None, **kwargs: default or "")
    monkeypatch.setattr(setup, "_curses_select", lambda *args, **kwargs: 0)
    setup._setup_platform(str(tmp_path), {}, {"api_key": "new-key", "user_id": "chosen-user"})
    assert plugin._load_config()["user_id"] == "chosen-user"


@pytest.mark.parametrize("scoped_key", ["profile-key", ""])
def test_oss_embedder_never_uses_another_profiles_credentials(plugin, monkeypatch, scoped_key):
    backend = importlib.import_module(f"{plugin.__name__}._backend")
    memory = Mock()
    monkeypatch.setitem(sys.modules, "mem0", types.SimpleNamespace(Memory=memory))
    monkeypatch.setenv("OPENAI_API_KEY", "other-profile-key")
    monkeypatch.setenv("OPENAI_API_BASE", "https://other-profile.invalid/v1")
    secrets = {"OPENAI_API_KEY": scoped_key, "OPENAI_BASE_URL": "https://profile.invalid/v1"}
    monkeypatch.setattr(sys.modules["agent.secret_scope"], "get_secret", lambda key, default="": secrets.get(key, default))
    config = {
        "llm": {"provider": "ollama", "config": {}},
        "embedder": {"provider": "openai", "config": {}},
        "vector_store": {"provider": "qdrant", "config": {}},
    }
    if not scoped_key:
        with pytest.raises(ValueError, match="OpenAI API key"):
            backend.OSSBackend(config)
        memory.from_config.assert_not_called()
    else:
        backend.OSSBackend(config)
        resolved = memory.from_config.call_args.args[0]["embedder"]["config"]
        assert resolved["api_key"] == scoped_key
        assert resolved["openai_base_url"] == "https://profile.invalid/v1"
        assert config["embedder"]["config"] == {}


def test_pgvector_setup_never_removes_existing_container(plugin, monkeypatch):
    setup = importlib.import_module(f"{plugin.__name__}._setup")
    monkeypatch.setattr(setup, "_check_pgvector", lambda *args: (False, "unreachable"))
    monkeypatch.setattr(setup.shutil, "which", lambda name: "/test/docker")
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    calls = []

    def docker(*args, **kwargs):
        calls.append(args)
        if args[0] == "run":
            raise setup.subprocess.CalledProcessError(1, "docker run: container name already exists")
        return types.SimpleNamespace(returncode=0, stdout="paused")

    monkeypatch.setattr(setup, "_docker", docker)
    assert setup._ensure_pgvector() is None
    assert not any(args[0] == "rm" for args in calls)


def test_platform_dry_run_does_not_print_stored_secrets(plugin, monkeypatch, tmp_path, capsys):
    setup = importlib.import_module(f"{plugin.__name__}._setup")
    config = {"api_key": "old-secret", "oss": {"vector_store": {"config": {"password": "db-secret"}}}}
    path = tmp_path / "mem0.json"
    path.write_text(json.dumps(config))
    monkeypatch.setattr(setup, "_prompt", lambda label, default=None, **kwargs: default or "")
    monkeypatch.setattr(setup, "_curses_select", lambda *args, **kwargs: 0)
    setup._setup_platform(str(tmp_path), {}, {"api_key": "new-secret", "dry_run": True})
    output = capsys.readouterr().out
    assert all(secret not in output for secret in ("old-secret", "db-secret", "new-secret"))
    assert json.loads(path.read_text()) == config
    assert not (tmp_path / ".env").exists()


def test_oss_setup_preserves_distinct_llm_and_embedder_keys(plugin):
    setup = importlib.import_module(f"{plugin.__name__}._setup")
    config, env = setup.build_oss_config({"oss_llm_key": "llm-key", "oss_embedder_key": "embedder-key"})
    assert config["llm"]["config"].get("api_key", env.get("OPENAI_API_KEY")) == "llm-key"
    assert config["embedder"]["config"].get("api_key", env.get("OPENAI_API_KEY")) == "embedder-key"


def test_direct_openai_llm_uses_scoped_credentials(plugin, monkeypatch):
    llm_mod = importlib.import_module(f"{plugin.__name__}._openai_llm")
    openai_mock = types.SimpleNamespace(OpenAI=Mock(return_value=Mock()))
    monkeypatch.setitem(sys.modules, "openai", openai_mock)
    monkeypatch.setenv("OPENROUTER_API_KEY", "should-be-ignored")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key-should-be-ignored")
    secrets = {"OPENAI_API_KEY": "scoped-key", "OPENAI_API_BASE": "", "OPENAI_BASE_URL": ""}
    monkeypatch.setattr(sys.modules["agent.secret_scope"], "get_secret", lambda key, default="": secrets.get(key, default))
    llm_mod.DirectOpenAILLM({"api_key": "", "model": "gpt-5-mini"})
    call_kwargs = openai_mock.OpenAI.call_args.kwargs
    assert call_kwargs["api_key"] == "scoped-key"
    assert "openrouter" not in call_kwargs.get("base_url", "").lower()


def test_direct_openai_llm_rejects_missing_key(plugin, monkeypatch):
    llm_mod = importlib.import_module(f"{plugin.__name__}._openai_llm")
    monkeypatch.setattr(sys.modules["agent.secret_scope"], "get_secret", lambda key, default="": "")
    with pytest.raises(ValueError, match="API key"):
        llm_mod.DirectOpenAILLM({"api_key": "", "model": "gpt-5-mini"})


def test_selfhosted_keyless_omits_auth_header(plugin):
    import httpx

    backend = importlib.import_module(f"{plugin.__name__}._backend")
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"results": []})

    client = backend.SelfHostedBackend("", "http://localhost:8888", transport=httpx.MockTransport(respond))
    client.search("test", filters={"user_id": "u"})
    assert "X-API-Key" not in requests[0].headers
    client.close()


def test_initialize_tolerates_non_numeric_sync_max_chars(plugin, monkeypatch):
    monkeypatch.setattr(plugin, "_load_config", lambda: {"sync_max_chars": "not-a-number"})
    provider = plugin.Mem0MemoryProvider()
    provider.initialize("test-session")
    assert provider._sync_max_chars == plugin._SYNC_MSG_MAX_CHARS
