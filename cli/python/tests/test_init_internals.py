"""Unit tests for init internals — decision tree primitives + plugin sync.

These tests exercise the units that the high-level subprocess parity tests in
``test_agent_mode.py`` deliberately can't reach:

  - ``_ping_key`` must NOT treat network errors as "invalid key" (else a VPN
    flap silently mints a new shadow over a working key).
  - ``plugin_sync`` must only update entries that already exist, preserve
    trailing newlines, and never mangle other lines.
  - The 403→ratelimit translation in ``bootstrap_via_backend`` surfaces the
    real cause instead of DRF's opaque "You do not have permission" string.

Mirror surface lives in ``cli/node/tests/agent-mode.test.ts``; if you add a
behavioral assertion here, mirror it on the Node side and vice versa.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from mem0_cli.commands.init_cmd import _ping_key
from mem0_cli.plugin_sync import _update_claude_settings, _update_shell_rc

# ── _ping_key ──────────────────────────────────────────────────────────────


class _Resp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


def test_ping_key_200_is_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _Resp(200))
    assert _ping_key("k", "http://x") is True


def test_ping_key_401_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _Resp(401))
    assert _ping_key("k", "http://x") is False


def test_ping_key_403_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _Resp(403))
    assert _ping_key("k", "http://x") is False


def test_ping_key_5xx_is_not_definitively_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    # Transient upstream failure must NOT cause a shadow to be minted.
    monkeypatch.setattr(httpx, "get", lambda *a, **kw: _Resp(503))
    assert _ping_key("k", "http://x") is True


def test_ping_key_connect_error_prefers_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    # Network blip (DNS, captive portal, etc.) — must NOT trigger a re-mint.
    def boom(*a, **kw):
        raise httpx.ConnectError("nope")

    monkeypatch.setattr(httpx, "get", boom)
    assert _ping_key("k", "http://x") is True


def test_ping_key_timeout_prefers_reuse(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*a, **kw):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(httpx, "get", boom)
    assert _ping_key("k", "http://x") is True


# ── plugin_sync._update_shell_rc ──────────────────────────────────────────


def test_shell_rc_updates_existing_export_preserves_trailing_newline(tmp_path) -> None:
    rc = tmp_path / ".zshrc"
    rc.write_text('export MEM0_API_KEY="old"\n', encoding="utf-8")
    changed = _update_shell_rc(rc, "newkey")
    assert changed is True
    assert rc.read_text(encoding="utf-8") == 'export MEM0_API_KEY="newkey"\n'


def test_shell_rc_does_not_create_new_export(tmp_path) -> None:
    rc = tmp_path / ".zshrc"
    rc.write_text("alias ll='ls -la'\n", encoding="utf-8")
    changed = _update_shell_rc(rc, "newkey")
    assert changed is False
    assert rc.read_text(encoding="utf-8") == "alias ll='ls -la'\n"


def test_shell_rc_preserves_surrounding_content(tmp_path) -> None:
    rc = tmp_path / ".zshrc"
    original = "# my zshrc\nalias ll='ls -la'\nexport MEM0_API_KEY='old'\nexport OTHER=keepme\n"
    rc.write_text(original, encoding="utf-8")
    _update_shell_rc(rc, "newkey")
    after = rc.read_text(encoding="utf-8")
    assert "alias ll='ls -la'\n" in after
    assert "export OTHER=keepme\n" in after
    assert "# my zshrc\n" in after
    assert 'export MEM0_API_KEY="newkey"\n' in after


def test_shell_rc_idempotent_when_already_matching(tmp_path) -> None:
    rc = tmp_path / ".zshrc"
    rc.write_text('export MEM0_API_KEY="same"\n', encoding="utf-8")
    assert _update_shell_rc(rc, "same") is False


def test_shell_rc_missing_file_is_noop(tmp_path) -> None:
    rc = tmp_path / ".zshrc"  # does not exist
    assert _update_shell_rc(rc, "x") is False


# ── plugin_sync._update_claude_settings ────────────────────────────────────


def test_claude_settings_does_not_create_env_block(tmp_path) -> None:
    import json

    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"otherKey": 1}), encoding="utf-8")
    changed = _update_claude_settings(settings, "newkey")
    assert changed is False
    # Original content unchanged.
    assert json.loads(settings.read_text(encoding="utf-8")) == {"otherKey": 1}


def test_claude_settings_does_not_create_mem0_entry_in_existing_env(tmp_path) -> None:
    import json

    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {"OTHER_KEY": "x"}}), encoding="utf-8")
    changed = _update_claude_settings(settings, "newkey")
    assert changed is False


def test_claude_settings_updates_existing_entry(tmp_path) -> None:
    import json

    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"env": {"MEM0_API_KEY": "old", "OTHER": "y"}}, indent=2),
        encoding="utf-8",
    )
    changed = _update_claude_settings(settings, "fresh")
    assert changed is True
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data["env"]["MEM0_API_KEY"] == "fresh"
    assert data["env"]["OTHER"] == "y"  # other keys preserved


def test_claude_settings_idempotent(tmp_path) -> None:
    import json

    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"env": {"MEM0_API_KEY": "same"}}), encoding="utf-8")
    assert _update_claude_settings(settings, "same") is False


def test_claude_settings_malformed_json_is_noop(tmp_path) -> None:
    settings = tmp_path / "settings.json"
    settings.write_text("{ this is not json", encoding="utf-8")
    assert _update_claude_settings(settings, "x") is False


# ── bootstrap rate-limit translation ──────────────────────────────────────


def test_bootstrap_403_permission_surfaces_ratelimit(monkeypatch, capsys) -> None:
    """DRF 403 'You do not have permission' must be translated to the daily limit message."""
    from mem0_cli.commands.agent_mode_cmd import bootstrap_via_backend
    from mem0_cli.config import Mem0Config

    fake_resp = MagicMock()
    fake_resp.status_code = 403
    fake_resp.text = '{"detail": "You do not have permission to perform this action."}'
    fake_resp.json = MagicMock(
        return_value={"detail": "You do not have permission to perform this action."}
    )

    class _Client:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **kw):
            return fake_resp

    monkeypatch.setattr(httpx, "Client", _Client)
    cfg = Mem0Config()
    cfg.platform.base_url = "https://api.mem0.ai"
    import typer

    with pytest.raises(typer.Exit):
        bootstrap_via_backend(cfg)

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "Daily Agent Mode signup limit reached" in combined
    assert "permission to perform this action" not in combined
