"""Tests for telemetry subprocess secret handling."""

from __future__ import annotations

import io
import json
import subprocess
import sys

from mem0_cli.config import Mem0Config, save_config
from mem0_cli.telemetry import capture_event
from mem0_cli.telemetry_sender import _load_context


class _CaptureStdin:
    def __init__(self):
        self.buffer = ""
        self.closed = False

    def write(self, value: str) -> None:
        self.buffer += value

    def close(self) -> None:
        self.closed = True


class _DummyProcess:
    def __init__(self):
        self.stdin = _CaptureStdin()


def test_capture_event_writes_context_to_stdin_not_argv(isolate_config, monkeypatch):
    config = Mem0Config()
    config.platform.api_key = "m0-test-secret"
    config.telemetry.anonymous_id = "cli-anon-test"
    save_config(config)

    captured: dict[str, object] = {}
    proc = _DummyProcess()

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return proc

    monkeypatch.setattr("mem0_cli.telemetry.subprocess.Popen", fake_popen)

    capture_event("unit_test_event", {"case": "stdin-secret"})

    argv = captured["args"]
    assert argv == [sys.executable, "-m", "mem0_cli.telemetry_sender"]
    assert all("m0-test-secret" not in arg for arg in argv)

    kwargs = captured["kwargs"]
    assert kwargs["stdin"] == subprocess.PIPE
    assert kwargs["text"] is True

    ctx = json.loads(proc.stdin.buffer)
    assert ctx["mem0_api_key"] == "m0-test-secret"
    assert ctx["payload"]["event"] == "unit_test_event"

    assert proc.stdin.closed


def test_load_context_reads_from_stdin(monkeypatch):
    monkeypatch.setattr("sys.argv", ["telemetry_sender"])
    monkeypatch.setattr("sys.stdin", io.StringIO('{"payload": {"event": "stdin"}}'))

    ctx = _load_context()

    assert ctx["payload"]["event"] == "stdin"


def test_load_context_falls_back_to_argv(monkeypatch):
    monkeypatch.setattr("sys.argv", ["telemetry_sender", '{"payload": {"event": "argv"}}'])
    monkeypatch.setattr("sys.stdin", io.StringIO(""))

    ctx = _load_context()

    assert ctx["payload"]["event"] == "argv"


def test_cache_email_round_trips_utf8_config(tmp_path):
    from mem0_cli.telemetry_sender import _cache_email

    cfg_path = tmp_path / "config.json"
    cfg_path.write_bytes(
        json.dumps(
            {
                "platform": {
                    "api_key": "k",
                    "user_email": "用户@example.com",
                    "display_name": "José 東京",
                }
            },
            ensure_ascii=False,
        ).encode("utf-8")
    )

    _cache_email(str(cfg_path), "new@example.com")

    data = json.loads(cfg_path.read_bytes().decode("utf-8"))
    assert data["platform"]["user_email"] == "new@example.com"
    # Fields the write does not touch must survive byte-identical: without
    # explicit UTF-8 I/O a non-UTF-8 locale silently corrupts them (#7227).
    assert data["platform"]["display_name"] == "José 東京"
