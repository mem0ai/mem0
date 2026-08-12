"""Tests for auto_setup_instructions.py -- the background memory-policy installer.

Covers the pure, network-free logic:
  - policy resolution (env var precedence over settings)
  - fingerprints (api key + policy text)
  - state-file gating (load / save / is_applied)
  - idempotent apply via an injected fake client (no SDK, no network)
"""

from __future__ import annotations

import os
import sys

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import auto_setup_instructions as asi  # noqa: E402


# --------------------------------------------------------------------------- #
# Fake client (dependency injection — apply_instructions takes a client)       #
# --------------------------------------------------------------------------- #
class _FakeProject:
    def __init__(self, current):
        self._current = current
        self.update_calls: list = []

    def get(self, fields=None):
        return {"custom_instructions": self._current}

    def update(self, custom_instructions=None, **kwargs):
        self.update_calls.append(custom_instructions)
        return {"ok": True}


class _FakeClient:
    def __init__(self, current):
        self.project = _FakeProject(current)


# --------------------------------------------------------------------------- #
# Policy resolution                                                            #
# --------------------------------------------------------------------------- #
def test_resolve_prefers_env_over_settings(monkeypatch):
    monkeypatch.setenv("MEM0_CUSTOM_INSTRUCTIONS", "  from env  ")
    monkeypatch.setattr(asi, "load_settings", lambda: {"custom_instructions": "from settings"})
    assert asi.resolve_instructions() == "from env"


def test_resolve_falls_back_to_settings(monkeypatch):
    monkeypatch.delenv("MEM0_CUSTOM_INSTRUCTIONS", raising=False)
    monkeypatch.setattr(asi, "load_settings", lambda: {"custom_instructions": "  from settings  "})
    assert asi.resolve_instructions() == "from settings"


def test_resolve_empty_when_unset(monkeypatch):
    monkeypatch.delenv("MEM0_CUSTOM_INSTRUCTIONS", raising=False)
    monkeypatch.setattr(asi, "load_settings", lambda: {"custom_instructions": ""})
    assert asi.resolve_instructions() == ""


# --------------------------------------------------------------------------- #
# Fingerprints                                                                 #
# --------------------------------------------------------------------------- #
def test_instructions_fingerprint_is_stable_hex():
    fp = asi.instructions_fingerprint("Remember decisions; ignore secrets.")
    assert isinstance(fp, str)
    assert len(fp) == 16
    assert all(c in "0123456789abcdef" for c in fp)


def test_instructions_fingerprint_whitespace_insensitive():
    """Reflowing whitespace must not count as a policy change."""
    a = asi.instructions_fingerprint("Remember   decisions;\n  ignore secrets.")
    b = asi.instructions_fingerprint("Remember decisions; ignore secrets.")
    assert a == b


def test_instructions_fingerprint_changes_with_content():
    assert asi.instructions_fingerprint("policy A") != asi.instructions_fingerprint("policy B")


def test_apikey_fingerprint_is_stable_and_opaque():
    key = "m0-supersecret-abc123"
    fp = asi.apikey_fingerprint(key)
    assert len(fp) == 16
    assert "supersecret" not in fp
    assert key not in fp


# --------------------------------------------------------------------------- #
# State file: load / save / gating                                            #
# --------------------------------------------------------------------------- #
def test_load_state_missing_file_returns_empty(tmp_path):
    assert asi.load_state(str(tmp_path / "nope.json")) == {}


def test_save_then_load_roundtrip_creates_parent_dir(tmp_path):
    p = tmp_path / "nested" / "instructions_setup.json"
    asi.save_state({"abc123": "deadbeef00000000"}, str(p))
    assert p.is_file()
    assert asi.load_state(str(p)) == {"abc123": "deadbeef00000000"}


def test_is_applied_true_only_on_exact_match():
    state = {"keyfp": "instrfp"}
    assert asi.is_applied(state, "keyfp", "instrfp") is True
    assert asi.is_applied(state, "keyfp", "OTHER") is False
    assert asi.is_applied({}, "keyfp", "instrfp") is False


# --------------------------------------------------------------------------- #
# apply_instructions: idempotent, network-free via fake client                #
# --------------------------------------------------------------------------- #
def test_apply_skips_update_when_already_matching():
    client = _FakeClient("Remember decisions; ignore secrets.")
    result = asi.apply_instructions(client, "Remember decisions;  ignore secrets.")
    assert result == "already-configured"
    assert client.project.update_calls == []  # must NOT hit the write endpoint


def test_apply_updates_when_none_set():
    client = _FakeClient(None)
    result = asi.apply_instructions(client, "Remember decisions.")
    assert result == "applied"
    assert client.project.update_calls == ["Remember decisions."]


def test_apply_updates_when_policy_differs():
    client = _FakeClient("old policy")
    result = asi.apply_instructions(client, "new policy")
    assert result == "applied"
    assert client.project.update_calls == ["new policy"]


def test_fetch_current_instructions_handles_non_dict():
    class Weird:
        project = type("P", (), {"get": staticmethod(lambda fields=None: "unexpected")})()

    assert asi.fetch_current_instructions(Weird()) is None
