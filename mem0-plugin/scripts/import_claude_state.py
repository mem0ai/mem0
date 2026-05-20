#!/usr/bin/env python3
"""Holistic import of on-disk Claude state into mem0.

Backfills the user's existing CLAUDE.md hierarchy (+ @imports),
`.claude/rules`, `~/.claude/projects/*/memory`, and `~/.claude/agent-memory`
into mem0 as searchable memories. One-shot. Idempotent across re-runs via a
marker file at ~/.mem0/imports/claude-state.json.

Patterned on on_pre_compact.py: urllib-based POSTs, stderr logging,
_identity.resolve_user_id() for user_id, and an optional ~/.mem0/hooks.log
when MEM0_DEBUG is set.

Invocation:
    python3 import_claude_state.py [--dry-run] [--reset] [--no-infer]
                                   [--source TYPE]

Exit codes:
    0 = success (including dry-run and partial failures)
    1 = fatal (missing MEM0_API_KEY, auth failure)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Logging ──────────────────────────────────────────────────────────────

log = logging.getLogger("mem0-import-claude-state")
log.setLevel(logging.DEBUG)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("[mem0-import-claude-state] %(message)s"))
log.addHandler(_handler)

if os.environ.get("MEM0_DEBUG"):
    _log_dir = os.path.expanduser("~/.mem0")
    try:
        os.makedirs(_log_dir, exist_ok=True)
        _file_handler = logging.FileHandler(os.path.join(_log_dir, "hooks.log"))
        _file_handler.setFormatter(
            logging.Formatter("[mem0-import-claude-state] %(asctime)s %(message)s")
        )
        log.addHandler(_file_handler)
    except OSError:
        pass


# ── Constants ────────────────────────────────────────────────────────────

API_URL = "https://api.mem0.ai"
REQUEST_TIMEOUT_SECS = 15
RETRY_SLEEP_SECS = 2.0

MARKER_PATH = Path.home() / ".mem0" / "imports" / "claude-state.json"
EMPTY_MARKER: dict[str, Any] = {"schema_version": 1, "imports": []}

MAX_CHARS_PER_CHUNK = 2000
MIN_CHARS_PER_CHUNK = 200
MAX_IMPORT_DEPTH = 5

H1_LINE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
H2_LINE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
H3_LINE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
FENCE_LINE = re.compile(r"^\s*(```+|~~~+)")
IMPORT_LINE_RE = re.compile(r"(?<![A-Za-z0-9_])@([^\s,;)]+)")
PROJECT_DIR_DECODE_RE = re.compile(r"^-Users-[^-]+-(.+)$")

SOURCE_TYPES = {
    "claude_md_managed",
    "claude_md_user",
    "claude_md_project",
    "claude_md_import",
    "claude_local",
    "rule",
    "memory_md",
    "memory_topic",
    "agent_memory",
    "agent_memory_topic",
}

DEFAULT_TYPE_BY_SOURCE = {
    "claude_md_managed": "convention",
    "claude_md_user": "convention",
    "claude_md_project": "convention",
    "claude_md_import": "convention",
    "claude_local": "user_preference",
    "rule": "convention",
    "memory_md": "task_learning",
    "memory_topic": "task_learning",
    "agent_memory": "task_learning",
    "agent_memory_topic": "task_learning",
}

# Override priority: anti_pattern > decision > user_preference > default.
_ANTI_PATTERN_RE = re.compile(r"\b(bug|fix|debug|never|always|critical)\b", re.IGNORECASE)
_DECISION_RE = re.compile(r"\b(decision|decided|chose|picked|chosen)\b", re.IGNORECASE)
_PREFERENCE_RE = re.compile(r"\b(prefer|preference|style)\b", re.IGNORECASE)


# ── Data classes ─────────────────────────────────────────────────────────


@dataclass
class Chunk:
    heading: str
    body: str
    content_hash: str


@dataclass
class Source:
    path: Path
    source_type: str
    project_name: str | None = None
    subagent_name: str | None = None


class AuthError(RuntimeError):
    """Raised on 401 to abort the import run immediately."""


# ── Marker I/O ───────────────────────────────────────────────────────────


def read_marker(path: Path) -> dict[str, Any]:
    """Read the import marker, tolerating missing files and corrupted JSON."""
    if not path.exists():
        return {"schema_version": 1, "imports": []}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "imports" not in data:
            log.warning("Marker at %s has unexpected shape, treating as empty", path)
            return {"schema_version": 1, "imports": []}
        return data
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Marker at %s is corrupted (%s), treating as empty", path, e)
        return {"schema_version": 1, "imports": []}


def write_marker(path: Path, marker: dict[str, Any]) -> None:
    """Atomically write the marker file (temp + os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(marker, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


# ── Chunker ──────────────────────────────────────────────────────────────


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_chunk(heading: str, body: str) -> Chunk:
    body = body.strip("\n")
    return Chunk(heading=heading, body=body, content_hash=_sha256(body))


def _mask_fences(text: str) -> str:
    """Replace leading `#` of heading-like lines inside fenced code blocks with
    a space so the heading regex won't split them. Length-preserving so chunk
    offsets stay aligned with the original text.
    """
    out: list[str] = []
    open_marker: str | None = None
    for line in text.splitlines(keepends=True):
        m = FENCE_LINE.match(line)
        if m:
            marker = m.group(1)[:3]
            if open_marker is None:
                open_marker = marker
            elif open_marker == marker:
                open_marker = None
            out.append(line)
        elif open_marker is not None:
            stripped = line.lstrip()
            if stripped.startswith("#"):
                idx = len(line) - len(stripped)
                out.append(line[:idx] + " " + line[idx + 1 :])
            else:
                out.append(line)
        else:
            out.append(line)
    return "".join(out)


def _split_on_pattern(text: str, pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    """Split text into (heading, body) sections at each match of `pattern`.

    Content before the first match becomes one section with the H1 (if any) as
    its heading. Bodies preserve heading lines verbatim.
    """
    matches = list(pattern.finditer(text))
    if not matches:
        h1 = H1_LINE.search(text)
        heading = h1.group(1).strip() if h1 else ""
        return [(heading, text)]

    sections: list[tuple[str, str]] = []
    first = matches[0]
    preamble = text[: first.start()]
    if preamble.strip():
        h1 = H1_LINE.search(preamble)
        heading = h1.group(1).strip() if h1 else ""
        sections.append((heading, preamble))

    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        body_start = m.start()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append((heading, text[body_start:body_end]))
    return sections


def _descend_oversized(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """For each section whose body exceeds MAX_CHARS_PER_CHUNK, re-split at H3."""
    result: list[tuple[str, str]] = []
    for heading, body in sections:
        if len(body) <= MAX_CHARS_PER_CHUNK:
            result.append((heading, body))
            continue
        h3_subs = _split_on_pattern(body, H3_LINE)
        if len(h3_subs) <= 1:
            # No H3s present — emit oversized chunk rather than break paragraphs.
            result.append((heading, body))
        else:
            result.extend(h3_subs)
    return result


def _merge_small_siblings(sections: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Merge adjacent chunks where the *first* sibling's stripped body is under
    MIN_CHARS_PER_CHUNK and the combined size still fits in MAX_CHARS_PER_CHUNK.
    The merged chunk keeps the first sibling's heading.
    """
    if not sections:
        return sections
    merged: list[tuple[str, str]] = []
    buf_heading, buf_body = sections[0]
    for heading, body in sections[1:]:
        if (
            len(buf_body.strip()) < MIN_CHARS_PER_CHUNK
            and len(buf_body) + len(body) <= MAX_CHARS_PER_CHUNK
        ):
            buf_body = buf_body + "\n\n" + body
        else:
            merged.append((buf_heading, buf_body))
            buf_heading, buf_body = heading, body
    merged.append((buf_heading, buf_body))
    return merged


def chunk_markdown(text: str) -> list[Chunk]:
    """Split markdown into Chunks for upload to mem0.

    1. Mask heading-like lines inside fenced code blocks.
    2. Split the masked text at H2.
    3. For sections over MAX_CHARS_PER_CHUNK, re-split at H3.
    4. Merge adjacent sections whose first body is under MIN_CHARS_PER_CHUNK.
    5. Slice bodies from the ORIGINAL text using offsets so user wording is
       preserved exactly.
    """
    masked = _mask_fences(text)
    if len(masked) != len(text):
        log.warning("fence mask changed text length (%d -> %d); falling back to whole-file chunk", len(text), len(masked))
        return [_make_chunk("", text)]

    sections = _split_on_pattern(masked, H2_LINE)
    sections = _descend_oversized(sections)
    sections = _merge_small_siblings(sections)

    result: list[Chunk] = []
    cursor = 0
    for heading, masked_body in sections:
        end = cursor + len(masked_body)
        original_body = text[cursor:end]
        result.append(_make_chunk(heading, original_body))
        cursor = end
    return result


# ── Tagger ───────────────────────────────────────────────────────────────


def _override_type(default: str, search_text: str) -> str:
    if _ANTI_PATTERN_RE.search(search_text):
        return "anti_pattern"
    if _DECISION_RE.search(search_text):
        return "decision"
    if _PREFERENCE_RE.search(search_text):
        return "user_preference"
    return default


def tag_chunk(source: Source, chunk: Chunk) -> dict[str, Any]:
    """Build the metadata dict attached to the chunk's add_memory POST."""
    default = DEFAULT_TYPE_BY_SOURCE.get(source.source_type, "task_learning")
    type_value = _override_type(default, chunk.heading + "\n" + chunk.body)
    return {
        "source_file": str(source.path),
        "source_type": source.source_type,
        "section_heading": chunk.heading,
        "project": source.project_name,
        "subagent": source.subagent_name,
        "content_hash": chunk.content_hash,
        "type": type_value,
    }


# ── @import resolver ─────────────────────────────────────────────────────


def _parse_import_paths(text: str, base: Path) -> list[Path]:
    paths: list[Path] = []
    for m in IMPORT_LINE_RE.finditer(text):
        raw = m.group(1)
        if raw.startswith("~"):
            resolved = Path(os.path.expanduser(raw))
        elif raw.startswith("/"):
            resolved = Path(raw)
        else:
            resolved = (base.parent / raw).resolve()
        paths.append(resolved)
    return paths


def resolve_imports(
    path: Path,
    *,
    depth: int = 0,
    visited: set[Path] | None = None,
) -> list[Path]:
    """Return the transitive @-import closure starting at `path`.

    The starting `path` is NOT included. Cycles, missing targets, and depth
    overflows are logged and skipped (matches Claude Code's loader).
    """
    if visited is None:
        visited = set()
    if depth >= MAX_IMPORT_DEPTH:
        log.warning("import depth limit reached at %s (max=%d)", path, MAX_IMPORT_DEPTH)
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    out: list[Path] = []
    for target in _parse_import_paths(text, path):
        try:
            target_resolved = target.resolve()
        except OSError:
            continue
        if target_resolved in visited:
            log.warning("import cycle: skipping %s (re-entered from %s)", target_resolved, path)
            continue
        if not target_resolved.exists():
            log.warning("missing import target %s referenced from %s", target_resolved, path)
            continue
        visited.add(target_resolved)
        out.append(target_resolved)
        out.extend(resolve_imports(target_resolved, depth=depth + 1, visited=visited))
    return out


# ── Discovery ────────────────────────────────────────────────────────────


def _decode_project_name(encoded: str) -> str:
    """`-Users-alice-mem0-platform` → `mem0-platform`."""
    m = PROJECT_DIR_DECODE_RE.match(encoded)
    if m:
        return m.group(1)
    return encoded.lstrip("-")


def _collect_claude_md_chain(cwd: Path) -> list[Path]:
    """Walk up from cwd collecting CLAUDE.md / .claude/CLAUDE.md at each level."""
    chain: list[Path] = []
    seen: set[Path] = set()
    current = cwd
    while True:
        for candidate in (current / "CLAUDE.md", current / ".claude" / "CLAUDE.md"):
            try:
                if candidate.exists():
                    resolved = candidate.resolve()
                    if resolved not in seen:
                        chain.append(resolved)
                        seen.add(resolved)
            except OSError:
                continue
        parent = current.parent
        if parent == current:
            break
        current = parent
    return chain


def discover(*, home: Path | None = None, cwd: Path | None = None) -> list[Source]:
    """Enumerate every Claude state file we know how to import."""
    home = (home or Path.home()).resolve()
    cwd = (cwd or Path.cwd()).resolve()
    sources: list[Source] = []
    seen_paths: set[Path] = set()

    def add(path: Path, source_type: str, **kw: Any) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in seen_paths or not resolved.exists():
            return
        seen_paths.add(resolved)
        sources.append(Source(path=resolved, source_type=source_type, **kw))

    # User-global CLAUDE.md
    add(home / ".claude" / "CLAUDE.md", "claude_md_user")

    # User-level .claude/rules
    user_rules_dir = home / ".claude" / "rules"
    if user_rules_dir.is_dir():
        for rule in sorted(user_rules_dir.rglob("*.md")):
            add(rule, "rule")

    # Project CLAUDE.md chain (walking up from cwd)
    for path in _collect_claude_md_chain(cwd):
        add(path, "claude_md_project")

    # Project CLAUDE.local.md
    add(cwd / "CLAUDE.local.md", "claude_local")

    # Project-level .claude/rules
    project_rules_dir = cwd / ".claude" / "rules"
    if project_rules_dir.is_dir():
        for rule in sorted(project_rules_dir.rglob("*.md")):
            add(rule, "rule")

    # Per-project auto-memory
    projects_root = home / ".claude" / "projects"
    if projects_root.is_dir():
        for proj_dir in sorted(projects_root.iterdir()):
            mem_dir = proj_dir / "memory"
            if not mem_dir.is_dir():
                continue
            proj_name = _decode_project_name(proj_dir.name)
            for md in sorted(mem_dir.glob("*.md")):
                source_type = "memory_md" if md.name == "MEMORY.md" else "memory_topic"
                add(md, source_type, project_name=proj_name)

    # Subagent auto-memory
    agent_root = home / ".claude" / "agent-memory"
    if agent_root.is_dir():
        for sub_dir in sorted(agent_root.iterdir()):
            if not sub_dir.is_dir():
                continue
            for md in sorted(sub_dir.glob("*.md")):
                source_type = "agent_memory" if md.name == "MEMORY.md" else "agent_memory_topic"
                add(md, source_type, subagent_name=sub_dir.name)

    # Follow @imports from every CLAUDE.md / local / rule found above.
    snapshot = list(sources)
    for s in snapshot:
        if s.source_type in {"claude_md_user", "claude_md_project", "claude_local", "rule"}:
            for imp in resolve_imports(s.path):
                add(imp, "claude_md_import")

    return sources


# ── Dispatcher ───────────────────────────────────────────────────────────


def post_memory(
    *,
    content: str,
    user_id: str,
    metadata: dict[str, Any],
    infer: bool,
    api_key: str,
) -> dict[str, Any] | None:
    """POST one chunk to /v1/memories/. Returns the parsed response or None on
    recoverable failure. Raises AuthError on 401."""
    body = {
        "messages": [{"role": "user", "content": content}],
        "user_id": user_id,
        "metadata": metadata,
        "infer": infer,
    }
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Token {api_key}",
    }

    for attempt in (1, 2):
        req = urllib.request.Request(
            f"{API_URL}/v1/memories/",
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECS) as resp:
                if resp.status in (200, 201):
                    return json.loads(resp.read().decode("utf-8"))
                log.warning("API returned status %d", resp.status)
                return None
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise AuthError("Auth failed — check MEM0_API_KEY") from e
            if e.code == 429 and attempt == 1:
                log.warning("rate limited; sleeping %.1fs and retrying once", RETRY_SLEEP_SECS)
                time.sleep(RETRY_SLEEP_SECS)
                continue
            log.warning("API error %d: %s", e.code, e.reason)
            return None
        except urllib.error.URLError as e:
            log.warning("network error: %s", e)
            return None
    return None


# ── Orchestrator ─────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _hash_set_for_file(marker: dict[str, Any], file_path: str) -> set[str]:
    for entry in marker.get("imports", []):
        if entry.get("file") == file_path:
            return {c["content_hash"] for c in entry.get("chunks", []) if "content_hash" in c}
    return set()


def _get_or_create_file_entry(
    marker: dict[str, Any], file_path: str, source_type: str
) -> dict[str, Any]:
    for entry in marker["imports"]:
        if entry.get("file") == file_path:
            return entry
    entry = {
        "file": file_path,
        "source_type": source_type,
        "imported_at": _now_iso(),
        "chunks": [],
    }
    marker["imports"].append(entry)
    return entry


def run_import(
    *,
    home: Path,
    cwd: Path,
    marker_path: Path,
    user_id: str,
    api_key: str,
    infer: bool,
    dry_run: bool,
    source_filter: str | None,
) -> dict[str, int]:
    """Orchestrate the full import. Returns stats: planned, uploaded, skipped,
    failed, files.
    """
    marker = read_marker(marker_path)
    sources = discover(home=home, cwd=cwd)
    if source_filter:
        sources = [s for s in sources if s.source_type == source_filter]

    stats = {
        "planned": 0,
        "uploaded": 0,
        "skipped": 0,
        "failed": 0,
        "files": len(sources),
    }

    for source in sources:
        try:
            text = source.path.read_text(encoding="utf-8")
        except OSError as e:
            log.warning("cannot read %s: %s", source.path, e)
            continue
        if not text.strip():
            continue
        chunks = chunk_markdown(text)
        already = _hash_set_for_file(marker, str(source.path))

        for chunk in chunks:
            stats["planned"] += 1
            if chunk.content_hash in already:
                stats["skipped"] += 1
                continue
            if dry_run:
                continue
            metadata = tag_chunk(source, chunk)
            try:
                resp = post_memory(
                    content=chunk.body,
                    user_id=user_id,
                    metadata=metadata,
                    infer=infer,
                    api_key=api_key,
                )
            except AuthError:
                log.error("auth failed — aborting import")
                raise
            if resp is None:
                stats["failed"] += 1
                continue
            memory_ids = [item.get("id", "") for item in resp.get("results", [])]
            entry = _get_or_create_file_entry(marker, str(source.path), source.source_type)
            entry["chunks"].append(
                {
                    "heading": chunk.heading,
                    "content_hash": chunk.content_hash,
                    "memory_ids": memory_ids,
                }
            )
            marker["last_run_at"] = _now_iso()
            marker["user_id"] = user_id
            write_marker(marker_path, marker)
            stats["uploaded"] += 1

    return stats


# ── CLI ──────────────────────────────────────────────────────────────────


def _get_home() -> Path:
    return Path.home()


def _get_cwd() -> Path:
    return Path.cwd()


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="import_claude_state.py",
        description="Holistic import of on-disk Claude state into mem0.",
    )
    p.add_argument("--dry-run", action="store_true", help="Print plan, don't upload.")
    p.add_argument("--reset", action="store_true", help="Delete marker before running (forces full re-import).")
    p.add_argument("--no-infer", action="store_true", help="Upload chunks raw (infer=False) instead of letting mem0 extract facts.")
    p.add_argument(
        "--source",
        choices=sorted(SOURCE_TYPES),
        default=None,
        help="Restrict to one source_type.",
    )
    return p


def _print_summary(stats: dict[str, int], *, dry_run: bool) -> None:
    if dry_run:
        print(
            f"[dry-run] Would upload {stats['planned'] - stats['skipped']} chunks "
            f"from {stats['files']} files ({stats['skipped']} already imported, "
            f"planned={stats['planned']})."
        )
        return
    print(
        f"Imported {stats['uploaded']} chunks from {stats['files']} files "
        f"(skipped {stats['skipped']}, failed {stats['failed']})."
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    api_key = os.environ.get("MEM0_API_KEY", "")
    if not api_key:
        print("MEM0_API_KEY not set — see plugin README.", file=sys.stderr)
        return 1

    try:
        from _identity import resolve_user_id  # type: ignore[import-not-found]
    except ImportError:
        def resolve_user_id() -> str:
            return os.environ.get("MEM0_USER_ID") or os.environ.get("USER") or "default"

    user_id = resolve_user_id()

    if args.reset:
        try:
            MARKER_PATH.unlink()
        except FileNotFoundError:
            pass

    try:
        stats = run_import(
            home=_get_home(),
            cwd=_get_cwd(),
            marker_path=MARKER_PATH,
            user_id=user_id,
            api_key=api_key,
            infer=not args.no_infer,
            dry_run=args.dry_run,
            source_filter=args.source,
        )
    except AuthError as e:
        print(str(e), file=sys.stderr)
        return 1

    _print_summary(stats, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
