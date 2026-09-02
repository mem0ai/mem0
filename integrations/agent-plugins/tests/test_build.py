from __future__ import annotations

import sys
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build import build, render_template, replace_output  # noqa: E402
from scripts.validate import validate_bundle  # noqa: E402


def test_render_rejects_unknown_or_unresolved_tokens() -> None:
    with pytest.raises(ValueError, match="UNKNOWN"):
        render_template("run {{UNKNOWN}}", {})


def test_build_replaces_only_the_requested_output(tmp_path: Path) -> None:
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "plugin.json").write_text("{}", encoding="utf-8")
    output = tmp_path / "output"
    output.mkdir()
    (output / "stale.py").write_text("stale", encoding="utf-8")
    sibling = tmp_path / "keep.txt"
    sibling.write_text("keep", encoding="utf-8")

    replace_output(staged, output)

    assert not (output / "stale.py").exists()
    assert (output / "plugin.json").exists()
    assert sibling.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("host", ["claude-code", "cursor", "codex", "kimi", "antigravity"])
def test_portable_bundle_is_conformant_and_self_contained(host: str, tmp_path: Path) -> None:
    root = build(host, "portable", tmp_path / host)

    assert validate_bundle(root, "portable") == []
    assert json.loads((root / "plugin.json").read_text(encoding="utf-8"))["$schema"] == (
        "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    )
    server = json.loads((root / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["mem0"]
    assert server["type"] == "stdio"
    assert server["args"] == ["${PLUGIN_ROOT}/core/mcp_server.py"]
    assert "env" not in server
    for skill in (root / "skills").glob("*/SKILL.md"):
        frontmatter = skill.read_text(encoding="utf-8").split("---", 2)[1]
        keys = {line.split(":", 1)[0] for line in frontmatter.splitlines() if ":" in line}
        assert keys <= {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    assert not any(path.is_symlink() for path in root.rglob("*"))


def test_marketplaces_keep_public_names_and_reference_real_plugins() -> None:
    marketplace = json.loads((REPOSITORY_ROOT / "marketplace.json").read_text(encoding="utf-8"))
    sources = {plugin["name"]: plugin["source"] for plugin in marketplace["plugins"]}

    assert sources == {
        "mem0": "./integrations/agent-plugins/dist/claude-code/native",
        "mem0-cursor": "./integrations/agent-plugins/dist/cursor/native",
        "mem0-codex": "./integrations/agent-plugins/dist/codex/native",
        "mem0-openclaw": "./integrations/openclaw",
        "mem0-antigravity": "./integrations/agent-plugins/dist/antigravity/native",
        "mem0-kimi": "./integrations/agent-plugins/dist/kimi/native",
        "mem0-opencode": "./integrations/opencode-plugin",
    }
    for source in sources.values():
        assert (REPOSITORY_ROOT / source).exists()
