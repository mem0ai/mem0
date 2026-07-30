"""CLI-level behavior: what the editor's hooks actually invoke."""

import io
import json
import sys

import pytest

from mem0_agent import cli
from mem0_agent.settings import SessionState, Settings


class Args:
    def __init__(self, **kw):
        self.session_id = "sess-cli"
        for k, v in kw.items():
            setattr(self, k, v)


class FakeCtx:
    def __init__(self, tmp_path, ready=True):
        self.api = None
        self.settings = Settings(data={"capture": "balanced", "retrieval": "balanced"},
                                 path=tmp_path / "s.json")
        self.state = SessionState("sess-cli", root=tmp_path / "sessions")
        self.user_id, self.app_id = "dev", "acme-repo"
        self.session_id, self.branch = "sess-cli", "main"
        self.ready, self.reason = ready, "" if ready else "no API key"

    def provenance(self, mtype):
        return {"type": mtype}

    def log(self, *a, **k):
        pass


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    c = FakeCtx(tmp_path)
    monkeypatch.setattr(cli, "build", lambda *a, **k: c)
    return c


def run(fn, args, stdin=""):
    """Invoke a command with a controlled stdin/stdout."""
    old_in, old_out = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(stdin)
    sys.stdout = out = io.StringIO()
    try:
        code = fn(args)
    finally:
        sys.stdin, sys.stdout = old_in, old_out
    return code, out.getvalue()


def test_hook_input_tolerates_garbage(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO("not json at all"))
    assert cli.hook_input() == {}


def test_hook_input_parses_payload(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"session_id": "abc"})))
    assert cli.hook_input()["session_id"] == "abc"


def test_queued_context_is_delivered_once(ctx):
    """The detached error assist queues; the next prompt hook drains it exactly once."""
    cli.queue_context(ctx, "<mem0-recall>- [insight] restart pgbouncer</mem0-recall>")
    first = cli.drain_context(ctx)
    second = cli.drain_context(ctx)
    assert "pgbouncer" in first
    assert second == "", "a queued block must not be delivered twice"


def test_observe_emits_queued_recall(ctx, tmp_path):
    cli.queue_context(ctx, "<mem0-recall>- [insight] the fix</mem0-recall>")
    code, out = run(cli.cmd_observe, Args(transcript=None, source="prompt"),
                    stdin=json.dumps({"session_id": "sess-cli", "prompt": "why did that fail?"}))
    assert code == 0
    assert "the fix" in out


def test_commands_are_noops_without_credentials(tmp_path, monkeypatch):
    c = FakeCtx(tmp_path, ready=False)
    monkeypatch.setattr(cli, "build", lambda *a, **k: c)
    for fn, args in [
        (cli.cmd_context, Args(force=False, stats=False)),
        (cli.cmd_observe, Args(transcript=None, source="prompt")),
        (cli.cmd_flush, Args(transcript=None, reason="stop", json=False)),
        (cli.cmd_assist_error, Args(text="boom", emit=True)),
    ]:
        code, out = run(fn, args)
        assert code == 0, "a hook must never exit non-zero"
        assert out == ""


def test_main_never_propagates_an_exception(monkeypatch):
    def explode(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(cli, "cmd_health", explode)
    assert cli.main(["health"]) == 0, "a crash in memory must not break the session"


def test_config_reports_and_updates(tmp_path, monkeypatch):
    settings = Settings(data=dict(capture="balanced", retrieval="balanced",
                                  memory_mode="dual"), path=tmp_path / "s.json")
    monkeypatch.setattr(cli.Settings, "load", classmethod(lambda cls, *a, **k: settings))
    code, out = run(cli.cmd_config, Args(capture="conservative", retrieval=None, mode=None))
    assert code == 0
    assert settings.get("capture") == "conservative"
    assert "capture   = conservative" in out


def test_every_subcommand_is_registered():
    """The generated hook manifest invokes these by name; a rename must fail loudly."""
    for cmd in ("setup", "onboard", "context", "observe", "flush", "assist-error",
                "remember", "forget", "maintain", "health", "stats", "config", "sessions"):
        with pytest.raises(SystemExit) as e:
            cli.main([cmd, "--help"])
        assert e.value.code == 0


def test_hook_manifest_commands_all_exist():
    """Guards against the manifest and the CLI drifting apart."""
    import pathlib

    manifest = pathlib.Path(__file__).resolve().parents[1] / "hooks/hooks.json"
    data = json.loads(manifest.read_text())
    known = {"setup", "onboard", "context", "observe", "flush", "assist-error",
             "remember", "forget", "maintain", "health", "stats", "config", "sessions"}
    found = 0
    for entries in data["hooks"].values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                cmd = hook["command"]
                assert "bin/mem0-agent " in cmd, "hooks must call the bundled launcher"
                sub = cmd.split("bin/mem0-agent ", 1)[1].split()[0]
                assert sub in known, f"manifest invokes unknown subcommand {sub!r}"
                found += 1
    assert found >= 6


def test_session_id_accepted_on_either_side_of_the_subcommand(monkeypatch):
    """The hook manifest writes `mem0-agent context --session-id X`. argparse only
    accepts a top-level flag BEFORE the subcommand, so without a per-subcommand copy
    every SessionStart hook exits 2 and the plugin silently does nothing."""
    seen = []
    monkeypatch.setattr(cli, "cmd_context", lambda a: seen.append(getattr(a, "session_id", None)) or 0)
    cli.main(["context", "--session-id", "AFTER"])
    cli.main(["--session-id", "BEFORE", "context"])
    assert seen == ["AFTER", "BEFORE"]


def test_every_manifest_command_parses_verbatim(monkeypatch):
    """Every command line in the generated manifest must parse.

    This is the test that would have caught SessionStart exiting 2 on install:
    the manifest wrote the global --session-id flag after the subcommand.
    """
    import pathlib
    import shlex

    manifest = pathlib.Path(__file__).resolve().parents[1] / "hooks/hooks.json"
    data = json.loads(manifest.read_text())

    ran = []
    for name in ("cmd_context", "cmd_observe", "cmd_flush", "cmd_assist_error"):
        monkeypatch.setattr(cli, name, lambda a, _n=name: ran.append(_n) or 0)

    checked = 0
    for entries in data["hooks"].values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                raw = hook["command"].strip("() ").split(">/dev/null")[0]
                tokens = shlex.split(raw)
                idx = next(i for i, t in enumerate(tokens) if t.endswith("bin/mem0-agent"))
                argv = [t for t in tokens[idx + 1:] if t != "&"]
                # shell vars like "$CLAUDE_SESSION_ID" become a literal in the test
                argv = ["session-x" if t.startswith("$") else t for t in argv]
                assert cli.main(argv) == 0, f"manifest command did not run: {raw}"
                checked += 1
    assert checked >= 6
    assert ran, "the manifest should invoke real subcommands"


def test_key_resolution_prefers_env_then_plugin_config_then_keychain(monkeypatch):
    """The desktop app never sources your shell rc, so the plugin-config variable is what
    makes the app and the terminal behave identically. v1 read it; v2 originally did not."""
    from mem0_agent import settings as S

    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_MEM0_API_KEY", raising=False)
    monkeypatch.setattr(S, "KEYRING_SERVICE", "mem0-agent-test-missing")

    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_MEM0_API_KEY", "m0-legacy")
    assert S.resolve_api_key() == ("m0-legacy", "plugin config (legacy)")

    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_API_KEY", "m0-plugin")
    assert S.resolve_api_key() == ("m0-plugin", "plugin config")

    monkeypatch.setenv("MEM0_API_KEY", "m0-env")
    assert S.resolve_api_key() == ("m0-env", "env")


def test_no_shell_rc_is_ever_read():
    """v1 grepped ~/.zshrc for the key and re-exported it in plaintext. Never again.

    Checks real string literals only -- docstrings are allowed to mention the old
    behaviour, since explaining why it is gone is the point of those comments.
    """
    import ast
    import pathlib

    rc_names = (".zshrc", ".bashrc", ".bash_profile", ".profile", ".zprofile")
    offenders = []
    for f in (pathlib.Path(__file__).resolve().parents[1] / "src/mem0_agent").rglob("*.py"):
        tree = ast.parse(f.read_text())
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    docstrings.add(doc)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in docstrings:
                    continue
                if any(rc in node.value for rc in rc_names):
                    offenders.append(f"{f.name}:{node.lineno} {node.value[:40]!r}")
    assert not offenders, f"shell rc files must never be read: {offenders}"
