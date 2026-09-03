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

CORE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = CORE_ROOT.parents[1]
INTEGRATIONS_ROOT = REPOSITORY_ROOT / "integrations"
SHARED_SKILLS = CORE_ROOT / "skills"
PORTABLE_PLUGIN = "mem0-agent-plugin"
NATIVE_PLUGINS = {
    "claude-code": INTEGRATIONS_ROOT / "claude-code-plugin",
    "cursor": INTEGRATIONS_ROOT / "cursor-plugin",
    "codex": INTEGRATIONS_ROOT / "codex-plugin",
    "kimi": INTEGRATIONS_ROOT / "kimi-plugin",
    "antigravity": INTEGRATIONS_ROOT / "antigravity-plugin",
}
PROTECTED_OUTPUTS = {
    REPOSITORY_ROOT,
    INTEGRATIONS_ROOT,
    CORE_ROOT,
    INTEGRATIONS_ROOT / PORTABLE_PLUGIN,
    *NATIVE_PLUGINS.values(),
}
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


def _bundle_python(staged: Path, host: str, plugin_root: str, *, portable: bool = False) -> None:
    core = staged / "core"
    core.mkdir()
    for source in sorted((CORE_ROOT / "python").glob("*.py")):
        if portable and source.name in {"flush_worker.py", "hook_runner.py"}:
            continue
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


def _build_portable(staged: Path) -> None:
    source = INTEGRATIONS_ROOT / PORTABLE_PLUGIN
    _copy_declared_files(staged, source, {"plugin.json": "plugin.json", "mcp.json": "mcp.json"})
    _bundle_python(staged, "coding-agent", "${PLUGIN_ROOT}", portable=True)


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


def _build_native(host: str, source_root: Path, staged: Path, descriptor: dict) -> None:
    native = descriptor.get("native")
    if not isinstance(native, dict) or not isinstance(native.get("pluginRoot"), str):
        raise ValueError(f"native build is not declared for {host}")
    _bundle_python(staged, host, native["pluginRoot"])
    _copy_declared_files(staged, source_root, native.get("files", {}))


def build(host: str, kind: str, output: Path) -> Path:
    if kind not in {"portable", "native"}:
        raise ValueError(f"unknown bundle kind: {kind}")
    if kind == "portable":
        if host != PORTABLE_PLUGIN:
            raise ValueError(f"the portable bundle is {PORTABLE_PLUGIN}")
        source_root = INTEGRATIONS_ROOT / PORTABLE_PLUGIN
        descriptor = None
    else:
        source_root = NATIVE_PLUGINS.get(host)
        if source_root is None:
            raise ValueError(f"unknown host: {host}")
        descriptor_path = source_root / "plugin-build.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix=f"mem0-{host}-{kind}-") as temporary:
        staged = Path(temporary) / "bundle"
        staged.mkdir()
        if kind == "portable":
            _build_portable(staged)
        else:
            assert descriptor is not None
            _build_native(host, source_root, staged, descriptor)
        errors = validate_bundle(staged, kind)
        if errors:
            raise ValueError("invalid bundle:\n" + "\n".join(errors))
        return replace_output(staged, output)


def installable_root(host: str, kind: str) -> Path:
    if kind == "portable" and host == PORTABLE_PLUGIN:
        return INTEGRATIONS_ROOT / PORTABLE_PLUGIN
    if kind == "native" and host in NATIVE_PLUGINS:
        return NATIVE_PLUGINS[host]
    raise ValueError(f"unknown {kind} plugin: {host}")


def bundle_drift(host: str, kind: str) -> list[str]:
    target = installable_root(host, kind)
    with tempfile.TemporaryDirectory(prefix=f"mem0-check-{host}-") as temporary:
        generated = build(host, kind, Path(temporary) / "bundle")
        errors: list[str] = []
        for directory in ("core", "skills"):
            expected = {
                path.relative_to(generated)
                for path in (generated / directory).rglob("*")
                if path.is_file()
            }
            actual = {
                path.relative_to(target)
                for path in (target / directory).rglob("*")
                if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
            }
            errors.extend(f"missing generated file: {path}" for path in sorted(expected - actual))
            errors.extend(f"stale generated file: {path}" for path in sorted(actual - expected))
        for source in sorted(path for path in generated.rglob("*") if path.is_file()):
            relative = source.relative_to(generated)
            installed = target / relative
            if not installed.is_file() or source.read_bytes() != installed.read_bytes():
                errors.append(f"generated file differs: {relative}")
        return errors


def sync_generated(host: str, kind: str) -> Path:
    target = installable_root(host, kind)
    with tempfile.TemporaryDirectory(prefix=f"mem0-sync-{host}-") as temporary:
        generated = build(host, kind, Path(temporary) / "bundle")
        for directory in ("core", "skills"):
            replace_output(generated / directory, target / directory)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a self-contained Mem0 agent plugin")
    parser.add_argument("host")
    parser.add_argument("--kind", choices=("portable", "native"), required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--output", type=Path)
    action.add_argument("--check", action="store_true")
    action.add_argument("--sync", action="store_true")
    args = parser.parse_args()
    if args.check:
        errors = bundle_drift(args.host, args.kind)
        if errors:
            print("\n".join(errors))
            return 1
        print(f"Current {args.kind} bundle: {installable_root(args.host, args.kind)}")
    elif args.sync:
        print(sync_generated(args.host, args.kind))
    else:
        assert args.output is not None
        print(build(args.host, args.kind, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
