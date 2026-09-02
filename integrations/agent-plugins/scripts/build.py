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


def _build_cursor(staged: Path) -> None:
    host_root = HOSTS / "cursor"
    _bundle_python(staged, "cursor", "${CURSOR_PLUGIN_ROOT}")
    (staged / ".cursor-plugin").mkdir()
    (staged / "hooks").mkdir()
    (staged / "agents").mkdir()
    shutil.copy2(host_root / "plugin.json", staged / ".cursor-plugin" / "plugin.json")
    shutil.copy2(host_root / "hooks.json", staged / "hooks" / "hooks.json")
    shutil.copy2(host_root / "adapter.py", staged / "hooks" / "adapter.py")
    shutil.copy2(host_root / "sidekick.md", staged / "agents" / "sidekick.md")
    mcp = {
        "mcpServers": {
            "mem0": {
                "type": "stdio",
                "command": "python3",
                "args": ["${CURSOR_PLUGIN_ROOT}/core/mcp_server.py"],
                "env": {
                    "PLUGIN_OPTION_API_KEY": "${api_key}",
                    "PLUGIN_OPTION_USER_ID": "${user_id}",
                    "PLUGIN_OPTION_TOP_K": "${top_k}",
                    "PLUGIN_OPTION_MAX_CONTEXT_CHARS": "${max_context_chars}",
                    "PLUGIN_OPTION_SEARCH_SCOPE": "${search_scope}",
                },
            }
        }
    }
    _write_json(staged / "mcp.json", mcp)


def _build_codex(staged: Path) -> None:
    host_root = HOSTS / "codex"
    _bundle_python(staged, "codex", "${PLUGIN_ROOT}")
    (staged / ".codex-plugin").mkdir()
    (staged / "hooks").mkdir()
    shutil.copy2(host_root / "plugin.json", staged / ".codex-plugin" / "plugin.json")
    shutil.copy2(host_root / "hooks.json", staged / "hooks" / "hooks.json")
    shutil.copy2(host_root / "adapter.py", staged / "hooks" / "adapter.py")
    shutil.copy2(TEMPLATES / "mcp.json.tmpl", staged / "mcp.json")


def _build_claude(staged: Path) -> None:
    host_root = HOSTS / "claude-code"
    _bundle_python(staged, "claude-code", "${CLAUDE_PLUGIN_ROOT}")
    for directory in (".claude-plugin", "hooks", "agents", "adapters/claude"):
        (staged / directory).mkdir(parents=True)
    shutil.copy2(host_root / "plugin.json", staged / ".claude-plugin" / "plugin.json")
    shutil.copy2(host_root / "mcp.json", staged / ".mcp.json")
    shutil.copy2(host_root / "hooks.json", staged / "hooks" / "hooks.json")
    shutil.copy2(PLUGIN_ROOT / "shared" / "sidekick" / "prompt.md", staged / "agents" / "sidekick.md")
    shutil.copy2(host_root / "adapter.py", staged / "adapters" / "claude" / "hook.py")
    shutil.copy2(host_root / "transcript.py", staged / "adapters" / "claude" / "transcript.py")


def _build_kimi(staged: Path) -> None:
    host_root = HOSTS / "kimi"
    _bundle_python(staged, "kimi", "${KIMI_PLUGIN_ROOT}")
    (staged / "hooks").mkdir()
    (staged / "agents").mkdir()
    shutil.copy2(host_root / "plugin.json", staged / "kimi.plugin.json")
    shutil.copy2(host_root / "adapter.py", staged / "hooks" / "adapter.py")
    shutil.copy2(host_root / "sidekick.md", staged / "agents" / "sidekick.md")


def _build_antigravity(staged: Path) -> None:
    host_root = HOSTS / "antigravity"
    _bundle_python(staged, "antigravity", "${ANTIGRAVITY_PLUGIN_ROOT}")
    (staged / "hooks").mkdir()
    (staged / "agents" / "sidekick").mkdir(parents=True)
    for name in ("plugin.json", "hooks.json", "mcp_config.json"):
        shutil.copy2(host_root / name, staged / name)
    shutil.copy2(host_root / "adapter.py", staged / "hooks" / "adapter.py")
    shutil.copy2(host_root / "sidekick.md", staged / "agents" / "sidekick" / "agent.md")


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
        elif host == "cursor":
            _build_cursor(staged)
        elif host == "codex":
            _build_codex(staged)
        elif host == "claude-code":
            _build_claude(staged)
        elif host == "kimi":
            _build_kimi(staged)
        elif host == "antigravity":
            _build_antigravity(staged)
        else:
            raise ValueError(f"native build is not implemented for {host}")
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
