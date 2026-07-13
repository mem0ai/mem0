"""Cost-admission contracts for hosted Mem0 traffic."""

from __future__ import annotations

import concurrent.futures
import importlib
import os
import subprocess
import sys
import urllib.request
import uuid
import json
from unittest.mock import patch

import pytest


def _reset_budget_env(monkeypatch):
    for name in (
        "MEM0_BUDGET_SESSION_REQUESTS",
        "MEM0_BUDGET_DAILY_REQUESTS",
        "MEM0_BUDGET_SESSION_AUTO_REQUESTS",
        "MEM0_BUDGET_DAILY_AUTO_REQUESTS",
        "MEM0_BUDGET_SESSION_WEIGHT",
        "MEM0_BUDGET_DAILY_WEIGHT",
    ):
        monkeypatch.delenv(name, raising=False)


def test_default_auto_search_is_off_in_python_resolution(monkeypatch, tmp_path):
    monkeypatch.setattr("load_settings.SETTINGS_PATH", tmp_path / "missing.json")
    import load_settings
    import _identity

    importlib.reload(load_settings)
    importlib.reload(_identity)
    monkeypatch.setattr(load_settings, "SETTINGS_PATH", tmp_path / "missing.json")
    assert load_settings.load_settings()["auto_search"] is False
    assert _identity.resolve_config()["auto_search"] is False


def test_atomic_session_limit_across_processes(monkeypatch, tmp_path):
    _reset_budget_env(monkeypatch)
    monkeypatch.setenv("MEM0_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("MEM0_BUDGET_SESSION_REQUESTS", "1")
    env = os.environ.copy()
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "admission_cli.py")

    def charge_once():
        return subprocess.run(
            [
                sys.executable,
                script,
                "charge",
                "--operation",
                "search",
                "--ingress",
                "test",
                "--session-id",
                "one-session",
                "--charge-id",
                str(uuid.uuid4()),
            ],
            env=env,
            capture_output=True,
            text=True,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: charge_once(), range(8)))

    assert sum(result.returncode == 0 for result in results) == 1
    assert sum(result.returncode == 2 for result in results) == 7


def test_duplicate_charge_id_is_idempotent(monkeypatch, tmp_path):
    _reset_budget_env(monkeypatch)
    monkeypatch.setenv("MEM0_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("MEM0_BUDGET_SESSION_REQUESTS", "1")
    from admission import admit

    first = admit("search", "test", False, "session", charge_id="same")
    second = admit("search", "test", False, "session", charge_id="same")

    assert first.admitted is True
    assert second.admitted is True
    assert second.idempotent is True


def test_automatic_ceiling_preserves_explicit_reserve(monkeypatch, tmp_path):
    _reset_budget_env(monkeypatch)
    monkeypatch.setenv("MEM0_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("MEM0_BUDGET_SESSION_REQUESTS", "2")
    monkeypatch.setenv("MEM0_BUDGET_SESSION_AUTO_REQUESTS", "1")
    from admission import admit

    assert admit("search", "hook", True, "session").admitted
    denied = admit("search", "hook", True, "session")
    assert denied.admitted is False
    assert denied.reason == "remote-automatic-budget-exhausted"
    assert admit("search", "explicit", False, "session").admitted


def test_daily_request_ceiling_spans_sessions(monkeypatch, tmp_path):
    _reset_budget_env(monkeypatch)
    monkeypatch.setenv("MEM0_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("MEM0_BUDGET_DAILY_REQUESTS", "1")
    from admission import admit

    assert admit("search", "test", False, "session-a").admitted
    denied = admit("search", "test", False, "session-b")
    assert denied.admitted is False
    assert denied.reason == "remote-daily-budget-exhausted"


def test_daily_weight_ceiling_spans_sessions(monkeypatch, tmp_path):
    _reset_budget_env(monkeypatch)
    monkeypatch.setenv("MEM0_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("MEM0_BUDGET_DAILY_WEIGHT", "3")
    from admission import admit

    assert admit("add", "test", False, "session-a", payload_bytes=1).admitted
    denied = admit("search", "test", False, "session-b")
    assert denied.admitted is False
    assert denied.reason == "remote-daily-weight-exhausted"


@pytest.mark.parametrize("value", ["-1", "garbage", "1.5"])
def test_invalid_budget_configuration_fails_closed(monkeypatch, tmp_path, value):
    _reset_budget_env(monkeypatch)
    monkeypatch.setenv("MEM0_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("MEM0_BUDGET_DAILY_REQUESTS", value)
    from admission import admit

    result = admit("search", "test", False, "session")
    assert result.admitted is False
    assert result.reason == "remote-invalid-budget-config"


def test_unwritable_accounting_fails_closed(monkeypatch, tmp_path):
    _reset_budget_env(monkeypatch)
    state_file = tmp_path / "not-a-directory"
    state_file.write_text("x")
    monkeypatch.setenv("MEM0_STATE_DIR", str(state_file))
    from admission import admit

    result = admit("search", "test", False, "session")
    assert result.admitted is False
    assert result.reason == "remote-accounting-unavailable"


def test_weight_ceiling_is_monotonic(monkeypatch, tmp_path):
    _reset_budget_env(monkeypatch)
    monkeypatch.setenv("MEM0_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("MEM0_BUDGET_SESSION_WEIGHT", "3")
    from admission import admit

    assert admit("add", "test", False, "session", payload_bytes=1).admitted
    denied = admit("search", "test", False, "session")
    assert denied.admitted is False
    assert denied.reason == "remote-session-weight-exhausted"


def test_automatic_search_coalesces_before_charge(monkeypatch, tmp_path):
    _reset_budget_env(monkeypatch)
    monkeypatch.setenv("MEM0_STATE_DIR", str(tmp_path))
    from admission import admit

    first = admit("search", "read", True, "session", coalesce_key="same-scope-query")
    duplicate = admit("search", "read", True, "session", coalesce_key="same-scope-query")
    assert first.admitted is True
    assert duplicate.admitted is False
    assert duplicate.reason == "remote-coalesced"


def test_denied_hosted_request_never_reaches_network(monkeypatch, tmp_path):
    _reset_budget_env(monkeypatch)
    monkeypatch.setenv("MEM0_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("MEM0_BUDGET_SESSION_REQUESTS", "0")
    from hosted_request import HostedRequestDenied, open_hosted_request

    request = urllib.request.Request("https://api.mem0.ai/v3/memories/search/")
    with patch("urllib.request.urlopen") as network:
        with pytest.raises(HostedRequestDenied):
            open_hosted_request(
                request,
                timeout=1,
                ingress="test",
                automatic=False,
                operation="search",
            )
    network.assert_not_called()


def test_file_read_hook_default_off_never_enters_admission(tmp_path):
    target = tmp_path / "large.py"
    target.write_text("x" * 2000)
    state = tmp_path / "state"
    hook = os.path.join(os.path.dirname(__file__), "..", "scripts", "on_file_read.sh")
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path),
            "MEM0_API_KEY": "sentinel-no-network",
            "MEM0_STATE_DIR": str(state),
            "MEM0_BUDGET_SESSION_REQUESTS": "0",
        }
    )
    result = subprocess.run(
        [hook],
        input=json.dumps({"tool_input": {"file_path": str(target)}, "cwd": str(tmp_path)}),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert not (state / "admission.sqlite3").exists()


def test_file_read_hook_explicit_opt_in_reaches_admission_not_network(tmp_path):
    target = tmp_path / "large.py"
    target.write_text("x" * 2000)
    settings = tmp_path / ".mem0" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({"auto_search": True}))
    state = tmp_path / "state"
    hook = os.path.join(os.path.dirname(__file__), "..", "scripts", "on_file_read.sh")
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path),
            "MEM0_API_KEY": "sentinel-no-network",
            "MEM0_STATE_DIR": str(state),
            "MEM0_BUDGET_SESSION_REQUESTS": "0",
        }
    )
    result = subprocess.run(
        [hook],
        input=json.dumps({"tool_input": {"file_path": str(target)}, "cwd": str(tmp_path)}),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (state / "admission.sqlite3").exists()


@pytest.mark.parametrize("helper", ["count_memories.py", "session_timeline.py"])
def test_session_start_helpers_default_off_never_enter_admission(tmp_path, helper):
    state = tmp_path / "state"
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", helper)
    env = os.environ.copy()
    env.update(
        {
            "HOME": str(tmp_path),
            "MEM0_API_KEY": "sentinel-no-network",
            "MEM0_STATE_DIR": str(state),
            "MEM0_BUDGET_SESSION_REQUESTS": "0",
        }
    )
    result = subprocess.run(
        [sys.executable, script], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0
    assert not (state / "admission.sqlite3").exists()
