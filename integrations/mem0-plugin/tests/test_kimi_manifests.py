"""Kimi Code plugin manifest checks.

Kimi is the only host that needs *two* copies of its manifest:

* ``integrations/mem0-plugin/.kimi-plugin/plugin.json`` — sits alongside every
  other host's manifest and serves ``/plugins install <local path>``.
* ``.kimi-plugin/plugin.json`` at the repo root — serves
  ``/plugins install https://github.com/mem0ai/mem0/tree/main``, because Kimi
  looks for a manifest at the downloaded archive's root only and has no way to
  be pointed at a subdirectory.

That duplication is deliberate (see README, "Why there are two manifests"), but
it is drift-prone, so these tests pin it down: the two files must stay identical
apart from the paths that are necessarily plugin-root-relative (``skills`` and
the script prefix inside ``hooks``), and both must satisfy the schema Kimi
actually enforces in ``packages/agent-core-v2/src/app/plugin/manifest.ts``.

Everything here is stdlib-only so it runs in mem0-plugin-checks.yml with no
extra dependencies.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = PLUGIN_DIR.parents[1]

ROOT_MANIFEST = REPO_ROOT / ".kimi-plugin" / "plugin.json"
DIR_MANIFEST = PLUGIN_DIR / ".kimi-plugin" / "plugin.json"
MARKETPLACE = REPO_ROOT / ".kimi-plugin" / "marketplace.json"

# The fields allowed to differ between the two manifests. Both point at the same
# skills directory and the same hook scripts, expressed relative to their own
# plugin root ($KIMI_PLUGIN_ROOT is the directory holding `.kimi-plugin/`).
KNOWN_DIFFERENT_FIELDS = {"skills", "hooks"}
EXPECTED_SKILLS = {
    ROOT_MANIFEST: "./integrations/mem0-plugin/skills/",
    DIR_MANIFEST: "./skills/",
}
# The path segment each manifest inserts between $KIMI_PLUGIN_ROOT and scripts/.
HOOK_PATH_PREFIX = {
    ROOT_MANIFEST: "/integrations/mem0-plugin",
    DIR_MANIFEST: "",
}

# agent/externalHooks/configSection.ts — HookDefSchema is `.strict()`, so any
# unknown key makes readHooks drop the whole entry with a warning.
HOOK_DEF_KEYS = {"event", "matcher", "command", "timeout"}
HOOK_DEF_REQUIRED_KEYS = {"event", "command"}

# agent/externalHooks/types.ts — HOOK_EVENT_TYPES.
HOOK_EVENT_TYPES = {
    "PreToolUse",
    "PostToolUse",
    "PostToolUseFailure",
    "PermissionRequest",
    "PermissionResult",
    "UserPromptSubmit",
    "UserPromptQueued",
    "TurnStarted",
    "Stop",
    "StopFailure",
    "Interrupt",
    "SessionStart",
    "SessionEnd",
    "SessionHeartbeat",
    "SubagentStart",
    "SubagentStop",
    "TaskStarted",
    "PreCompact",
    "PostCompact",
    "Notification",
}

# Every Kimi hook is routed through the adapter, which reshapes Kimi's payload
# into the Claude-shaped stdin the mem0 scripts expect and unwraps
# hookSpecificOutput.additionalContext (which Kimi does not understand) back
# into plain stdout. See scripts/kimi_hook_shim.sh.
HOOK_SHIM = "kimi_hook_shim.sh"
HOOK_COMMAND_RE = re.compile(
    r'^"\$KIMI_PLUGIN_ROOT(?P<prefix>[^"]*)/scripts/'
    + re.escape(HOOK_SHIM)
    + r'"\s+(?P<target>[A-Za-z0-9_.-]+\.sh)$'
)

# Coverage parity with hooks/codex-hooks.json.
EXPECTED_HOOK_SCRIPTS = {
    "block_memory_write.sh",
    "enforce_metadata_defaults.sh",
    "on_file_read.sh",
    "on_session_start.sh",
    "on_user_prompt.sh",
    "on_post_tool_use.sh",
    "on_bash_output.sh",
    "on_stop.sh",
    "on_pre_compact.sh",
}

# manifest.ts:185 (types.ts) — PLUGIN_NAME_REGEX
PLUGIN_NAME_REGEX = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

# manifest.ts:517-528 — readInterface reads exactly these keys and drops the rest.
ALLOWED_INTERFACE_KEYS = {
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "websiteURL",
}

# manifest.ts:21-28 — UNSUPPORTED_RUNTIME_FIELDS
UNSUPPORTED_RUNTIME_FIELDS = {
    "tools",
    "apps",
    "inject",
    "configFile",
    "config_file",
    "bootstrap",
}

# mcpCore/config-schema.ts — discriminated union on `transport`.
MCP_TRANSPORTS = {"stdio", "http", "sse"}

# The manifests of every host that ships from integrations/mem0-plugin and
# carries a semver `version`. Kimi must not drift away from them.
SIBLING_MANIFESTS = [
    PLUGIN_DIR / ".claude-plugin" / "plugin.json",
    PLUGIN_DIR / ".codex-plugin" / "plugin.json",
    PLUGIN_DIR / ".cursor-plugin" / "plugin.json",
]

MANIFESTS = [ROOT_MANIFEST, DIR_MANIFEST]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _plugin_root(manifest_path: Path) -> Path:
    # pluginRoot is the directory containing `.kimi-plugin/`.
    return manifest_path.parent.parent


# --------------------------------------------------------------------------
# Drift guard: the two manifests are one artifact stored twice.
# --------------------------------------------------------------------------


def test_both_manifests_exist():
    for path in MANIFESTS:
        assert path.is_file(), f"missing Kimi manifest: {path}"


def test_manifests_differ_only_in_plugin_root_relative_paths():
    # `skills` and the script prefix inside `hooks` are the same targets spelled
    # relative to each manifest's own plugin root. Nothing else may diverge.
    root = _load(ROOT_MANIFEST)
    nested = _load(DIR_MANIFEST)

    assert set(root) == set(nested), (
        "Kimi manifests declare different fields. Keep "
        f"{ROOT_MANIFEST.relative_to(REPO_ROOT)} and "
        f"{DIR_MANIFEST.relative_to(REPO_ROOT)} in sync."
    )

    differing = {key for key in root if root[key] != nested[key]}
    assert differing == KNOWN_DIFFERENT_FIELDS, (
        f"Kimi manifests may only differ in {sorted(KNOWN_DIFFERENT_FIELDS)}, "
        f"but these differ: {sorted(differing)}."
    )


def test_manifests_have_identical_key_order():
    # Same artifact stored twice — keep them visually diffable.
    assert list(_load(ROOT_MANIFEST)) == list(_load(DIR_MANIFEST))


# --------------------------------------------------------------------------
# Schema: what Kimi's parseManifest actually enforces.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_manifest_is_a_json_object(manifest_path: Path):
    assert isinstance(_load(manifest_path), dict)


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_name_matches_kimi_regex(manifest_path: Path):
    name = _load(manifest_path).get("name")
    assert isinstance(name, str) and name.strip(), '"name" is required'
    assert PLUGIN_NAME_REGEX.match(name.strip()), (
        f'"name" must match {PLUGIN_NAME_REGEX.pattern} (got "{name}")'
    )


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_skills_path_resolves_inside_its_plugin_root(manifest_path: Path):
    skills = _load(manifest_path)["skills"]
    assert skills == EXPECTED_SKILLS[manifest_path]
    # resolveDirListField: must start with "./", must be a directory, and must
    # not escape the plugin root.
    assert skills.startswith("./"), '"skills" path must start with "./"'
    plugin_root = _plugin_root(manifest_path).resolve()
    resolved = (plugin_root / skills).resolve()
    assert resolved.is_dir(), f"skills path is not a directory: {resolved}"
    assert os.path.commonpath([resolved, plugin_root]) == str(plugin_root), (
        "skills path resolves outside the plugin root"
    )


def test_both_manifests_point_at_the_same_skills_directory():
    resolved = {
        (_plugin_root(path).resolve() / _load(path)["skills"]).resolve() for path in MANIFESTS
    }
    assert resolved == {(PLUGIN_DIR / "skills").resolve()}


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_no_agents_directory_shadows_the_plugin_root(manifest_path: Path):
    # manifest.ts:108-114 — when `agents` is unset, Kimi silently adopts an
    # `agents/` directory at the plugin root. For the repo-root manifest that
    # would be some unrelated top-level directory, so assert there is none.
    manifest = _load(manifest_path)
    if "agents" in manifest:
        return
    assert not (_plugin_root(manifest_path) / "agents").is_dir(), (
        "an `agents/` directory at the plugin root would be auto-loaded by Kimi; "
        "declare `agents` explicitly in the manifest"
    )


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_session_start_skill_exists(manifest_path: Path):
    session_start = _load(manifest_path)["sessionStart"]
    assert isinstance(session_start, dict)
    skill = session_start.get("skill")
    assert isinstance(skill, str) and skill.strip()
    assert (PLUGIN_DIR / "skills" / skill / "SKILL.md").is_file(), (
        f'sessionStart.skill "{skill}" has no SKILL.md'
    )


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_mcp_servers_are_inline_and_well_formed(manifest_path: Path):
    # readMcpServers requires an object; a path string is dropped with a warning,
    # which is why Kimi cannot reference .kimi-mcp.json the way Cursor/Codex do.
    servers = _load(manifest_path)["mcpServers"]
    assert isinstance(servers, dict), '"mcpServers" must be an inline object'
    assert servers, '"mcpServers" must not be empty'
    for name, config in servers.items():
        assert name.strip(), "MCP server names must be non-empty"
        assert isinstance(config, dict)
        transport = config.get("transport")
        assert transport in MCP_TRANSPORTS, (
            f'MCP server "{name}": transport must be one of {sorted(MCP_TRANSPORTS)} '
            f"(got {transport!r}); Kimi discriminates on `transport`, not `type`"
        )
        if transport in {"http", "sse"}:
            assert isinstance(config.get("url"), str) and config["url"].startswith("http")
            # Kimi passes `headers` through verbatim with no ${VAR} expansion, so
            # credentials must go through bearerTokenEnvVar.
            token_env = config.get("bearerTokenEnvVar")
            assert isinstance(token_env, str) and token_env, (
                f'MCP server "{name}": remote transports must authenticate via '
                "bearerTokenEnvVar (headers are not interpolated)"
            )
            assert "${" not in json.dumps(config.get("headers", {})), (
                f'MCP server "{name}": headers are not variable-expanded by Kimi'
            )
        else:
            assert isinstance(config.get("command"), str) and config["command"]


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_interface_only_uses_supported_keys(manifest_path: Path):
    interface = _load(manifest_path).get("interface")
    if interface is None:
        return
    assert isinstance(interface, dict)
    unsupported = set(interface) - ALLOWED_INTERFACE_KEYS
    assert not unsupported, (
        f"Kimi's readInterface drops these keys: {sorted(unsupported)}. "
        f"Supported keys: {sorted(ALLOWED_INTERFACE_KEYS)}."
    )
    for key, value in interface.items():
        assert isinstance(value, str) and value.strip()


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_no_unsupported_runtime_fields(manifest_path: Path):
    present = set(_load(manifest_path)) & UNSUPPORTED_RUNTIME_FIELDS
    assert not present, f"Kimi ignores these fields and warns about them: {sorted(present)}"


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_hooks_are_an_inline_array(manifest_path: Path):
    # readHooks warns and drops anything that is not an array, so a
    # "hooks": "./hooks/kimi-hooks.json" reference (the Codex/Cursor style)
    # would silently do nothing.
    hooks = _load(manifest_path).get("hooks")
    assert isinstance(hooks, list) and hooks, (
        '"hooks" must be a non-empty inline array of {event, command} objects; '
        "Kimi does not accept a path to a hooks file"
    )


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_hook_entries_satisfy_hook_def_schema(manifest_path: Path):
    for index, hook in enumerate(_load(manifest_path)["hooks"]):
        where = f"hooks[{index}]"
        assert isinstance(hook, dict), f"{where}: entry must be an object"

        unknown = set(hook) - HOOK_DEF_KEYS
        assert not unknown, (
            f"{where}: HookDefSchema is .strict(), so {sorted(unknown)} would make "
            "readHooks drop this entry"
        )
        missing = HOOK_DEF_REQUIRED_KEYS - set(hook)
        assert not missing, f"{where}: missing required key(s) {sorted(missing)}"

        assert hook["event"] in HOOK_EVENT_TYPES, (
            f"{where}: invalid event {hook['event']!r}; "
            f"valid events: {sorted(HOOK_EVENT_TYPES)}"
        )
        assert isinstance(hook["command"], str) and len(hook["command"]) >= 1, (
            f"{where}: command must be a non-empty string"
        )
        if "matcher" in hook:
            assert isinstance(hook["matcher"], str), f"{where}: matcher must be a string"
            # Kimi compiles the matcher with `new RegExp(...)` and treats a
            # compile failure as "never matches".
            re.compile(hook["matcher"])
        if "timeout" in hook:
            timeout = hook["timeout"]
            assert isinstance(timeout, int) and not isinstance(timeout, bool), (
                f"{where}: timeout must be an integer"
            )
            assert 1 <= timeout <= 600, f"{where}: timeout {timeout} is outside 1..600"


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_hook_commands_resolve_to_executable_scripts(manifest_path: Path):
    plugin_root = _plugin_root(manifest_path).resolve()
    scripts_dir = PLUGIN_DIR / "scripts"
    seen: set[str] = set()

    for index, hook in enumerate(_load(manifest_path)["hooks"]):
        where = f"hooks[{index}]"
        match = HOOK_COMMAND_RE.match(hook["command"])
        assert match, (
            f"{where}: command must invoke the Kimi adapter as "
            f'"$KIMI_PLUGIN_ROOT/<prefix>/scripts/{HOOK_SHIM}" <script.sh>, got '
            f"{hook['command']!r}"
        )
        assert match.group("prefix") == HOOK_PATH_PREFIX[manifest_path], (
            f"{where}: $KIMI_PLUGIN_ROOT is {plugin_root}, so the scripts prefix "
            f"must be {HOOK_PATH_PREFIX[manifest_path]!r}"
        )

        target = match.group("target")
        seen.add(target)
        for path in (scripts_dir / HOOK_SHIM, scripts_dir / target):
            assert path.is_file(), f"{where}: referenced script does not exist: {path}"
            assert os.access(path, os.X_OK), f"{where}: script is not executable: {path}"
            # The command is built from $KIMI_PLUGIN_ROOT, so it must live there.
            assert os.path.commonpath([path.resolve(), plugin_root]) == str(plugin_root), (
                f"{where}: {path} is outside the plugin root"
            )

    assert seen == EXPECTED_HOOK_SCRIPTS, (
        "Kimi hook coverage must match hooks/codex-hooks.json; "
        f"missing={sorted(EXPECTED_HOOK_SCRIPTS - seen)} "
        f"extra={sorted(seen - EXPECTED_HOOK_SCRIPTS)}"
    )


@pytest.mark.parametrize("manifest_path", MANIFESTS, ids=lambda p: str(p.parent.parent.name))
def test_hook_commands_are_unique(manifest_path: Path):
    # externalHooksRunner/runner.ts dedups matched hooks on (cwd, command), and
    # every plugin hook shares the plugin root as its cwd — two entries with the
    # same command would silently collapse into one.
    commands = [hook["command"] for hook in _load(manifest_path)["hooks"]]
    duplicates = {cmd for cmd in commands if commands.count(cmd) > 1}
    assert not duplicates, f"duplicate hook commands would be deduped by Kimi: {sorted(duplicates)}"


def test_both_manifests_declare_the_same_hooks():
    def normalise(manifest_path: Path) -> list[dict]:
        prefix = HOOK_PATH_PREFIX[manifest_path]
        return [
            {
                **hook,
                "command": hook["command"].replace(
                    f"$KIMI_PLUGIN_ROOT{prefix}/scripts/", "$PLUGIN/scripts/"
                ),
            }
            for hook in _load(manifest_path)["hooks"]
        ]

    assert normalise(ROOT_MANIFEST) == normalise(DIR_MANIFEST), (
        "the two Kimi manifests must declare identical hooks; only the "
        "$KIMI_PLUGIN_ROOT-relative script prefix may differ"
    )


# --------------------------------------------------------------------------
# Cross-host consistency.
# --------------------------------------------------------------------------


def test_version_matches_the_other_host_manifests():
    kimi_version = _load(DIR_MANIFEST)["version"]
    for sibling in SIBLING_MANIFESTS:
        assert _load(sibling)["version"] == kimi_version, (
            f"{sibling.relative_to(REPO_ROOT)} is at "
            f"{_load(sibling)['version']} but the Kimi manifests are at "
            f"{kimi_version}; bump all host manifests together"
        )


def test_shared_metadata_matches_the_other_host_manifests():
    kimi = _load(DIR_MANIFEST)
    for field in ("name", "homepage", "repository", "license", "keywords"):
        for sibling in SIBLING_MANIFESTS:
            other = _load(sibling)
            if field not in other:
                continue
            if field == "keywords":
                # Cursor carries one extra keyword; only require a shared core.
                assert set(kimi[field]) <= set(other[field]) or set(other[field]) <= set(
                    kimi[field]
                ), f"{sibling.name}: keywords diverge from the Kimi manifest"
                continue
            assert other[field] == kimi[field], (
                f"{sibling.relative_to(REPO_ROOT)}: {field} diverges from the Kimi manifest"
            )


# --------------------------------------------------------------------------
# Marketplace catalog.
# --------------------------------------------------------------------------


def test_marketplace_catalog_matches_kimi_schema():
    # apps/kimi-code/src/utils/plugin-marketplace.ts — parsePluginMarketplace /
    # parseMarketplaceEntry. Note this schema differs from every other host's
    # marketplace.json: entries key on `id`, and `source` must be a string.
    catalog = _load(MARKETPLACE)
    assert isinstance(catalog, dict)
    plugins = catalog.get("plugins")
    assert isinstance(plugins, list) and plugins, 'catalog must contain a "plugins" array'

    manifest = _load(ROOT_MANIFEST)
    for entry in plugins:
        assert isinstance(entry, dict)
        assert isinstance(entry.get("id"), str) and entry["id"].strip(), (
            'each entry must define a string "id" (Kimi does not fall back to "name")'
        )
        source = entry.get("source")
        assert isinstance(source, str), (
            '"source" must be a string; the object form used by the Antigravity '
            "and Codex catalogs is rejected by Kimi"
        )
        # resolveEntrySource resolves a relative source against the catalog URL,
        # which for a raw.githubusercontent.com catalog yields a raw URL that
        # resolveInstallSource would treat as a zip. Require an absolute URL.
        assert source.startswith("https://github.com/"), (
            "source must be an absolute github.com URL so resolveInstallSource "
            "classifies it as a GitHub install"
        )
        # A bare repo URL installs the *latest release tag*, which for this repo
        # is an unrelated SDK tag. Pin the ref explicitly.
        assert re.match(r"^https://github\.com/[^/]+/[^/]+/(tree|releases/tag|commit)/", source), (
            "pin the ref (/tree/<branch>, /releases/tag/<tag> or /commit/<sha>): a bare "
            "repo URL resolves to github.com/mem0ai/mem0/releases/latest, which is an "
            "unrelated SDK tag that does not contain the plugin manifest"
        )
        if "tier" in entry:
            assert entry["tier"] in {"official", "curated"}
        if "type" in entry:
            assert entry["type"] in {"plugin", "managed", "guide"}
        assert entry.get("id") == manifest["name"]
        assert entry.get("version") == manifest["version"], (
            "marketplace entry version must track the manifest version"
        )
