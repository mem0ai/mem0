"""Consent and session provenance at the outgoing HTTP boundary."""

import importlib
import json
import threading

import httpx
import pytest

GATEWAY = {
    "platform": "slack", "user_id": "U123", "user_id_alt": "alt-42",
    "user_name": "Ada", "chat_id": "C456", "chat_name": "support",
    "chat_type": "channel", "thread_id": "123.456", "session_title": "Login triage",
    "hermes_home": "/private/profile", "agent_workspace": "/private/workspace",
    "gateway_session_key": "private-routing-key", "api_key": "private-key",
}
EXPECTED = {
    "channel": "slack", "gateway_user_id": "U123", "gateway_user_id_alt": "alt-42",
    "user_name": "Ada", "chat_id": "C456", "chat_name": "support",
    "chat_type": "channel", "thread_id": "123.456", "session_title": "Login triage",
    "session_id": "session-1",
}


@pytest.fixture
def configured(plugin, monkeypatch, tmp_path):
    providers = []

    def create(config=None, context=None, session_id="session-1"):
        (tmp_path / "mem0.json").write_text(json.dumps(config or {}))
        requests = []

        def respond(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={"results": []})

        backend_module = importlib.import_module(f"{plugin.__name__}._backend")
        backend = backend_module.SelfHostedBackend(
            "test-key", "http://localhost:8888", transport=httpx.MockTransport(respond)
        )
        provider = plugin.Mem0MemoryProvider()
        monkeypatch.setattr(provider, "_create_backend", lambda: backend)
        provider.initialize(session_id, **(GATEWAY if context is None else context))
        providers.append(provider)
        return provider, requests

    yield create
    for provider in providers:
        provider.shutdown()


def write(provider, path, **kwargs):
    if path == "tool":
        assert "error" not in json.loads(provider.handle_tool_call("mem0_add", {"content": "Prefers tea"}))
    else:
        provider.sync_turn("I prefer tea", "Noted", **kwargs)
        provider._sync_thread.join(timeout=5)
        assert not provider._sync_thread.is_alive()


@pytest.mark.parametrize("path", ["tool", "sync"])
@pytest.mark.parametrize("consent", [None, False, "false", "0", "no", "", "invalid", 1, [True]])
def test_no_provenance_without_explicit_opt_in(configured, path, consent):
    provider, requests = configured({"share_conversation_context": consent})
    write(provider, path, session_id="fresh-session")
    assert requests[-1]["metadata"] == {"channel": "slack"}


@pytest.mark.parametrize("path", ["tool", "sync"])
@pytest.mark.parametrize("consent", [True, "true", "1", "yes"])
def test_opt_in_exports_only_allowed_context(configured, path, consent):
    provider, requests = configured({"share_conversation_context": consent, "user_id": "shared-store"})
    write(provider, path)
    assert requests[-1]["metadata"] == EXPECTED
    assert requests[-1]["user_id"] == "shared-store"
    assert requests[-1]["infer"] is (path == "sync")
    provider.handle_tool_call("mem0_search", {"query": "tea"})
    assert requests[-1]["filters"] == {"user_id": "shared-store"}


def test_missing_context_and_value_limits(configured):
    provider, requests = configured({"share_conversation_context": True}, {
        "user_id": 123, "session_title": "x" * 1000, "chat_name": "", "thread_id": None,
    }, session_id="s" * 1000)
    write(provider, "tool")
    assert requests[-1]["metadata"] == {
        "channel": "cli", "gateway_user_id": "123", "session_title": "x" * 256, "session_id": "s" * 256,
    }


def test_cli_without_gateway_context(configured):
    provider, requests = configured({"share_conversation_context": True}, {}, session_id="cli-session")
    write(provider, "tool")
    assert requests[-1]["metadata"] == {"channel": "cli", "session_id": "cli-session"}


def test_sync_prefers_call_session(configured):
    provider, requests = configured({"share_conversation_context": True})
    write(provider, "sync", session_id="call-session")
    assert requests[-1]["metadata"]["session_id"] == "call-session"
    assert "session_title" not in requests[-1]["metadata"]
    assert requests[-1]["metadata"]["thread_id"] == "123.456"


@pytest.mark.parametrize("reset", [False, True])
def test_session_switch_updates_manual_writes(configured, reset):
    provider, requests = configured({"share_conversation_context": True})
    provider.on_session_switch("session-2", parent_session_id="session-1", reset=reset)
    write(provider, "tool")
    assert requests[-1]["metadata"]["session_id"] == "session-2"
    assert "session_title" not in requests[-1]["metadata"]
    assert requests[-1]["metadata"]["thread_id"] == "123.456"


def test_queued_sync_keeps_original_metadata(configured, plugin, monkeypatch):
    provider, requests = configured({"share_conversation_context": True})
    started, release = threading.Event(), threading.Event()

    def delayed_thread(target, *, name):
        def run():
            started.set()
            assert release.wait(timeout=5)
            target()
        return threading.Thread(target=run, name=name)

    monkeypatch.setattr(plugin, "spawn_context_thread", delayed_thread)
    provider.sync_turn("I prefer tea", "Noted")
    try:
        assert started.wait(timeout=5)
        provider.on_session_switch("session-2", reset=True)
    finally:
        release.set()
        provider._sync_thread.join(timeout=5)
    assert requests[-1]["metadata"] == EXPECTED


def test_reinitialize_replaces_context_and_consent(configured, tmp_path):
    provider, requests = configured({"share_conversation_context": True})
    provider.initialize("session-2", platform="telegram", user_id="tg-7")
    write(provider, "tool")
    assert requests[-1]["metadata"] == {
        "channel": "telegram", "gateway_user_id": "tg-7", "session_id": "session-2",
    }
    (tmp_path / "mem0.json").write_text(json.dumps({"share_conversation_context": False}))
    provider.initialize("session-3", **GATEWAY)
    write(provider, "sync")
    assert requests[-1]["metadata"] == {"channel": "slack"}


def test_generic_setup_schema_exposes_default_off_consent(plugin):
    fields = {field["key"]: field for field in plugin.Mem0MemoryProvider().get_config_schema()}
    assert fields["share_conversation_context"]["default"] == "false"
    assert fields["share_conversation_context"]["type"] == "boolean"


@pytest.mark.parametrize("mode", ["platform", "selfhosted"])
@pytest.mark.parametrize("consent", [False, True])
def test_setup_persists_explicit_consent(plugin, monkeypatch, tmp_path, mode, consent):
    setup = importlib.import_module(f"{plugin.__name__}._setup")
    monkeypatch.setattr(setup, "_activate_provider", lambda config: None)
    monkeypatch.setattr(setup, "_check_selfhosted_server", lambda host: None)
    monkeypatch.setattr(setup, "_prompt", lambda label, default=None, **kwargs: default or "")

    def select(title, items, default=0):
        return int(consent) if "conversation" in title.lower() else default

    monkeypatch.setattr(setup, "_curses_select", select)
    setup._MODE_HANDLERS[mode](str(tmp_path), {}, {"api_key": "new-key", "host": "http://localhost:8888"})
    assert plugin._load_config()["share_conversation_context"] is consent


def test_oss_interactive_setup_persists_consent(plugin, monkeypatch, tmp_path):
    setup = importlib.import_module(f"{plugin.__name__}._setup")
    monkeypatch.setattr(setup, "_configure_model_provider", lambda kind, registry, *a, **kw: (
        "openai", registry["openai"], "test-model", None,
    ))
    monkeypatch.setattr(setup, "_input", lambda label, default: default)
    monkeypatch.setattr(setup, "_curses_select", lambda title, *a, **kw: int("conversation" in title.lower()))
    for name in ("_install_provider_deps", "_activate_provider", "_run_connectivity_checks"):
        monkeypatch.setattr(setup, name, lambda *a: None)
    setup._setup_oss_interactive(str(tmp_path), {})
    assert plugin._load_config()["share_conversation_context"] is True


@pytest.mark.parametrize("existing", [None, False, True])
def test_unattended_oss_setup_preserves_consent(plugin, monkeypatch, tmp_path, existing):
    setup = importlib.import_module(f"{plugin.__name__}._setup")
    path = tmp_path / "mem0.json"
    path.write_text(json.dumps({} if existing is None else {"share_conversation_context": existing}))
    for name in ("_install_provider_deps", "_activate_provider", "_run_connectivity_checks"):
        monkeypatch.setattr(setup, name, lambda *a: None)
    setup._setup_oss(str(tmp_path), {}, {"_mode_from_flag": True, "oss_llm_key": "test-key"})
    assert plugin._load_config().get("share_conversation_context") is existing


@pytest.mark.parametrize("existing", [None, False, True])
def test_setup_prompt_defaults_to_saved_consent(plugin, monkeypatch, tmp_path, existing):
    setup = importlib.import_module(f"{plugin.__name__}._setup")
    path = tmp_path / "mem0.json"
    path.write_text(json.dumps({} if existing is None else {"share_conversation_context": existing}))
    monkeypatch.setattr(setup, "_activate_provider", lambda config: None)
    monkeypatch.setattr(setup, "_prompt", lambda label, default=None, **kwargs: default or "")
    monkeypatch.setattr(setup, "_curses_select", lambda title, items, default=0: default)
    setup._setup_platform(str(tmp_path), {}, {"api_key": "test-key"})
    assert plugin._load_config()["share_conversation_context"] is (existing is True)
