"""Resolve mem0 project_id and branch.

Resolution priority (project_id):
  1. MEM0_PROJECT_ID env var (explicit override)
  2. ~/.mem0/project_map.json lookup by cwd
  3. Git remote slug: strip protocol/prefix, strip .git, replace / and : with -
     e.g. git@github.com:mem0ai/mem0.git -> mem0ai-mem0
  4. Fallback: basename of cwd
"""

from __future__ import annotations

import json
import os
import re
import subprocess


def resolve_project_id(cwd: str | None = None) -> str:
    if cwd is None:
        cwd = os.getcwd()

    # 1. Explicit override
    explicit = os.environ.get("MEM0_PROJECT_ID", "").strip()
    if explicit:
        return explicit

    # 2. project_map.json lookup
    map_path = os.path.expanduser("~/.mem0/project_map.json")
    if os.path.isfile(map_path):
        try:
            with open(map_path) as f:
                project_map = json.load(f)
            mapped = project_map.get(cwd, "").strip()
            if mapped:
                return mapped
        except (OSError, json.JSONDecodeError, AttributeError):
            pass

    # 3. Git remote slug
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        remote_url = result.stdout.strip()
        if remote_url:
            slug = _remote_url_to_slug(remote_url)
            if slug:
                return slug
    except (subprocess.CalledProcessError, OSError):
        pass

    # 4. Fallback: basename of cwd
    return os.path.basename(cwd) or "unknown"


def resolve_branch(cwd: str | None = None) -> str:
    if cwd is None:
        cwd = os.getcwd()
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
            cwd=cwd,
        )
        branch = result.stdout.strip()
        return branch if branch else "unknown"
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def save_project_mapping(cwd: str, project_id: str) -> None:
    """Write cwd -> project_id into ~/.mem0/project_map.json."""
    mem0_dir = os.path.expanduser("~/.mem0")
    os.makedirs(mem0_dir, exist_ok=True)
    map_path = os.path.join(mem0_dir, "project_map.json")
    project_map: dict[str, str] = {}
    if os.path.isfile(map_path):
        try:
            with open(map_path) as f:
                project_map = json.load(f)
        except (OSError, json.JSONDecodeError):
            project_map = {}
    project_map[cwd] = project_id
    with open(map_path, "w") as f:
        json.dump(project_map, f, indent=2)


def _remote_url_to_slug(url: str) -> str:
    """Convert a git remote URL to a deterministic slug.

    Handles:
      - HTTPS:  https://github.com/owner/repo.git
      - SSH:    git@github.com:owner/repo.git
      - SSH:    git@github.com-alias:owner/repo.git  (custom host aliases)
      - ssh://: ssh://git@github.com/owner/repo.git
      - git://: git://github.com/owner/repo.git
    """
    slug = url.strip()
    # Strip .git suffix
    if slug.endswith(".git"):
        slug = slug[:-4]
    # Strip protocol prefixes
    for prefix in ("https://", "http://", "ssh://", "git://"):
        if slug.startswith(prefix):
            slug = slug[len(prefix):]
            break
    else:
        # Handle git@ style (no protocol prefix matched)
        slug = re.sub(r"^git@", "", slug)
    # Replace the first colon (SSH host:path separator) with /
    slug = slug.replace(":", "/", 1)
    # Split on / and take last two components (owner, repo)
    parts = [p for p in slug.split("/") if p]
    if len(parts) >= 2:
        owner, repo = parts[-2], parts[-1]
        slug = f"{owner}-{repo}"
    elif parts:
        slug = parts[-1]
    else:
        return ""
    # Replace any remaining / and : with -
    slug = slug.replace("/", "-").replace(":", "-")
    return slug
