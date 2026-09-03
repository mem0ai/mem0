from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from conformance.run import _command_check  # noqa: E402


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNNER = PLUGIN_ROOT / "conformance" / "run.py"
PYTHON_HOSTS = {"claude-code", "cursor", "codex", "kimi", "antigravity"}


def test_python_bundle_conformance_builds_every_host(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    artifacts = tmp_path / "artifacts"

    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--group",
            "python-bundles",
            "--artifacts-dir",
            str(artifacts),
            "--report",
            str(report),
        ],
        cwd=PLUGIN_ROOT.parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
    assert {
        entry["host"]
        for entry in payload["checks"]
        if entry["kind"] == "native"
    } == PYTHON_HOSTS
    assert {
        entry["host"]
        for entry in payload["checks"]
        if entry["kind"] == "portable"
    } == {"mem0-agent-plugin"}
    for host in PYTHON_HOSTS:
        assert (artifacts / host).is_dir()
    assert (artifacts / "mem0-agent-plugin").is_dir()


def test_conformance_plan_covers_every_runtime(tmp_path: Path) -> None:
    report = tmp_path / "plan.json"

    result = subprocess.run(
        [sys.executable, str(RUNNER), "--list", "--report", str(report)],
        cwd=PLUGIN_ROOT.parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert {entry["group"] for entry in payload["checks"]} == {
        "python-bundles",
        "python-tests",
        "typescript-core",
        "openclaw",
        "opencode",
        "pi-agent",
        "deepseek",
    }
    assert all(entry["status"] == "planned" for entry in payload["checks"])


def test_live_conformance_requires_an_explicit_mem0_key(tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment.pop("MEM0_API_KEY", None)

    result = subprocess.run(
        [sys.executable, str(RUNNER), "--live", "--report", str(tmp_path / "report.json")],
        cwd=PLUGIN_ROOT.parents[1],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "MEM0_API_KEY is required for --live" in result.stderr


def test_live_conformance_reports_platform_failure_without_crashing(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    environment = {
        **os.environ,
        "MEM0_API_KEY": "m0-intentionally-invalid",
        "MEM0_API_URL": "http://127.0.0.1:1",
    }

    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--group",
            "live-platform",
            "--live",
            "--report",
            str(report),
        ],
        cwd=PLUGIN_ROOT.parents[1],
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["status"] == "failed"
    assert payload["checks"][0]["group"] == "live-platform"


def test_runtime_checks_preserve_the_callers_telemetry_setting(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MEM0_TELEMETRY", raising=False)

    result = _command_check(
        "environment",
        "test",
        [sys.executable, "-c", "import os; print(os.environ.get('MEM0_TELEMETRY', 'unset'))"],
        cwd=tmp_path,
    )

    assert result["status"] == "passed"
    assert result["output"] == "unset"


def test_conformance_report_redacts_command_output(tmp_path: Path) -> None:
    secret = "sk-eval-12345678901234567890"

    result = _command_check(
        "redaction",
        "test",
        [sys.executable, "-c", f"print('failure: {secret}')"],
        cwd=tmp_path,
    )

    assert secret not in json.dumps(result)
    assert "[REDACTED]" in result["output"]
