"""Every Python host consumes shared handoffs through the same MCP tool."""

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

CORE = Path(__file__).resolve().parents[1] / "python"
sys.path.insert(0, str(CORE))
spec = importlib.util.spec_from_file_location("handoff_mcp", CORE / "mcp_server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def request(arguments):
    return {
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "handoff_resource",
            "arguments": arguments,
            "_meta": {"x-codex-turn-metadata": {"workspaces": {"/project root": {}}}},
        },
    }


def test_resource_tool_exposes_full_context_without_replaying_tools(monkeypatch):
    context = json.dumps({"context_type": "historical_session", "handoff": {"text": "evidence" * 1000}})
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=context, stderr="")

    monkeypatch.setattr(server.subprocess, "run", run)
    resource = "/saved handoff; $(do-not-execute).json"
    result = server.handle_request(request({"action": "resume", "resource": resource}))
    text = result["result"]["content"][0]["text"]
    guard, returned_context = text.split("\n\n", 1)
    assert returned_context == context
    assert "do not automatically re-execute recorded tools" in guard
    ts = (CORE.parent / "typescript/src/handoff.ts").read_text()
    assert json.dumps(guard + "\n\n") in ts
    command, kwargs = calls[0]
    assert command == [sys.executable, str(CORE / "session_handoff.py"), f"--resume={resource}",
                       "--cwd=/project root", "--command-output"]
    assert not kwargs.get("shell")
    tools = server.handle_request({"id": 2, "method": "tools/list"})["result"]["tools"]
    assert {tool["name"] for tool in tools} == {"search_memories", "handoff_resource"}


def test_resource_listing_is_scoped_to_host_project_and_failures_are_visible(monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1, stdout="", stderr="Invalid handoff resource")

    monkeypatch.setattr(server.subprocess, "run", run)
    result = server.handle_request(request({"action": "list"}))["result"]
    assert "--list" in calls[0]
    assert "--cwd=/project root" in calls[0]
    assert result["isError"] is True
    assert result["content"][0]["text"] == "Invalid handoff resource"


@pytest.mark.parametrize("arguments", [None, {}, {"action": "save"}, {"action": "resume"},
                                        {"action": "resume", "resource": "\0"},
                                        {"action": "list", "resource": "/unexpected"},
                                        {"action": "list", "cwd": "/other-project"}])
def test_invalid_resource_calls_do_not_execute(arguments, monkeypatch):
    def never(*args, **kwargs):
        pytest.fail("invalid call reached the runtime")

    monkeypatch.setattr(server.subprocess, "run", never)
    assert server.handle_request(request(arguments))["result"]["isError"] is True
