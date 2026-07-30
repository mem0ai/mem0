"""The hook manifests are generated, so these tests guard the generator and the spec.

v1's four hand-written manifests drifted; the drift test below is the mechanism that
makes that impossible now.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1]
HOOKS = PKG / "hooks"
sys.path.insert(0, str(HOOKS))

import generate  # noqa: E402

EXPECTED_EVENTS = {
    "SessionStart", "UserPromptSubmit", "PostToolUse", "Stop", "PreCompact", "SessionEnd",
}


@pytest.fixture(scope="module")
def spec():
    return generate.load_spec()


@pytest.fixture(scope="module")
def manifest(spec):
    return generate.build_manifest(spec, "claude-code")


# ------------------------------------------------------------------ spec parsing
def test_spec_parses_into_editors_and_hooks(spec):
    assert isinstance(spec["hooks"], list) and spec["hooks"]
    ids = [e["id"] for e in spec["editors"]]
    assert ids[0] == "claude-code", "claude-code is the reference dialect and comes first"
    assert {"cursor", "codex"} <= set(ids), "other editors stay declared so gaps are visible"
    assert [e["id"] for e in generate.supported_editors(spec)] == ["claude-code"]


def test_every_hook_declares_its_contract(spec):
    for entry in spec["hooks"]:
        assert entry["why"], f"{entry['id']} must say why it exists"
        assert isinstance(entry["local_only"], bool)
        assert isinstance(entry["background"], bool)
        assert entry["command"].startswith("${CLAUDE_PLUGIN_ROOT}/bin/mem0-agent "), (
            "hooks must call the plugin's bundled launcher, not a global console script "
            "(a pyenv shim resolves against the directory's Python version and can vanish)"
        )


def test_tiny_parser_handles_quotes_comments_and_nesting():
    parsed = generate.parse_yaml(
        'top: 1  # trailing comment\n'
        '# whole line comment\n'
        'block:\n'
        '  flag: true\n'
        '  none: null\n'
        '  text: "a: b # not a comment"\n'
        'items:\n'
        '  - id: one\n'
        '    n: 2\n'
        '  - id: two\n'
        '    nested:\n'
        '      k: "v"\n'
    )
    assert parsed == {
        "top": 1,
        "block": {"flag": True, "none": None, "text": "a: b # not a comment"},
        "items": [{"id": "one", "n": 2}, {"id": "two", "nested": {"k": "v"}}],
    }


# --------------------------------------------------------------- manifest shape
def test_manifest_contains_every_declared_event(spec, manifest):
    declared = {e["event"] for e in spec["hooks"]}
    assert declared == EXPECTED_EVENTS
    assert set(manifest["hooks"]) == declared
    for event, groups in manifest["hooks"].items():
        for group in groups:
            for step in group["hooks"]:
                assert step["type"] == "command", event
                assert "mem0-agent " in step["command"]
                assert isinstance(step["timeout"], int)


def test_manifest_matches_claude_code_schema(manifest):
    start = manifest["hooks"]["SessionStart"][0]
    assert start["matcher"] == "startup|resume|compact"
    assert "--session-id" in start["hooks"][0]["command"]
    # Events without a matcher must omit the key rather than emit null.
    assert "matcher" not in manifest["hooks"]["Stop"][0]
    assert manifest["hooks"]["PostToolUse"][0]["matcher"] == "Bash"


def test_user_prompt_submit_is_declared_local_only(spec, manifest):
    entry = next(e for e in spec["hooks"] if e["event"] == "UserPromptSubmit")
    assert entry["local_only"] is True
    command = manifest["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    assert "MEM0_LOCAL_ONLY=1" in command, "the local-only contract must be machine-enforced"
    assert entry["background"] is False and entry["blocking"] is True


def test_write_hooks_are_not_shell_backgrounded(spec, manifest):
    """These hooks must NOT be wrapped in `( ... &)`.

    A shell-backgrounded hook loses stdin the instant the parent exits, so the child
    sees no session_id and no transcript_path and drains the wrong buffer -- observed
    live as flagged candidates that were never written. The CLI now reads the payload
    first and re-execs itself detached, so the hook still returns in milliseconds.
    """
    for event in ("PostToolUse", "Stop", "PreCompact", "SessionEnd"):
        command = manifest["hooks"][event][0]["hooks"][0]["command"]
        assert not command.strip().endswith("&)"), f"{event} must not be backgrounded by the shell"
        assert "mem0-agent" in command, event


def test_editor_env_is_pinned(manifest):
    for groups in manifest["hooks"].values():
        for group in groups:
            for step in group["hooks"]:
                assert "MEM0_EDITOR=claude-code" in step["command"]


def test_unsupported_editors_are_not_emitted(spec):
    for ed in spec["editors"]:
        if not ed["supported"]:
            assert not generate.output_path(spec, ed["id"]).exists(), ed["id"]


# ------------------------------------------------------------------- validation
def test_validate_rejects_networked_user_prompt_hook(spec):
    broken = json.loads(json.dumps(spec))
    entry = next(e for e in broken["hooks"] if e["event"] == "UserPromptSubmit")
    entry["local_only"] = False
    with pytest.raises(generate.SpecError, match="local_only"):
        generate.validate(broken)


def test_validate_rejects_unknown_hook_field(spec):
    broken = json.loads(json.dumps(spec))
    broken["hooks"][0]["retries"] = 3
    with pytest.raises(generate.SpecError, match="unknown fields"):
        generate.validate(broken)


def test_validate_rejects_background_and_blocking(spec):
    broken = json.loads(json.dumps(spec))
    broken["hooks"][0]["background"] = True
    broken["hooks"][0]["blocking"] = True
    with pytest.raises(generate.SpecError, match="cannot also be blocking"):
        generate.validate(broken)


# ------------------------------------------------------------------------ drift
def test_committed_manifest_is_up_to_date(spec, manifest):
    path = generate.output_path(spec, "claude-code")
    assert path.exists(), "run `python3 hooks/generate.py`"
    assert json.loads(path.read_text()) == manifest


def test_check_flag_passes_against_committed_file():
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "generate.py"), "--check"],
        capture_output=True, text=True, cwd=PKG,
    )
    assert proc.returncode == 0, proc.stderr


def test_check_flag_detects_drift(tmp_path, spec):
    path = generate.output_path(spec, "claude-code")
    original = path.read_text()
    try:
        path.write_text(original.replace('"timeout": 10', '"timeout": 99'))
        proc = subprocess.run(
            [sys.executable, str(HOOKS / "generate.py"), "--check"],
            capture_output=True, text=True, cwd=PKG,
        )
        assert proc.returncode == 1
        assert "DRIFT" in proc.stderr
    finally:
        path.write_text(original)


def test_generate_is_idempotent(spec):
    path = generate.output_path(spec, "claude-code")
    before = path.read_text()
    proc = subprocess.run(
        [sys.executable, str(HOOKS / "generate.py")], capture_output=True, text=True, cwd=PKG
    )
    assert proc.returncode == 0, proc.stderr
    assert path.read_text() == before
