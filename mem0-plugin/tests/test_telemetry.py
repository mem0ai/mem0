"""Tests for telemetry.py — fire-and-forget PostHog plugin telemetry."""

from __future__ import annotations

import json
import os
import sys
import urllib.error

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS_DIR))


def test_import_succeeds():
    import telemetry

    assert hasattr(telemetry, "emit")
    assert hasattr(telemetry, "main")


def test_opt_out_skips_send(monkeypatch):
    import telemetry

    monkeypatch.setenv("MEM0_TELEMETRY", "false")
    sent = []
    monkeypatch.setattr(telemetry, "send", lambda p: sent.append(p))
    telemetry.emit("session_start")
    assert sent == []


def test_opt_out_variants(monkeypatch):
    import telemetry

    for val in ("0", "no", "off", "FALSE", "No"):
        monkeypatch.setenv("MEM0_TELEMETRY", val)
        assert not telemetry.is_enabled()


def test_enabled_by_default(monkeypatch):
    import telemetry

    monkeypatch.delenv("MEM0_TELEMETRY", raising=False)
    assert telemetry.is_enabled()


def test_posthog_payload_structure(monkeypatch):
    import telemetry

    monkeypatch.setenv("MEM0_RESOLVED_USER_ID", "testuser")
    monkeypatch.setenv("MEM0_PROJECT_ID", "test-project")
    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_MEM0_API_KEY", raising=False)

    payload = telemetry.build_posthog_payload("plugin.session_start", {"memory_count": 5})

    assert payload["api_key"] == telemetry.POSTHOG_API_KEY
    assert payload["event"] == "plugin.session_start"
    assert "distinct_id" in payload
    assert payload["properties"]["source"] == "plugin"
    assert isinstance(payload["properties"]["plugin_version"], str)
    assert payload["properties"]["plugin_version"] != ""
    assert payload["properties"]["memory_count"] == 5
    assert payload["properties"]["$process_person_profile"] is False

    raw = json.dumps(payload)
    assert "testuser" not in raw
    assert "test-project" not in raw


def test_system_props_override_caller_props(monkeypatch):
    """H8: system properties must win over caller-supplied properties."""
    import telemetry

    monkeypatch.setenv("MEM0_RESOLVED_USER_ID", "testuser")
    monkeypatch.setenv("MEM0_PROJECT_ID", "test-project")
    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_MEM0_API_KEY", raising=False)

    # Caller tries to override system-controlled properties
    caller_props = {
        "source": "CALLER_OVERRIDE",
        "platform": "CALLER_OVERRIDE",
        "plugin_version": "CALLER_OVERRIDE",
        "memory_count": 42,
    }
    payload = telemetry.build_posthog_payload("plugin.test", caller_props)
    props = payload["properties"]

    # System props must win
    assert props["source"] == "plugin"
    assert props["platform"] == telemetry.detect_platform()
    assert props["plugin_version"] == telemetry.PLUGIN_VERSION
    # Caller-only props still present
    assert props["memory_count"] == 42


def test_distinct_id_from_api_key(monkeypatch):
    import hashlib

    import telemetry

    monkeypatch.setenv("MEM0_API_KEY", "m0-testkey123")
    expected = hashlib.sha256(b"m0-testkey123").hexdigest()[:32]
    assert telemetry._distinct_id() == expected


def test_distinct_id_fallback_no_key(monkeypatch):
    import telemetry

    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_MEM0_API_KEY", raising=False)
    monkeypatch.setenv("MEM0_RESOLVED_USER_ID", "kartik")
    assert telemetry._distinct_id() == telemetry._sha256("kartik")


def test_hash_deterministic():
    import telemetry

    h1 = telemetry._sha256("same-value")
    h2 = telemetry._sha256("same-value")
    assert h1 == h2
    assert h1 != telemetry._sha256("different-value")


def test_platform_claude_code(monkeypatch):
    import telemetry

    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CURSOR_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CODEX_PLUGIN_ROOT", raising=False)
    assert telemetry.detect_platform() == "claude-code"


def test_platform_cursor(monkeypatch):
    import telemetry

    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.setenv("CURSOR_PLUGIN_ROOT", "/path")
    monkeypatch.delenv("CODEX_PLUGIN_ROOT", raising=False)
    assert telemetry.detect_platform() == "cursor"


def test_platform_codex(monkeypatch):
    import telemetry

    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CURSOR_PLUGIN_ROOT", raising=False)
    monkeypatch.setenv("CODEX_PLUGIN_ROOT", "/path")
    assert telemetry.detect_platform() == "codex"


def test_sampling_drops_at_high_random(monkeypatch):
    import telemetry

    monkeypatch.setattr(telemetry.random, "random", lambda: 0.5)
    assert telemetry._should_sample() is False


def test_sampling_sends_at_low_random(monkeypatch):
    import telemetry

    monkeypatch.setattr(telemetry.random, "random", lambda: 0.05)
    assert telemetry._should_sample() is True


def test_send_fails_silently(monkeypatch):
    import telemetry

    def raise_error(req, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(telemetry.urllib.request, "urlopen", raise_error)
    telemetry.send({"event": "test"})


def test_cli_exits_zero_when_disabled(monkeypatch):
    import telemetry

    monkeypatch.setenv("MEM0_TELEMETRY", "false")
    monkeypatch.setattr(sys, "argv", ["telemetry.py", "session_start"])
    assert telemetry.main() == 0


def test_cli_no_args_exits_nonzero(monkeypatch):
    import telemetry

    monkeypatch.delenv("MEM0_TELEMETRY", raising=False)
    monkeypatch.setattr(sys, "argv", ["telemetry.py"])
    assert telemetry.main() == 1
