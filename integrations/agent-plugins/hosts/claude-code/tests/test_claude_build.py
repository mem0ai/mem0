from __future__ import annotations

import sys
from pathlib import Path

HOST = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = HOST.parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.build import SHARED_SKILLS, build, render_template  # noqa: E402


def test_native_claude_bundle_preserves_working_contract(tmp_path: Path) -> None:
    root = build("claude-code", "native", tmp_path / "claude-code")

    assert (root / ".claude-plugin" / "plugin.json").read_bytes() == (HOST / "plugin.json").read_bytes()
    assert (root / ".mcp.json").read_bytes() == (HOST / "mcp.json").read_bytes()
    assert (root / "hooks" / "hooks.json").read_bytes() == (HOST / "hooks.json").read_bytes()
    assert (root / "agents" / "sidekick.md").read_bytes() == (
        PLUGIN_ROOT / "shared" / "sidekick" / "prompt.md"
    ).read_bytes()
    values = {
        "PLUGIN_ROOT": "${CLAUDE_PLUGIN_ROOT}",
        "PLUGIN_DATA": "${PLUGIN_DATA}",
        "COMMAND_PREFIX": "mem0",
        "HARNESS_NAME": "Claude Code",
    }
    for skill in SHARED_SKILLS.glob("*/SKILL.md.tmpl"):
        rendered = render_template(skill.read_text(encoding="utf-8"), values)
        assert (root / "skills" / skill.parent.name / "SKILL.md").read_text(encoding="utf-8") == rendered
    assert (root / "adapters" / "claude" / "hook.py").is_file()
    assert (root / "core" / "mcp_server.py").is_file()
    assert not any(path.is_symlink() for path in root.rglob("*"))
