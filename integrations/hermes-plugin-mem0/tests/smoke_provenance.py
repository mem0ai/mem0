"""Real Hermes manager and native settings; HTTP memory responses stay local.

HERMES_SOURCE=/path/to/hermes-agent python tests/smoke_provenance.py
Requires the Hermes dependencies and httpx in the active environment.
All configuration and credentials are temporary; no external requests are made.
"""

import importlib
import json
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import httpx


def main():
    sys.path.insert(0, str(Path(os.environ["HERMES_SOURCE"]).resolve()))
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary)
        os.environ["HERMES_HOME"] = temporary
        (home / "config.yaml").write_text("memory:\n  provider: mem0\nsecurity:\n  allow_lazy_installs: false\n")
        (home / "mem0.json").write_text(json.dumps({"host": "http://localhost:8888", "user_id": "shared-store"}))
        destination = home / "plugins" / "mem0"
        shutil.copytree(Path(__file__).resolve().parents[1], destination)

        import plugins.memory as memory_plugins
        from agent.memory_manager import MemoryManager
        from hermes_cli.web_routers.memory_providers import (
            _memory_provider_payload,
            _write_memory_provider_config_values,
        )

        # Older hosts may still bundle mem0; exercise this checkout's plugin.
        memory_plugins._MEMORY_PLUGINS_DIR = home / "empty-bundled"
        memory_plugins._MEMORY_PLUGINS_DIR.mkdir()
        provider = memory_plugins.load_memory_provider("mem0", register_skills=False)
        assert provider is not None
        backend_module = importlib.import_module(f"{provider.__class__.__module__}._backend")
        requests = []
        synced = threading.Event()

        def respond(request):
            requests.append(json.loads(request.content))
            if requests[-1].get("infer"):
                synced.set()
            return httpx.Response(200, json={"results": []})

        def backend():
            return backend_module.SelfHostedBackend("test-key", "http://localhost:8888", transport=httpx.MockTransport(respond))

        fields = {field["key"]: field for field in _memory_provider_payload("mem0", provider)["fields"]}
        assert fields["share_conversation_context"]["kind"] == "boolean"
        assert fields["share_conversation_context"]["value"] is False

        manager = MemoryManager()
        manager.add_provider(provider)

        def add():
            result = json.loads(manager.handle_tool_call("mem0_add", {"content": "Prefers tea"}))
            assert "error" not in result, result
            return requests[-1]["metadata"]

        with patch.object(provider, "_create_backend", backend):
            try:
                manager.initialize_all("original", platform="slack", user_id="U123", session_title="Original title")
                assert add() == {"channel": "slack"}
                # Use the same schema coercion + native save_config path as the settings UI.
                _write_memory_provider_config_values("mem0", provider, {"share_conversation_context": True})
                assert json.loads((home / "mem0.json").read_text())["share_conversation_context"] is True
                provider.shutdown()
                manager.initialize_all("original", platform="slack", user_id="U123", session_title="Original title")
                assert add() == {"channel": "slack", "gateway_user_id": "U123", "session_id": "original", "session_title": "Original title"}
                for session_id, kwargs in [
                    ("new", {"reset": True}),
                    ("resume", {}),
                    ("branch", {"parent_session_id": "resume"}),
                    ("compressed", {"parent_session_id": "branch"}),
                    ("compressed", {"rewound": True}),
                ]:
                    manager.on_session_switch(session_id, **kwargs)
                    assert add() == {"channel": "slack", "gateway_user_id": "U123", "session_id": session_id}
                    assert requests[-1]["user_id"] == "shared-store"
                manager.sync_all("I prefer tea", "Noted", session_id="per-turn")
                assert synced.wait(timeout=5)
                provider._sync_thread.join(timeout=5)
                assert requests[-1]["metadata"]["session_id"] == "per-turn"
                _write_memory_provider_config_values("mem0", provider, {"share_conversation_context": False})
                provider.shutdown()
                manager.initialize_all("disabled", platform="slack", user_id="U123")
                assert add() == {"channel": "slack"}
                assert (home / "mem0.json").stat().st_mode & 0o777 == 0o600
            finally:
                manager.shutdown_all()
        print("PASS: native settings consent, manager-driven new/resume/branch/compression/rewind, and both write paths")


if __name__ == "__main__":
    main()
