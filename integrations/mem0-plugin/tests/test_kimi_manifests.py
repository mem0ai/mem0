"""Validate the Kimi Code plugin manifests and hook wiring.

Kimi Code loads a plugin from `.kimi-plugin/plugin.json`. This test locks down
the structural contract so a stray edit cannot silently break the plugin:

  - both manifests parse and carry the required Kimi fields
  - the MCP server uses Kimi's supported auth (transport/url/bearerTokenEnvVar)
  - every hook command routes through kimi_hook_shim.sh and targets a script
    that actually exists in scripts/
  - the sessionStart skill and skills/ path resolve on disk
"""

import json
import os

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(PLUGIN_DIR))

SUBDIR_MANIFEST = os.path.join(PLUGIN_DIR, ".kimi-plugin", "plugin.json")
ROOT_MARKETPLACE = os.path.join(REPO_ROOT, ".kimi-plugin", "marketplace.json")
SHIM = os.path.join(PLUGIN_DIR, "scripts", "kimi_hook_shim.sh")


def _load(path):
    with open(path) as fh:
        return json.load(fh)


def test_manifest_parses_and_has_required_fields():
    m = _load(SUBDIR_MANIFEST)
    assert m["name"] == "mem0"
    for field in ("version", "description", "skills", "mcpServers", "interface", "hooks"):
        assert field in m, f"manifest missing {field}"


def test_mcp_uses_kimi_supported_auth():
    srv = _load(SUBDIR_MANIFEST)["mcpServers"]["mem0"]
    assert srv["transport"] == "http"
    assert srv["url"] == "https://mcp.mem0.ai/mcp/"  # trailing slash avoids the 307 redirect
    # Kimi reads the named env var and sends Authorization: Bearer <value>.
    assert srv["bearerTokenEnvVar"] == "MEM0_API_KEY"
    assert "headers" not in srv  # Kimi does not interpolate ${env:...} inside headers


def test_sessionstart_skill_and_skills_dir_resolve():
    m = _load(SUBDIR_MANIFEST)
    assert m["skills"] == "./skills/"
    assert os.path.isdir(os.path.join(PLUGIN_DIR, "skills"))
    start_skill = m["sessionStart"]["skill"]
    assert os.path.isdir(os.path.join(PLUGIN_DIR, "skills", start_skill))


def test_shim_exists_and_is_executable():
    assert os.path.isfile(SHIM)
    assert os.access(SHIM, os.X_OK), "kimi_hook_shim.sh must be executable"


def test_every_hook_routes_through_shim_to_a_real_script():
    hooks = _load(SUBDIR_MANIFEST)["hooks"]
    assert hooks, "no hooks declared"
    valid_events = {
        "SessionStart", "UserPromptSubmit", "PreToolUse",
        "PostToolUse", "Stop", "PreCompact",
    }
    for hook in hooks:
        assert hook["event"] in valid_events, f"unknown event {hook['event']}"
        cmd = hook["command"]
        assert "kimi_hook_shim.sh" in cmd, f"hook must route through the shim: {cmd}"
        assert "$KIMI_PLUGIN_ROOT/scripts/kimi_hook_shim.sh" in cmd
        target = cmd.rsplit('"', 1)[-1].strip()  # the script name after the shim
        assert target.endswith(".sh")
        assert os.path.isfile(os.path.join(PLUGIN_DIR, "scripts", target)), \
            f"hook target script missing: {target}"


def test_root_marketplace_catalog():
    cat = _load(ROOT_MARKETPLACE)
    entry = cat["plugins"][0]
    assert entry["id"] == "mem0"  # Kimi marketplace entries key on id
    assert entry["source"].startswith("https://github.com/mem0ai/mem0")
