"""Offline contract smoke against a real Hermes checkout.

HERMES_SOURCE=/path/to/hermes-agent python tests/smoke_hermes.py
Host modules are real; only the Mem0 backend is mocked. Uses a temporary profile.
"""

import json
import os
import pathlib
import shutil
import sys
import tempfile
from unittest.mock import Mock

hermes_source = pathlib.Path(os.environ["HERMES_SOURCE"]).resolve()
plugin_source = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(hermes_source))
with tempfile.TemporaryDirectory() as d:
    os.environ["HERMES_HOME"] = d
    os.environ["MEM0_API_KEY"] = "test-key"
    import plugins.memory as pm
    from agent.memory_manager import MemoryManager

    destination = pathlib.Path(d) / "plugins" / "mem0"
    shutil.copytree(plugin_source, destination)
    assert pm.find_provider_dir("mem0") == hermes_source / "plugins" / "memory" / "mem0"
    pm._MEMORY_PLUGINS_DIR = pathlib.Path(d) / "empty-bundled"
    pm._MEMORY_PLUGINS_DIR.mkdir()
    provider = pm.load_memory_provider("mem0", register_skills=False)
    assert provider is not None
    assert provider.__class__.__module__.startswith("_hermes_user_memory.")
    backend = Mock()
    backend.search.return_value = []
    backend.add.return_value = {}
    provider._create_backend = lambda: backend
    manager = MemoryManager()
    manager.add_provider(provider)
    manager.initialize_all("s1", platform="cli", user_id="alice")
    result = manager.handle_tool_call("mem0_search", {"query": "favorite programming language"})
    assert json.loads(result)["result"] == "No relevant memories found."
    manager.sync_all(
        "I prefer Python for tooling. " * 100 + "UNIQUE_END_MARKER",
        "I will remember that.",
        session_id="s2",
        messages=[{"role": "tool", "content": "NOT_FOR_CAPTURE"}],
        turn_author={"id": "alice"},
    )
    manager.shutdown_all()
    assert backend.add.call_count >= 1
    sent = str(backend.add.call_args_list)
    assert "UNIQUE_END_MARKER" in sent and "NOT_FOR_CAPTURE" not in sent
    assert backend.add.call_args.kwargs["run_id"] == "s2"
    print("PASS:", hermes_source, "real external loader + MemoryManager lifecycle/tools/full capture/session ID")
