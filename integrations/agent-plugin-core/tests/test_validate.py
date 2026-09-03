from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATE = ROOT / "build" / "validate.py"
PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"


def run_validator(bundle: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATE), str(bundle), "--kind", "portable"],
        capture_output=True,
        check=False,
        text=True,
    )


def write_manifest(bundle: Path, schema: str = PLUGIN_SCHEMA) -> None:
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "plugin.json").write_text(
        json.dumps({"$schema": schema, "name": "mem0"}),
        encoding="utf-8",
    )


def test_rejects_wrong_agent_plugin_schema(tmp_path: Path) -> None:
    bundle = tmp_path / "plugin"
    write_manifest(bundle, "https://agent-plugins.org/v1.0.0/plugin.schema.json")

    result = run_validator(bundle)

    assert result.returncode == 1
    assert result.stderr == (
        "plugin.json.$schema: "
        "'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json' was expected\n"
    )


def test_rejects_symlink_outside_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "plugin"
    write_manifest(bundle)
    outside = tmp_path / "outside"
    outside.mkdir()
    (bundle / "skills").symlink_to(outside, target_is_directory=True)

    result = run_validator(bundle)

    assert result.returncode == 1
    assert result.stderr == "skills: symlinks are not allowed in release bundles\n"


def test_accepts_minimal_portable_bundle(tmp_path: Path) -> None:
    bundle = tmp_path / "plugin"
    write_manifest(bundle)

    result = run_validator(bundle)

    assert result.returncode == 0
    assert result.stdout == f"Validated portable bundle: {bundle}\n"
    assert result.stderr == ""


def test_rejects_nonconformant_agent_skill(tmp_path: Path) -> None:
    bundle = tmp_path / "plugin"
    write_manifest(bundle)
    skill = bundle / "skills" / "Bad_Name"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: Bad_Name\ndescription: invalid\nunknown: true\n---\n",
        encoding="utf-8",
    )

    result = run_validator(bundle)

    assert result.returncode == 1
    assert "skills/Bad_Name" in result.stderr
