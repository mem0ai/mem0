"""The mem0 plugin's version is duplicated across five manifests; they must agree.

Regression guard: release 0.2.14 bumped the two marketplace manifests but left the
three per-host plugin.json files at 0.2.13, so a host that advertised 0.2.14 installed
a plugin whose own manifest reported 0.2.13 and never converged.

The Antigravity manifest (integrations/mem0-plugin/plugin.json) tracks its own version
line and is deliberately not part of this set.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN_SOURCE = "./integrations/mem0-plugin"

PLUGIN_MANIFESTS = [
    REPO_ROOT / "integrations" / "mem0-plugin" / host / "plugin.json"
    for host in (".claude-plugin", ".cursor-plugin", ".codex-plugin")
]
MARKETPLACE_MANIFESTS = [
    REPO_ROOT / ".claude-plugin" / "marketplace.json",
    REPO_ROOT / ".cursor-plugin" / "marketplace.json",
]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _declared_version(path: Path) -> str:
    manifest = _load(path)
    if "plugins" not in manifest:
        return manifest["version"]
    entry = next(p for p in manifest["plugins"] if p["source"] == PLUGIN_SOURCE)
    return entry["version"]


def test_all_manifests_declare_the_same_version():
    versions = {
        path.relative_to(REPO_ROOT).as_posix(): _declared_version(path)
        for path in PLUGIN_MANIFESTS + MARKETPLACE_MANIFESTS
    }
    assert len(set(versions.values())) == 1, f"plugin version drift: {versions}"
