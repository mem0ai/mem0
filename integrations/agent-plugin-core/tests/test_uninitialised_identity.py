"""Core telemetry behaviour with NO telemetry.init(), in a real subprocess.

Why this file exists
--------------------
``telemetry.py`` lives in ``agent-plugin-core/python/`` but its only tests lived
under ``claude-code-plugin/tests/``, behind a ``conftest.py`` that calls
``configure_harness()`` and ``telemetry.init()`` at import. Core behaviour was
therefore only ever exercised inside an already-configured module.

Two processes in the real pipeline never call ``init()``:

- ``mcp_server.py``, which records every manual search;
- the detached ``python3 telemetry.py`` sender that ``spawn_flush()`` starts at
  session start, after every skill command, and when the MCP server exits.

Both fell back to module defaults, so MCP searches reported ``harness=generic``
and everything that sender delivered was labelled ``MEM0_PLUGIN`` regardless of
which of the six plugins produced it. The suite stayed green throughout.

These tests run in a fresh interpreter with no conftest, against a built host
bundle, which is the only arrangement that can catch that class of bug.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

CORE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = CORE_ROOT.parents[1]
HOSTS = {
    "claude-code": ("claude-code-plugin", "CLAUDE_CODE_PLUGIN"),
    "cursor": ("cursor-plugin", "CURSOR_PLUGIN"),
    "codex": ("codex-plugin", "CODEX_PLUGIN"),
    "kimi": ("kimi-plugin", "KIMI_PLUGIN"),
    "antigravity": ("antigravity-plugin", "ANTIGRAVITY_PLUGIN"),
    # Portable: no flush_worker and no hook_runner, so its ONLY sender is the
    # uninitialised telemetry.py. A native-only test passes here vacuously.
    "coding-agent": ("mem0-agent-plugin", "CODING_AGENT_PLUGIN"),
}


def _core_dir(directory: str) -> Path:
    return REPOSITORY_ROOT / "integrations" / directory / "core"


def _run(core: Path, data_dir: Path, body: str) -> str:
    """Execute `body` in a fresh interpreter with only the host's core on sys.path."""
    script = f"import sys; sys.path.insert(0, {str(core)!r})\n{body}"
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={
            "MEM0_CODE_DATA_DIR": str(data_dir),
            "PATH": "/usr/bin:/bin",
            "HOME": str(data_dir),
        },
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.mark.parametrize("harness,spec", sorted(HOSTS.items()))
def test_identity_resolves_without_init(harness, spec):
    """Every built host knows what it is with no configuration call at all."""
    directory, source_tag = spec
    core = _core_dir(directory)
    if not core.exists():
        pytest.skip(f"{directory} is not built in this tree")

    with tempfile.TemporaryDirectory() as tmp:
        out = _run(
            core,
            Path(tmp),
            "import telemetry; print(telemetry._harness, telemetry._source_tag)",
        )
    assert out == f"{harness} {source_tag}"


def test_mcp_server_records_the_real_harness():
    """mcp_server imports telemetry and never initialises it (server.py has no init).

    Its recorded events used to carry harness=generic for every plugin.
    """
    core = _core_dir("claude-code-plugin")
    if not core.exists():
        pytest.skip("claude-code-plugin is not built in this tree")

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _run(
            core,
            data_dir,
            "import mcp_server, telemetry; telemetry.record('search', trigger='mcp-search')",
        )
        spooled = (data_dir / "telemetry.jsonl").read_text(encoding="utf-8").strip()

    event = json.loads(spooled)
    assert event["properties"]["harness"] == "claude-code"
    assert event["properties"]["source"] == "CLAUDE_CODE_PLUGIN"


def test_the_detached_sender_does_not_relabel_events():
    """`python3 telemetry.py` is the sender spawn_flush() starts, and never inits.

    source is stamped at record time now, so which process sends is irrelevant.
    """
    core = _core_dir("claude-code-plugin")
    if not core.exists():
        pytest.skip("claude-code-plugin is not built in this tree")

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _run(core, data_dir, "import telemetry; telemetry.record('search')")

        captured = data_dir / "captured.json"
        # Drain with a fresh, unconfigured interpreter, capturing the payload
        # instead of posting it.
        _run(
            core,
            data_dir,
            "import json, telemetry\n"
            "sent = []\n"
            "telemetry._post = lambda payload, url: sent.append(payload) or True\n"
            "telemetry.flush()\n"
            f"open({str(captured)!r}, 'w').write(json.dumps(sent))",
        )
        payloads = json.loads(captured.read_text(encoding="utf-8"))

    batches = [p for p in payloads if "batch" in p]
    assert batches, "nothing was sent"
    properties = batches[0]["batch"][0]["properties"]
    assert properties["source"] == "CLAUDE_CODE_PLUGIN"
    assert properties["harness"] == "claude-code"


def test_every_event_carries_a_uuid_for_dedupe():
    core = _core_dir("claude-code-plugin")
    if not core.exists():
        pytest.skip("claude-code-plugin is not built in this tree")

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        _run(core, data_dir, "import telemetry; telemetry.record('search'); telemetry.record('flush')")
        lines = (data_dir / "telemetry.jsonl").read_text(encoding="utf-8").strip().splitlines()

    ids = [json.loads(line)["uuid"] for line in lines]
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_source_tag_defaults_agree_between_the_two_modules():
    """configure_harness and telemetry.init must derive the same tag.

    They disagreed: `<host>_plugin` in one and `MEM0_<HOST>_PLUGIN` in the other,
    so one plugin could emit three different source values depending on which
    process sent the batch.
    """
    core = _core_dir("claude-code-plugin")
    if not core.exists():
        pytest.skip("claude-code-plugin is not built in this tree")

    with tempfile.TemporaryDirectory() as tmp:
        out = _run(
            core,
            Path(tmp),
            "import memory_core, telemetry\n"
            "memory_core.configure_harness('kimi')\n"
            "telemetry.init(harness='kimi')\n"
            "print(memory_core.harness_config()['source_tag'].upper(), telemetry._source_tag)",
        )
    left, right = out.split()
    assert left == right == "KIMI_PLUGIN"


def test_the_plugin_declares_its_surface_in_the_body_and_the_headers():
    """Body and headers both, because only the body works on every backend."""
    core = _core_dir("claude-code-plugin")
    if not core.exists():
        pytest.skip("claude-code-plugin is not built in this tree")

    with tempfile.TemporaryDirectory() as tmp:
        out = _run(
            core,
            Path(tmp),
            "import json, memory_core\n"
            "h = memory_core.platform_headers('k')\n"
            "print(json.dumps({'source': h.get('X-Mem0-Source'),"
            " 'app': h.get('X-Application'),"
            " 'client': h.get('X-Mem0-Client'),"
            " 'auth': h.get('Authorization'),"
            " 'ctype': h.get('Content-Type')}))",
        )
    headers = json.loads(out)
    assert headers["source"] == "MEM0_PLUGIN"
    assert headers["app"] == "claude-code"
    assert headers["client"].startswith("mem0-plugin/")
    # The transport headers the three call sites relied on must survive.
    assert headers["auth"] == "Token k"
    assert headers["ctype"] == "application/json"


def _session_start(core: Path, data_dir: Path) -> list[str]:
    """Drive the real hook_runner session-start path and return lifecycle events."""
    recorded = "\n".join(
        [
            "import io, json, sys",
            f"sys.path.insert(0, {str(core)!r})",
            "import telemetry, hook_runner",
            "seen = []",
            "telemetry.record = lambda event, **kw: seen.append(event) or None",
            "telemetry.spawn_flush = lambda: False",
            # run() reads sys.argv through argparse; it takes no positional args.
            "sys.argv = ['hook_runner', 'session-start']",
            "sys.stdin = io.StringIO('{}')",
            "hook_runner.run()",
            "print(json.dumps([e for e in seen if e in ('install', 'upgrade')]))",
        ]
    )
    import json as _json

    return _json.loads(_run(core, data_dir, recorded) or "[]")


def test_a_fresh_install_reports_install_not_upgrade():
    """The decision must survive the writes hook_runner does before asking.

    claim_install() is reached only after cache_plugin_api_key() has written
    `api-key` and EvidenceStore() has created `evidence.sqlite3`. Asking "is the
    data dir empty" at that point always saw content, so code.install could
    never fire and every new user was counted as an upgrade.
    """
    core = _core_dir("claude-code-plugin")
    if not core.exists():
        pytest.skip("claude-code-plugin is not built in this tree")

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        assert _session_start(core, data_dir) == ["install"]


def test_the_lifecycle_event_fires_exactly_once():
    core = _core_dir("claude-code-plugin")
    if not core.exists():
        pytest.skip("claude-code-plugin is not built in this tree")

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        first = _session_start(core, data_dir)
        second = _session_start(core, data_dir)
        third = _session_start(core, data_dir)

    assert first == ["install"]
    assert second == []
    assert third == []


def test_an_existing_data_dir_reports_upgrade():
    core = _core_dir("claude-code-plugin")
    if not core.exists():
        pytest.skip("claude-code-plugin is not built in this tree")

    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        data_dir.mkdir(parents=True)
        # A 0.2.x leftover: the data dir survives the upgrade.
        (data_dir / "requirements.txt").write_text("mem0ai\n", encoding="utf-8")
        assert _session_start(core, data_dir) == ["upgrade"]
