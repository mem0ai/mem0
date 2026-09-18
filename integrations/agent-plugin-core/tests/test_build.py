from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from build.build import (  # noqa: E402
    build,
    bundle_drift,
    render_template,
    replace_output,
    sync_generated,
)
from build.validate import validate_bundle  # noqa: E402


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


def test_build_cannot_replace_an_installable_source_directory(tmp_path: Path) -> None:
    staged = tmp_path / "staged"
    staged.mkdir()

    with pytest.raises(ValueError, match="protected output path"):
        replace_output(staged, REPOSITORY_ROOT / "integrations" / "claude-code-plugin")


def test_portable_bundle_is_conformant_and_self_contained(tmp_path: Path) -> None:
    root = build("mem0-agent-plugin", "portable", tmp_path / "mem0-agent-plugin")

    assert validate_bundle(root, "portable") == []
    assert json.loads((root / "plugin.json").read_text(encoding="utf-8"))["$schema"] == (
        "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    )
    server = json.loads((root / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]["mem0"]
    assert server["type"] == "stdio"
    assert server["args"] == ["${PLUGIN_ROOT}/core/mcp_server.py"]
    assert "env" not in server
    assert not (root / "core" / "hook_runner.py").exists()
    assert not (root / "core" / "flush_worker.py").exists()
    assert not (root / "agents").exists()
    for skill in (root / "skills").glob("*/SKILL.md"):
        frontmatter = skill.read_text(encoding="utf-8").split("---", 2)[1]
        keys = {line.split(":", 1)[0] for line in frontmatter.splitlines() if ":" in line}
        assert keys <= {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    assert not any(path.is_symlink() for path in root.rglob("*"))


@pytest.mark.parametrize("host", ["claude-code", "cursor", "codex", "kimi", "antigravity"])
def test_native_bundle_is_self_contained(host: str, tmp_path: Path) -> None:
    root = build(host, "native", tmp_path / host)

    assert (root / "core" / "memory_core.py").is_file()
    assert (root / "skills" / "remember" / "SKILL.md").is_file()
    assert not any(path.is_symlink() for path in root.rglob("*"))


@pytest.mark.parametrize("host", ["claude-code", "cursor", "codex", "kimi", "antigravity"])
def test_only_claude_bundles_sidekick(host: str, tmp_path: Path) -> None:
    root = build(host, "native", tmp_path / host)
    if host == "claude-code":
        agent = (root / "agents" / "sidekick.md").read_text()
        assert "model: sonnet" in agent
        assert "isolation: worktree" in agent
    else:
        assert not (root / "agents").exists()
        for path in root.rglob("*.json"):
            assert "sidekick" not in path.read_text().lower()


@pytest.mark.parametrize("host", ["claude-code", "cursor", "codex", "kimi", "antigravity"])
def test_native_control_skills_select_the_host_store(host: str, tmp_path: Path) -> None:
    root = build(host, "native", tmp_path / host)
    status = (root / "skills" / "status" / "SKILL.md").read_text(encoding="utf-8")

    assert f'--harness "{host}"' in status
    if host == "claude-code":
        assert '--plugin-data-dir "${CLAUDE_PLUGIN_DATA}"' in status
    elif host == "codex":
        assert '--plugin-data-dir "${PLUGIN_DATA}"' in status


@pytest.mark.parametrize(
    ("host", "kind"),
    [
        ("mem0-agent-plugin", "portable"),
        ("claude-code", "native"),
        ("cursor", "native"),
        ("codex", "native"),
        ("kimi", "native"),
        ("antigravity", "native"),
        ("hermes", "native"),
    ],
)
def test_installable_plugin_directories_are_current(host: str, kind: str) -> None:
    assert bundle_drift(host, kind) == []


def test_marketplaces_keep_public_names_and_reference_real_plugins() -> None:
    marketplace = json.loads((REPOSITORY_ROOT / "marketplace.json").read_text(encoding="utf-8"))
    sources = {plugin["name"]: plugin["source"] for plugin in marketplace["plugins"]}

    assert sources == {"mem0": "./integrations/claude-code-plugin"}
    for source in sources.values():
        assert (REPOSITORY_ROOT / source).exists()

    codex_marketplace = json.loads(
        (REPOSITORY_ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert [plugin["name"] for plugin in codex_marketplace["plugins"]] == ["mem0"]
    codex = codex_marketplace["plugins"][0]
    assert codex["source"]["path"] == "./integrations/codex-plugin"


def test_native_bundle_can_select_runtime_without_skills(tmp_path: Path, monkeypatch) -> None:
    from build import build as builder

    source = tmp_path / "plugin"
    source.mkdir()
    (source / "__init__.py").write_text("# Native plugin adapter\n", encoding="utf-8")
    (source / "plugin-build.json").write_text(
        json.dumps(
            {
                "native": {
                    "pluginRoot": "${PLUGIN_ROOT}",
                    "pythonFiles": ["message_utils.py"],
                    "skills": False,
                    "files": {"__init__.py": "__init__.py"},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setitem(builder.NATIVE_PLUGINS, "test-host", source)
    stale_skill = source / "skills" / "remember" / "SKILL.md"
    stale_skill.parent.mkdir(parents=True)
    stale_skill.write_text("stale generated skill", encoding="utf-8")

    root = build("test-host", "native", tmp_path / "output")

    assert {path.name for path in (root / "core").iterdir()} == {"message_utils.py"}
    assert not (root / "skills").exists()
    assert (root / "__init__.py").read_text(encoding="utf-8") == "# Native plugin adapter\n"
    sync_generated("test-host", "native")
    assert bundle_drift("test-host", "native") == []
    assert not (source / "skills").exists()


@pytest.mark.parametrize("files", ["message_utils.py", ["../README.md"], ["/tmp/source.py"], [7], ["missing.py"]])
def test_native_runtime_selection_rejects_invalid_sources(files, tmp_path: Path) -> None:
    from build.build import _build_native

    with pytest.raises(ValueError, match="pythonFiles|native source file"):
        _build_native(
            "test",
            tmp_path,
            tmp_path,
            {
                "native": {
                    "pluginRoot": "${PLUGIN_ROOT}",
                    "pythonFiles": files,
                }
            },
        )


def test_native_runtime_selection_rejects_escaping_symlink(tmp_path: Path, monkeypatch) -> None:
    from build import build as builder

    source = tmp_path / "shared" / "python"
    source.mkdir(parents=True)
    secret = tmp_path / "outside.py"
    secret.write_text("secret", encoding="utf-8")
    (source / "message_utils.py").symlink_to(secret)
    monkeypatch.setattr(builder, "CORE_ROOT", source.parent)
    staged = tmp_path / "bundle"
    staged.mkdir()

    with pytest.raises(ValueError, match="inside their roots"):
        builder._build_native(
            "test",
            tmp_path,
            staged,
            {
                "native": {
                    "pluginRoot": "${PLUGIN_ROOT}",
                    "pythonFiles": ["message_utils.py"],
                }
            },
        )


def test_hermes_bundle_uses_only_host_independent_runtime(tmp_path: Path) -> None:
    root = build("hermes", "native", tmp_path / "hermes")

    assert {path.name for path in (root / "core").iterdir()} == {"message_utils.py"}
    assert (root / "__init__.py").is_file()
    assert (root / "plugin.yaml").is_file()
    assert not (root / "skills").exists()
    assert not (root / "agents").exists()
