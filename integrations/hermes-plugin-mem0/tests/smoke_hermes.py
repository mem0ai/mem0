"""Real Hermes + Mem0 SDK + local Qdrant; only the model API is simulated.

HERMES_SOURCE=/path/to/hermes-agent python tests/smoke_hermes.py
Requires the Hermes dependencies, mem0ai, and qdrant-client in the active environment.
All configuration, credentials, and database files are temporary.
"""

import importlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


class ModelAPI(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        if self.headers.get("Authorization") != "Bearer local-test":
            self.send_error(401)
            return
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.calls.append(self.path)
        if self.path == "/v1/embeddings":
            result = {
                "object": "list",
                "data": [{"object": "embedding", "index": i, "embedding": [1.0, 0.0, 0.0]}
                         for i, _ in enumerate(body["input"])],
                "model": "test-embedding",
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            }
        elif self.path == "/v1/chat/completions":
            result = {
                "id": "test-completion", "object": "chat.completion", "created": 0, "model": "gpt-4.1-mini",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content":
                    json.dumps({"facts": ["Prefers green tea."], "memory": [
                        {"id": "0", "text": "Prefers green tea.", "event": "ADD"}]})}}],
            }
        else:
            self.send_error(404)
            return
        encoded = json.dumps(result).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main():
    hermes_source = Path(os.environ["HERMES_SOURCE"]).resolve()
    sys.path.insert(0, str(hermes_source))
    with tempfile.TemporaryDirectory() as temporary:
        home = Path(temporary)
        os.environ.update(HERMES_HOME=temporary, MEM0_DIR=str(home / "mem0-data"), MEM0_TELEMETRY="false")
        (home / "mem0-data").mkdir()
        server = ThreadingHTTPServer(("127.0.0.1", 0), ModelAPI)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/v1"
            config = {
                "mode": "oss", "user_id": "existing-user", "agent_id": "hermes",
                "oss": {
                    "llm": {"provider": "openai", "config": {
                        "model": "gpt-4.1-mini", "api_key": "local-test", "openai_base_url": url}},
                    "embedder": {"provider": "openai", "config": {
                        "model": "test-embedding", "embedding_dims": 3,
                        "api_key": "local-test", "openai_base_url": url}},
                    "vector_store": {"provider": "qdrant", "config": {"path": str(home / "qdrant")}},
                },
            }
            (home / "mem0.json").write_text(json.dumps(config))
            destination = home / "plugins" / "mem0"
            shutil.copytree(Path(__file__).resolve().parents[1], destination)
            import plugins.memory as memory_plugins
            from agent.memory_manager import MemoryManager

            # Simulate bundled-provider removal only inside this test process.
            memory_plugins._MEMORY_PLUGINS_DIR = home / "empty-bundled"
            memory_plugins._MEMORY_PLUGINS_DIR.mkdir()
            assert memory_plugins.find_provider_dir("mem0") == destination
            provider = memory_plugins.load_memory_provider("mem0", register_skills=False)
            assert provider is not None and provider.__class__.__module__.startswith("_hermes_user_memory.")
            setup = importlib.import_module(f"{provider.__class__.__module__}._setup")
            from hermes_cli.memory_setup import cmd_setup_provider, cmd_status

            output = io.StringIO()
            arguments = ["hermes", "memory", "setup", "mem0", "--mode", "platform", "--api-key", "local-test"]
            with patch.object(sys, "argv", arguments), patch.object(sys, "stdin", io.StringIO("\n\n")):
                with patch.object(setup, "_curses_select", return_value=0), redirect_stdout(output):
                    cmd_setup_provider("mem0")
            assert json.loads((home / "mem0.json").read_text())["user_id"] == "existing-user"
            provider.save_config(config, home)
            assert (home / "mem0.json").stat().st_mode & 0o777 == 0o600
            with redirect_stdout(output):
                cmd_status(None)
            assert "installed ✓" in output.getvalue() and "available ✓" in output.getvalue()
            assert (home / ".env").stat().st_mode & 0o777 == 0o600
            manager = MemoryManager()
            manager.add_provider(provider)
            manager.initialize_all("smoke-session", platform="cli", user_id="gateway-user")
            assert provider._backend is not None, getattr(provider, "_init_error", "initialization failed")
            # Desktop keeps restored sessions alive while opening another conversation.
            peer = type(provider)()
            peer.initialize("second-desktop-session", platform="desktop")
            assert peer._backend is not None, getattr(peer, "_init_error", "second session failed")
            backend = importlib.import_module(f"{provider.__class__.__module__}._backend")
            # A symlink must resolve to the same owner; simultaneous callers must not race to open it.
            alias = home / "qdrant-alias"
            alias.symlink_to(home / "qdrant", target_is_directory=True)
            aliased = deepcopy(config["oss"])
            aliased["vector_store"]["config"]["path"] = str(alias)
            with ThreadPoolExecutor(max_workers=3) as pool:
                siblings = list(pool.map(lambda _: backend.OSSBackend(aliased), range(3)))
                try:
                    writes = [pool.submit(sibling.add, [{"role": "user", "content": f"Private fact {i}."}],
                                          user_id=f"separate-user-{i}", agent_id="hermes")
                              for i, sibling in enumerate(siblings)]
                    for write in writes:
                        write.result()
                    for i, sibling in enumerate(siblings):
                        found = sibling.search("fact", filters={"user_id": f"separate-user-{i}", "agent_id": "hermes"})
                        assert [item["memory"] for item in found] == [f"Private fact {i}."]
                finally:
                    for sibling in siblings:
                        sibling.close()
                        sibling.close()
            # Reject conflicting live settings without closing or modifying the existing owner.
            for section, key, value in (("llm", "api_key", "another-key"),
                                        ("embedder", "embedding_dims", 4),
                                        ("vector_store", "collection_name", "another-collection")):
                conflicting = deepcopy(config["oss"])
                conflicting[section]["config"][key] = value
                try:
                    backend.OSSBackend(conflicting)
                except ValueError as exc:
                    assert "Existing memories were preserved" in str(exc)
                else:
                    raise AssertionError("Conflicting local store configuration was accepted")
            with patch("hermes_constants.get_hermes_home", return_value=home / "different-profile"):
                try:
                    backend.OSSBackend(config["oss"])
                except ValueError as exc:
                    assert "different profile or configuration" in str(exc)
                else:
                    raise AssertionError("Another profile inherited an active local store")

            def tool(name, **arguments):
                result = json.loads(manager.handle_tool_call(name, arguments))
                assert "error" not in result, result
                return result

            try:
                assert tool("mem0_add", content="Prefers Python.")["result"] == "Fact stored."
                memories = tool("mem0_search", query="language")["results"]
                assert len(memories) == 1 and memories[0]["memory"] == "Prefers Python."
                memory_id = memories[0]["id"]
                assert "Prefers Python." in peer.prefetch("language")
                tool("mem0_update", memory_id=memory_id, text="Prefers Rust.")
                assert "Prefers Rust." in provider.prefetch("language preference")
                assert tool("mem0_search", query="language")["results"][0]["memory"] == "Prefers Rust."
                tool("mem0_delete", memory_id=memory_id)
                assert tool("mem0_search", query="language")["result"] == "No relevant memories found."
                manager.sync_all("I prefer green tea.", "Noted.", session_id="smoke-session")
                assert provider._user_id == "existing-user"
            finally:
                manager.shutdown_all()
            assert provider._backend is None
            try:
                assert "error" not in json.loads(peer.handle_tool_call("mem0_add", {"content": "Prefers evening walks."}))
                assert "green tea" in peer.prefetch("tea preference").lower()
            finally:
                peer.shutdown()
            # A changed embedder must fail without destroying the existing collection.
            config["oss"]["embedder"]["config"]["embedding_dims"] = 4
            provider.save_config(config, home)
            mismatched = type(provider)()
            mismatched.initialize("mismatched-session")
            assert mismatched._backend is None and "Existing memories were preserved" in mismatched._init_error
            config["oss"]["embedder"]["config"]["embedding_dims"] = 3
            # Resolve embedder credentials from the active profile, not another profile's process env.
            del config["oss"]["embedder"]["config"]["api_key"]
            del config["oss"]["embedder"]["config"]["openai_base_url"]
            provider.save_config(config, home)
            from agent.secret_scope import (
                reset_secret_scope,
                set_multiplex_active,
                set_secret_scope,
            )

            resumed = type(provider)()
            with patch.dict(os.environ, {"OPENAI_API_KEY": "wrong-profile", "OPENAI_API_BASE": "http://127.0.0.1:1/v1"}):
                set_multiplex_active(True)
                token = set_secret_scope({"OPENAI_API_KEY": "local-test", "OPENAI_BASE_URL": url})
                try:
                    resumed.initialize("resumed-session", user_id="different-gateway-user")
                finally:
                    reset_secret_scope(token)
                    set_multiplex_active(False)
            try:
                assert resumed._backend is not None
                found = json.loads(resumed.handle_tool_call("mem0_search", {"query": "drink"}))
                assert "results" in found, found
                assert any(item["memory"] == "Prefers green tea." for item in found["results"])
            finally:
                resumed.shutdown()
            assert "/v1/chat/completions" in ModelAPI.calls
            print("PASS: external Hermes loader, CLI setup/status, real Mem0/Qdrant CRUD, recall, background extraction,")
            print("      concurrent sessions, scoped identities, canonical paths, conflicting settings, last-owner shutdown,")
            print("      profile credentials, private files, dimension safety and persistence across restart. Model responses simulated locally.")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)


if __name__ == "__main__":
    main()
