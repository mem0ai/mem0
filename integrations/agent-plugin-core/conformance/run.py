#!/usr/bin/env python3
"""Run every coding-agent plugin check and emit one conformance report."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


CORE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = CORE_ROOT.parents[1]
PYTHON_HOSTS = ("claude-code", "cursor", "codex", "kimi", "antigravity")
GROUPS = (
    "python-bundles",
    "python-tests",
    "typescript-core",
    "openclaw",
    "opencode",
    "pi-agent",
    "deepseek",
)
LIVE_GROUP = "live-platform"

sys.path.insert(0, str(CORE_ROOT))
sys.path.insert(0, str(CORE_ROOT / "python"))
from memory_core import redact  # noqa: E402
from build.build import build  # noqa: E402


def _package_directories() -> dict[str, Path]:
    return {
        "typescript-core": CORE_ROOT / "typescript",
        "openclaw": REPOSITORY_ROOT / "integrations" / "openclaw",
        "opencode": REPOSITORY_ROOT / "integrations" / "opencode-plugin",
        "pi-agent": REPOSITORY_ROOT / "integrations" / "pi-agent-plugin",
        "deepseek": REPOSITORY_ROOT / "integrations" / "deepseek-plugin",
    }


def _runtime_commands() -> dict[str, list[list[str]]]:
    return {
        "python-tests": [
            [
                sys.executable,
                "-m",
                "pytest",
                "integrations/agent-plugin-core/tests",
                "integrations/claude-code-plugin/tests",
                "integrations/cursor-plugin/tests",
                "integrations/codex-plugin/tests",
                "integrations/kimi-plugin/tests",
                "integrations/antigravity-plugin/tests",
                "-q",
                "--ignore=integrations/agent-plugin-core/tests/test_conformance.py",
                "--ignore=integrations/claude-code-plugin/tests/integration",
            ]
        ],
        "typescript-core": [["pnpm", "test"], ["pnpm", "typecheck"]],
        "openclaw": [
            ["pnpm", "test"],
            ["pnpm", "exec", "tsc", "--noEmit"],
            ["pnpm", "build"],
        ],
        "opencode": [
            ["bun", "test"],
            ["bun", "run", "type-check"],
            ["bun", "run", "build"],
        ],
        "pi-agent": [
            ["pnpm", "test"],
            ["pnpm", "typecheck"],
            ["pnpm", "build"],
        ],
        "deepseek": [
            ["pnpm", "test"],
            ["pnpm", "typecheck"],
            ["pnpm", "build"],
        ],
        LIVE_GROUP: [
            [
                sys.executable,
                "-m",
                "pytest",
                "integrations/claude-code-plugin/tests/integration",
                "-q",
            ]
        ],
    }


def _planned_checks(groups: set[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if "python-bundles" in groups:
        checks.append(
            {
                "name": "python-bundles",
                "group": "python-bundles",
                "status": "planned",
                "hosts": list(PYTHON_HOSTS),
                "kinds": {"native": list(PYTHON_HOSTS), "portable": ["mem0-agent-plugin"]},
            }
        )
    for group, commands in _runtime_commands().items():
        if group not in groups:
            continue
        for index, command in enumerate(commands, start=1):
            checks.append(
                {
                    "name": f"{group}-{index}",
                    "group": group,
                    "status": "planned",
                    "command": command,
                }
            )
    return checks


def _command_check(
    name: str,
    group: str,
    command: list[str],
    *,
    cwd: Path,
) -> dict[str, Any]:
    started = time.monotonic()
    environment = dict(os.environ)
    safe_command = [redact(part) for part in command]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        output = redact((result.stdout + result.stderr).strip())
        return {
            "name": name,
            "group": group,
            "status": "passed" if result.returncode == 0 else "failed",
            "duration_seconds": round(time.monotonic() - started, 3),
            "command": safe_command,
            "exit_code": result.returncode,
            **({"output": output[-8_000:]} if output else {}),
        }
    except OSError as exc:
        return {
            "name": name,
            "group": group,
            "status": "failed",
            "duration_seconds": round(time.monotonic() - started, 3),
            "command": safe_command,
            "exit_code": None,
            "output": redact(str(exc)),
        }


def _bundle_checks(artifacts_dir: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    plugins = [(host, "native") for host in PYTHON_HOSTS] + [("mem0-agent-plugin", "portable")]
    for host, kind in plugins:
        started = time.monotonic()
        try:
            output = artifacts_dir / host
            build(host, kind, output)
            status, error = "passed", ""
        except Exception as exc:
            status, error = "failed", f"{type(exc).__name__}: {exc}"
        checks.append(
            {
                "name": f"{host}-{kind}",
                "group": "python-bundles",
                "host": host,
                "kind": kind,
                "status": status,
                "duration_seconds": round(time.monotonic() - started, 3),
                **({"output": error} if error else {}),
            }
        )
    return checks


def _install_checks(groups: set[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for group, package in _package_directories().items():
        if group not in groups:
            continue
        command = (
            ["bun", "install", "--frozen-lockfile"]
            if group == "opencode"
            else ["pnpm", "install", "--frozen-lockfile"]
        )
        checks.append(_command_check(f"{group}-install", group, command, cwd=package))
    return checks


def _runtime_checks(groups: set[str]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    directories = {
        **_package_directories(),
        "python-tests": REPOSITORY_ROOT,
        LIVE_GROUP: REPOSITORY_ROOT,
    }
    for group, commands in _runtime_commands().items():
        if group not in groups:
            continue
        for index, command in enumerate(commands, start=1):
            checks.append(
                _command_check(
                    f"{group}-{index}",
                    group,
                    command,
                    cwd=directories[group],
                )
            )
    return checks


def _print_report(report: dict[str, Any]) -> None:
    for check in report["checks"]:
        marker = {"passed": "PASS", "failed": "FAIL", "planned": "PLAN"}[check["status"]]
        duration = f" ({check['duration_seconds']:.3f}s)" if "duration_seconds" in check else ""
        print(f"{marker:4} {check['name']}{duration}")
        if check["status"] == "failed" and check.get("output"):
            print(check["output"])
    print(f"\nConformance: {report['status']} ({len(report['checks'])} checks)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", action="append", choices=("all", *GROUPS, LIVE_GROUP), default=[])
    parser.add_argument("--list", action="store_true", help="Print the checks without running them")
    parser.add_argument("--install", action="store_true", help="Install TypeScript dependencies first")
    parser.add_argument("--live", action="store_true", help="Run the opt-in tests against Mem0 Platform")
    parser.add_argument("--artifacts-dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    selected = set(GROUPS if not args.group or "all" in args.group else args.group)
    if args.live:
        selected.add(LIVE_GROUP)
    if args.list:
        report = {"status": "planned", "checks": _planned_checks(selected)}
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        _print_report(report)
        return 0
    if LIVE_GROUP in selected and not os.environ.get("MEM0_API_KEY"):
        parser.error("MEM0_API_KEY is required for --live")

    temporary = None
    if args.artifacts_dir:
        artifacts_dir = args.artifacts_dir.resolve()
        artifacts_dir.mkdir(parents=True, exist_ok=True)
    else:
        temporary = tempfile.TemporaryDirectory(prefix="mem0-plugin-conformance-")
        artifacts_dir = Path(temporary.name)

    checks: list[dict[str, Any]] = []
    try:
        if args.install:
            checks.extend(_install_checks(selected))
        if "python-bundles" in selected:
            checks.extend(_bundle_checks(artifacts_dir))
        checks.extend(_runtime_checks(selected))
        report = {
            "status": "passed" if all(check["status"] == "passed" for check in checks) else "failed",
            "checks": checks,
        }
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        _print_report(report)
        return 0 if report["status"] == "passed" else 1
    finally:
        if temporary is not None:
            temporary.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
