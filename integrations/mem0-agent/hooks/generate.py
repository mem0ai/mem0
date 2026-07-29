#!/usr/bin/env python3
"""Generate editor hook manifests from hooks.spec.yaml.

v1 kept four hand-written hook manifests (Claude Code, Cursor, Codex, Antigravity).
They drifted apart -- events present in one file and missing in another, timeouts that
disagreed, and hooks that had been dead in two editors for months without anyone
noticing. This script makes the spec the only thing a human edits.

    python3 hooks/generate.py            # write manifests for every supported editor
    python3 hooks/generate.py --check    # exit 1 if the committed manifests differ

The YAML parser here is a deliberately tiny stdlib-only subset (maps, lists of maps,
quoted/bare scalars, comments) because the package has zero runtime dependencies and
the spec is kept simple enough to parse. The spec is still valid YAML, so an editor's
syntax highlighting and any real YAML parser agree with this one.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

HOOKS_DIR = Path(__file__).resolve().parent
SPEC_PATH = HOOKS_DIR / "hooks.spec.yaml"
OUT_DIR = HOOKS_DIR / "generated"

HOOK_FIELDS = {
    "id", "event", "matcher", "command", "timeout",
    "background", "blocking", "local_only", "status_message", "why",
}
REQUIRED_HOOK_FIELDS = {"id", "event", "command", "why"}
# Events that run on the hot path of every turn and therefore may never do network I/O.
LOCAL_ONLY_EVENTS = {"UserPromptSubmit"}


class SpecError(RuntimeError):
    """The spec is malformed or violates a wiring rule."""


# --------------------------------------------------------------------------- YAML
_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-]*:")


def _strip_comment(line: str) -> str:
    """Drop a trailing `#` comment without touching `#` inside quotes."""
    out: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\" and i + 1 < len(line):
                out.append(ch)
                out.append(line[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            out.append(ch)
        elif ch in "\"'":
            quote = ch
            out.append(ch)
        elif ch == "#" and (not out or out[-1] in " \t"):
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def _scalar(token: str) -> Any:
    t = token.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'":
        return t[1:-1].replace('\\"', '"').replace("\\'", "'")
    low = t.lower()
    if low in ("", "null", "~"):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(t)
    except ValueError:
        pass
    try:
        return float(t)
    except ValueError:
        pass
    return t


def _lines(text: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise SpecError("tabs are not allowed for indentation")
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        rows.append((len(stripped) - len(stripped.lstrip(" ")), stripped.strip()))
    return rows


def _parse_block(rows: list[tuple[int, str]], i: int, indent: int) -> tuple[Any, int]:
    if rows[i][1].startswith("- "):
        return _parse_list(rows, i, indent)
    return _parse_map(rows, i, indent)


def _parse_map(rows: list[tuple[int, str]], i: int, indent: int) -> tuple[dict, int]:
    obj: dict[str, Any] = {}
    while i < len(rows):
        ind, text = rows[i]
        if ind < indent:
            break
        if ind > indent:
            raise SpecError(f"unexpected indentation at: {text!r}")
        if text.startswith("- "):
            break
        if not _KEY_RE.match(text):
            raise SpecError(f"expected `key: value`, got: {text!r}")
        key, _, rest = text.partition(":")
        key = key.strip()
        if rest.strip():
            obj[key] = _scalar(rest)
            i += 1
            continue
        # Block value: everything indented deeper than this key.
        if i + 1 < len(rows) and rows[i + 1][0] > ind:
            obj[key], i = _parse_block(rows, i + 1, rows[i + 1][0])
        else:
            obj[key] = None
            i += 1
    return obj, i


def _parse_list(rows: list[tuple[int, str]], i: int, indent: int) -> tuple[list, int]:
    items: list[Any] = []
    while i < len(rows) and rows[i][0] == indent and rows[i][1].startswith("- "):
        head = rows[i][1][2:].strip()
        children: list[tuple[int, str]] = []
        j = i + 1
        while j < len(rows) and rows[j][0] > indent:
            children.append(rows[j])
            j += 1
        if _KEY_RE.match(head):
            sub = [(indent + 2, head), *children]
            value, _ = _parse_map(sub, 0, indent + 2)
            items.append(value)
        else:
            if children:
                raise SpecError(f"scalar list item cannot have children: {head!r}")
            items.append(_scalar(head))
        i = j
    return items, i


def parse_yaml(text: str) -> dict:
    rows = _lines(text)
    if not rows:
        return {}
    value, _ = _parse_block(rows, 0, rows[0][0])
    if not isinstance(value, dict):
        raise SpecError("spec must be a mapping at the top level")
    return value


# --------------------------------------------------------------------------- spec
def load_spec(path: Path = SPEC_PATH) -> dict:
    spec = parse_yaml(path.read_text())
    validate(spec)
    return spec


def validate(spec: dict) -> dict:
    if not isinstance(spec.get("editors"), list) or not spec["editors"]:
        raise SpecError("spec needs a non-empty `editors:` list")
    if not isinstance(spec.get("hooks"), list) or not spec["hooks"]:
        raise SpecError("spec needs a non-empty `hooks:` list")

    seen_editors = set()
    for ed in spec["editors"]:
        for field in ("id", "supported", "output", "why"):
            if field not in ed:
                raise SpecError(f"editor {ed.get('id')!r} is missing `{field}`")
        if ed["id"] in seen_editors:
            raise SpecError(f"duplicate editor id {ed['id']!r}")
        seen_editors.add(ed["id"])
        if not isinstance(ed["supported"], bool):
            raise SpecError(f"editor {ed['id']!r}: `supported` must be a boolean")

    seen_hooks = set()
    for entry in spec["hooks"]:
        missing = REQUIRED_HOOK_FIELDS - set(entry)
        if missing:
            raise SpecError(f"hook {entry.get('id')!r} is missing {sorted(missing)}")
        unknown = set(entry) - HOOK_FIELDS
        if unknown:
            raise SpecError(f"hook {entry['id']!r} has unknown fields {sorted(unknown)}")
        if entry["id"] in seen_hooks:
            raise SpecError(f"duplicate hook id {entry['id']!r}")
        seen_hooks.add(entry["id"])
        for flag in ("background", "blocking", "local_only"):
            value = entry.get(flag, spec.get("defaults", {}).get(flag))
            if not isinstance(value, bool):
                raise SpecError(f"hook {entry['id']!r}: `{flag}` must be a boolean")
        if entry.get("background") and entry.get("blocking"):
            raise SpecError(f"hook {entry['id']!r}: a backgrounded hook cannot also be blocking")
        if entry["event"] in LOCAL_ONLY_EVENTS and not entry.get("local_only"):
            raise SpecError(
                f"hook {entry['id']!r} runs on {entry['event']} and must declare local_only: true"
            )
        # Commands must invoke the plugin's own bundled launcher. A bare console script is
        # not dependable: under pyenv the shim resolves against whichever Python version the
        # current directory selects, so a repo pinning a different version fails with
        # "pyenv: mem0-agent: command not found".
        cmd = str(entry["command"])
        if not cmd.startswith("${CLAUDE_PLUGIN_ROOT}/bin/mem0-agent "):
            raise SpecError(
                f"hook {entry['id']!r}: command must invoke "
                "${CLAUDE_PLUGIN_ROOT}/bin/mem0-agent"
            )
    return spec


def editor(spec: dict, editor_id: str) -> dict:
    for ed in spec["editors"]:
        if ed["id"] == editor_id:
            return ed
    raise SpecError(f"unknown editor {editor_id!r}")


def supported_editors(spec: dict) -> list[dict]:
    return [ed for ed in spec["editors"] if ed["supported"]]


# ----------------------------------------------------------------------- rendering
def render_command(entry: dict, ed: dict, defaults: dict | None = None) -> str:
    """Spec command -> the exact shell string an editor will run.

    Placeholders are editor-specific, MEM0_EDITOR is always pinned (so a hook cannot
    be misattributed), MEM0_LOCAL_ONLY is the machine-enforced half of the local-only
    contract, and background hooks are detached so a network write can never be on the
    developer's critical path.
    """
    defaults = defaults or {}
    command = str(entry["command"])
    for name, value in (ed.get("placeholders") or {}).items():
        command = command.replace("{" + name + "}", f'"{value}"')
    left = re.search(r"\{[a-z_]+\}", command)
    if left:
        raise SpecError(f"hook {entry['id']!r}: editor {ed['id']!r} has no value for {left.group()}")

    env = dict(ed.get("env") or {})
    if entry.get("local_only", defaults.get("local_only", False)):
        env["MEM0_LOCAL_ONLY"] = "1"
    prefix = "".join(f"{k}={v} " for k, v in env.items())
    command = prefix + command
    if entry.get("background", defaults.get("background", False)):
        command = f"({command} >/dev/null 2>&1 &)"
    return command


def build_manifest(spec: dict, editor_id: str = "claude-code") -> dict:
    """Emit the nested schema Claude Code expects.

    {"hooks": {"<Event>": [{"matcher": ..., "hooks": [{"type": "command", ...}]}]}}
    Entries sharing an event and matcher are merged into one group, in spec order.
    """
    ed = editor(spec, editor_id)
    if ed.get("dialect") != "claude-code":
        raise SpecError(f"editor {editor_id!r} uses dialect {ed.get('dialect')!r}, not yet emitted")
    defaults = spec.get("defaults") or {}

    events: dict[str, list[dict]] = {}
    for entry in spec["hooks"]:
        step: dict[str, Any] = {
            "type": "command",
            "command": render_command(entry, ed, defaults),
            "timeout": int(entry.get("timeout") or defaults.get("timeout") or 10),
        }
        if entry.get("status_message"):
            step["statusMessage"] = entry["status_message"]

        groups = events.setdefault(entry["event"], [])
        matcher = entry.get("matcher")
        for group in groups:
            if group.get("matcher") == matcher:
                group["hooks"].append(step)
                break
        else:
            group = {}
            if matcher:
                group["matcher"] = matcher
            group["hooks"] = [step]
            groups.append(group)
    return {"hooks": events}


def serialize(manifest: dict) -> str:
    return json.dumps(manifest, indent=2) + "\n"


def output_path(spec: dict, editor_id: str) -> Path:
    return (HOOKS_DIR / editor(spec, editor_id)["output"]).resolve()


# ----------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate editor hook manifests from hooks.spec.yaml")
    ap.add_argument("--check", action="store_true",
                    help="regenerate in memory and exit non-zero if the committed manifest differs")
    ap.add_argument("--editor", action="append", default=None,
                    help="limit to one editor id (default: every supported editor)")
    ap.add_argument("--spec", type=Path, default=SPEC_PATH)
    args = ap.parse_args(argv)

    try:
        spec = load_spec(args.spec)
    except (SpecError, OSError) as exc:
        print(f"spec error: {exc}", file=sys.stderr)
        return 2

    ids = args.editor or [ed["id"] for ed in supported_editors(spec)]
    drift = 0
    for editor_id in ids:
        try:
            manifest = build_manifest(spec, editor_id)
        except SpecError as exc:
            print(f"{editor_id}: {exc}", file=sys.stderr)
            return 2
        wanted = serialize(manifest)
        path = output_path(spec, editor_id)
        events = ", ".join(manifest["hooks"])
        if args.check:
            current = path.read_text() if path.exists() else None
            if current != wanted:
                what = "missing" if current is None else "out of date"
                print(f"DRIFT {path.name} is {what}; run `python3 hooks/generate.py`", file=sys.stderr)
                drift += 1
            else:
                print(f"ok    {path.name} ({len(manifest['hooks'])} events: {events})")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(wanted)
            print(f"wrote {path} ({len(manifest['hooks'])} events: {events})")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
