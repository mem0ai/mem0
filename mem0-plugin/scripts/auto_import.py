#!/usr/bin/env python3
"""Auto-import declarative project files into mem0.

Runs in the background from the SessionStart hook (startup only).
Imports CLAUDE.md, AGENTS.md, .cursorrules, .windsurfrules, mem0.md
into mem0 as project profile memories, skipping unchanged files via
SHA-256 hashing.

Input:  MEM0_CWD env var (optional, defaults to os.getcwd())
Output: stderr logs only (exit 0 always — must not block)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _chunking import filter_and_truncate, split_by_headers
from _identity import resolve_api_key, resolve_user_id
from _project import resolve_branch, resolve_project_id, save_project_mapping

log = logging.getLogger("mem0-auto-import")
log.setLevel(logging.DEBUG)
_handler = logging.StreamHandler(sys.stderr)
_handler.setFormatter(logging.Formatter("[mem0-auto-import] %(message)s"))
log.addHandler(_handler)

if os.environ.get("MEM0_DEBUG"):
    _log_dir = os.path.expanduser("~/.mem0")
    try:
        os.makedirs(_log_dir, exist_ok=True)
        _file_handler = logging.FileHandler(os.path.join(_log_dir, "hooks.log"))
        _file_handler.setFormatter(logging.Formatter("[mem0-auto-import] %(asctime)s %(message)s"))
        log.addHandler(_file_handler)
    except OSError:
        pass

API_URL = "https://api.mem0.ai"
MAX_FILE_SIZE = 100_000  # skip files over 100 KB
TARGET_FILES = ["CLAUDE.md", "AGENTS.md", ".cursorrules", ".windsurfrules", "mem0.md"]
HASH_STORE = os.path.expanduser("~/.mem0/file_hashes.json")
LOCK_FILE = os.path.expanduser("~/.mem0/auto_import.lock")


def _acquire_lock() -> bool:
    """Try to acquire a file lock. Returns False if another instance is running."""
    try:
        os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        return True
    except FileExistsError:
        try:
            mtime = os.path.getmtime(LOCK_FILE)
            import time
            if time.time() - mtime > 120:
                os.unlink(LOCK_FILE)
                return _acquire_lock()
        except OSError:
            pass
        return False


def _release_lock() -> None:
    try:
        os.unlink(LOCK_FILE)
    except OSError:
        pass


def _git_root(cwd: str) -> str:
    """Return the git repo root, or empty string if not in a repo."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def sha256_file(path: str) -> str:
    """Return the hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_hashes() -> dict[str, str]:
    """Load the hash store from disk; return empty dict on any error."""
    if not os.path.isfile(HASH_STORE):
        return {}
    try:
        with open(HASH_STORE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_hashes(hashes: dict[str, str]) -> None:
    """Persist the hash store to disk."""
    mem0_dir = os.path.expanduser("~/.mem0")
    os.makedirs(mem0_dir, exist_ok=True)
    try:
        with open(HASH_STORE, "w") as f:
            json.dump(hashes, f, indent=2)
    except OSError as e:
        log.warning("Could not save hash store: %s", e)


def already_imported(api_key: str, user_id: str, project_id: str, filename: str) -> bool:
    body = json.dumps({
        "query": filename,
        "filters": {
            "AND": [
                {"user_id": user_id},
                {"app_id": project_id},
                {"metadata": {"source": "auto-import"}},
            ]
        },
        "top_k": 10,
        "threshold": 0.0,
    }).encode()
    req = urllib.request.Request(
        f"{API_URL}/v3/memories/search/",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Token {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read())
            results = data if isinstance(data, list) else data.get("results", [])
            for result in results:
                meta = result.get("metadata", {}) if isinstance(result, dict) else {}
                file_field = meta.get("file", "")
                if file_field == filename or file_field.startswith(f"{filename}["):
                    return True
            return False
    except Exception:
        return False


def _delete_stale_chunks(api_key: str, user_id: str, project_id: str, filename: str) -> int:
    """Find and delete existing chunks for a file before re-import. Returns count deleted."""
    body = json.dumps({
        "query": filename,
        "filters": {
            "AND": [
                {"user_id": user_id},
                {"app_id": project_id},
                {"metadata": {"source": "auto-import"}},
            ]
        },
        "top_k": 20,
        "threshold": 0.0,
    }).encode()
    req = urllib.request.Request(
        f"{API_URL}/v3/memories/search/",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Token {api_key}"},
        method="POST",
    )
    ids_to_delete = []
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            results = data if isinstance(data, list) else data.get("results", [])
            for result in results:
                if not isinstance(result, dict):
                    continue
                meta = result.get("metadata", {})
                file_field = meta.get("file", "")
                if file_field == filename or file_field.startswith(f"{filename}["):
                    mid = result.get("id")
                    if mid:
                        ids_to_delete.append(mid)
    except Exception as e:
        log.warning("Failed to search for stale chunks of %s: %s", filename, e)
        return 0

    deleted = 0
    for mid in ids_to_delete:
        try:
            del_req = urllib.request.Request(
                f"{API_URL}/v1/memories/{mid}/",
                headers={"Authorization": f"Token {api_key}"},
                method="DELETE",
            )
            with urllib.request.urlopen(del_req, timeout=10):
                deleted += 1
        except Exception as e:
            log.warning("Failed to delete stale chunk %s: %s", mid, e)

    if deleted:
        log.info("Deleted %d stale chunk(s) for %s before re-import", deleted, filename)
    return deleted


def post_memory(api_key: str, content: str, user_id: str, filename: str, project_id: str, branch: str = "") -> bool:
    """POST a project profile memory to the Mem0 REST API."""
    metadata = {
        "type": "project_profile",
        "file": filename,
        "source": "auto-import",
    }
    if branch:
        metadata["branch"] = branch
    body = {
        "messages": [
            {
                "role": "user",
                "content": f"## Project Profile: {filename}\n\nProject: {project_id}\n\n{content}",
            }
        ],
        "user_id": user_id,
        "app_id": project_id,
        "metadata": metadata,
        "infer": False,
    }

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/v3/memories/add/",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Token {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                log.info("Imported %s (project=%s)", filename, project_id)
                return True
            log.warning("API returned status %d for %s", resp.status, filename)
            return False
    except urllib.error.URLError as e:
        log.warning("API call failed for %s: %s", filename, e)
        return False


def main() -> None:
    api_key = resolve_api_key()
    if not api_key:
        log.debug("MEM0_API_KEY not set, skipping auto-import")
        return

    cwd = os.environ.get("MEM0_CWD", "").strip() or os.getcwd()
    user_id = resolve_user_id()
    project_id = resolve_project_id(cwd)
    branch = resolve_branch(cwd)

    save_project_mapping(cwd, project_id)

    git_root = _git_root(cwd)
    search_dirs = [cwd]
    if git_root and os.path.realpath(git_root) != os.path.realpath(cwd):
        search_dirs.append(git_root)

    log.debug("Auto-import started: cwd=%s git_root=%s project=%s user=%s branch=%s", cwd, git_root or "(none)", project_id, user_id, branch)

    hashes = load_hashes()
    updated = False
    seen_content_hashes: set[str] = set()

    for filename in TARGET_FILES:
        filepath = ""
        for search_dir in search_dirs:
            candidate = os.path.join(search_dir, filename)
            if os.path.isfile(candidate):
                filepath = candidate
                break

        if not filepath:
            log.debug("Not found, skipping: %s", filename)
            continue

        filepath = os.path.realpath(filepath)

        try:
            file_size = os.path.getsize(filepath)
        except OSError:
            log.debug("Cannot stat %s, skipping", filename)
            continue

        if file_size > MAX_FILE_SIZE:
            log.debug("Skipping %s: size %d exceeds %d bytes", filename, file_size, MAX_FILE_SIZE)
            continue

        try:
            current_hash = sha256_file(filepath)
        except OSError as e:
            log.debug("Cannot hash %s: %s", filename, e)
            continue

        if current_hash in seen_content_hashes:
            log.debug("Duplicate content, skipping: %s (same as earlier file)", filename)
            continue
        seen_content_hashes.add(current_hash)

        hash_key = f"{project_id}:{branch}:{filename}" if branch else f"{project_id}:{filename}"
        if hashes.get(hash_key) == current_hash:
            if already_imported(api_key, user_id, project_id, filename):
                log.debug("Unchanged and still in mem0, skipping: %s", filename)
                continue
            log.info("Hash matches but memories missing server-side, re-importing: %s", filename)

        elif already_imported(api_key, user_id, project_id, filename):
            log.debug("Already in mem0, updating hash store: %s", filename)
            hashes[hash_key] = current_hash
            updated = True
            continue

        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except OSError as e:
            log.debug("Cannot read %s: %s", filename, e)
            continue

        _delete_stale_chunks(api_key, user_id, project_id, filename)

        is_markdown = filename.endswith(".md")
        if is_markdown:
            chunks = filter_and_truncate(split_by_headers(content))
        else:
            chunks = filter_and_truncate([content])

        if not chunks:
            chunks = [content[:10000]]

        success = True
        for i, chunk in enumerate(chunks):
            chunk_name = f"{filename}[{i+1}/{len(chunks)}]" if len(chunks) > 1 else filename
            if not post_memory(api_key, chunk, user_id, chunk_name, project_id, branch):
                success = False

        if success:
            hashes[hash_key] = current_hash
            updated = True

    if updated:
        save_hashes(hashes)
    else:
        log.debug("No files imported this run")


if __name__ == "__main__":
    if not _acquire_lock():
        log.debug("Another auto_import instance is running — skipping")
        sys.exit(0)
    try:
        main()
    except Exception as e:
        log.error("Unexpected error: %s", e)
    finally:
        _release_lock()
    sys.exit(0)
