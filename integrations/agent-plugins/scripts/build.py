#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from collections.abc import Mapping
from pathlib import Path

try:
    from .validate import validate_bundle
except ImportError:
    from validate import validate_bundle

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PLUGIN_ROOT.parents[1]
PROTECTED_OUTPUTS = {REPOSITORY_ROOT, REPOSITORY_ROOT / "integrations", PLUGIN_ROOT}
HOSTS = PLUGIN_ROOT / "hosts"
SHARED_SKILLS = PLUGIN_ROOT / "shared" / "skills"
TEMPLATES = PLUGIN_ROOT / "templates"
TEMPLATE_TOKEN = re.compile(r"{{([A-Z_]+)}}")
TEMPLATE_TOKENS = {"PLUGIN_ROOT", "PLUGIN_DATA", "COMMAND_PREFIX", "HARNESS_NAME"}


def render_template(source: str, values: Mapping[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if token not in TEMPLATE_TOKENS or token not in values:
            raise ValueError(f"unknown or unresolved template token: {token}")
        return values[token]

    rendered = TEMPLATE_TOKEN.sub(replace, source)
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("unresolved template token")
    return rendered


def replace_output(staged: Path, output: Path) -> Path:
    """Replace one explicit build output without touching its siblings."""
    if not staged.is_dir():
        raise ValueError(f"staged directory does not exist: {staged}")

    resolved_output = output.resolve()
    if resolved_output in {path.resolve() for path in PROTECTED_OUTPUTS}:
        raise ValueError(f"refusing protected output path: {output}")
    if output.exists() and not output.is_dir():
        raise ValueError(f"output path is not a directory: {output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        shutil.copytree(staged, temporary, dirs_exist_ok=True)
        if output.exists():
            shutil.rmtree(output)
        temporary.replace(output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return output


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _bundle_python(staged: Path, host: str, plugin_root: str, *, portable: bool = False) -> None:
    core = staged / "core"
    core.mkdir()
    for source in sorted((PLUGIN_ROOT / "core" / "python").glob("*.py")):
        shutil.copy2(source, core / source.name)

    values = {
        "PLUGIN_ROOT": plugin_root,
        "PLUGIN_DATA": "${PLUGIN_DATA}",
        "COMMAND_PREFIX": "mem0",
        "HARNESS_NAME": host.replace("-", " ").title(),
    }
    for source in sorted(SHARED_SKILLS.glob("*/SKILL.md.tmpl")):
        target = staged / "skills" / source.parent.name / "SKILL.md"
        target.parent.mkdir(parents=True)
        rendered = render_template(source.read_text(encoding="utf-8"), values)
        if portable:
            rendered = "\n".join(
                line
                for line in rendered.splitlines()
                if not line.startswith(("argument-hint:", "disable-model-invocation:"))
            ) + "\n"
        target.write_text(rendered, encoding="utf-8")


def _build_portable(host: str, staged: Path, descriptor: dict) -> None:
    manifest = json.loads((TEMPLATES / "plugin.json.tmpl").read_text(encoding="utf-8"))
    manifest["name"] = descriptor["id"]
    manifest["version"] = descriptor["version"]
    manifest["homepage"] = descriptor["homepage"]
    _write_json(staged / "plugin.json", manifest)

    mcp = json.loads((TEMPLATES / "mcp.json.tmpl").read_text(encoding="utf-8"))
    _write_json(staged / "mcp.json", mcp)
    _bundle_python(staged, host, "${PLUGIN_ROOT}", portable=True)


def _copy_declared_files(staged: Path, source_root: Path, files: object) -> None:
    if not isinstance(files, dict):
        raise ValueError("native files must be an object")
    source_root = source_root.resolve()
    staged_root = staged.resolve()
    for source_name, target_name in files.items():
        if not isinstance(source_name, str) or not isinstance(target_name, str):
            raise ValueError("native file paths must be strings")
        source = (source_root / source_name).resolve()
        target = (staged / target_name).resolve()
        if not source.is_relative_to(source_root) or not target.is_relative_to(staged_root):
            raise ValueError("native file paths must stay inside their roots")
        if not source.is_file():
            raise ValueError(f"native source file does not exist: {source_name}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _build_native(host: str, staged: Path, descriptor: dict) -> None:
    native = descriptor.get("native")
    if not isinstance(native, dict) or not isinstance(native.get("pluginRoot"), str):
        raise ValueError(f"native build is not declared for {host}")
    _bundle_python(staged, host, native["pluginRoot"])
    _copy_declared_files(staged, HOSTS / host, native.get("files", {}))
    _copy_declared_files(staged, PLUGIN_ROOT, native.get("sharedFiles", {}))


def build(host: str, kind: str, output: Path) -> Path:
    descriptor_path = HOSTS / host / "host.json"
    if not descriptor_path.is_file():
        raise ValueError(f"unknown host: {host}")
    if kind not in {"portable", "native"}:
        raise ValueError(f"unknown bundle kind: {kind}")
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix=f"mem0-{host}-{kind}-") as temporary:
        staged = Path(temporary) / "bundle"
        staged.mkdir()
        if kind == "portable":
            _build_portable(host, staged, descriptor)
        else:
            _build_native(host, staged, descriptor)
        errors = validate_bundle(staged, kind)
        if errors:
            raise ValueError("invalid bundle:\n" + "\n".join(errors))
        return replace_output(staged, output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a self-contained Mem0 agent plugin")
    parser.add_argument("host")
    parser.add_argument("--kind", choices=("portable", "native"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(build(args.host, args.kind, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
