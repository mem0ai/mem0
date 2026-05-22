#!/usr/bin/env python3
"""Pre-commit memory capture.

Captures a summary of staged changes as a mem0 memory before each commit.
Runs as a background fire-and-forget call — never blocks the commit.

Usage:
  git diff --cached --stat | python3 on_pre_commit.py
  # or with full diff:
  git diff --cached | python3 on_pre_commit.py --full

Env vars required: MEM0_API_KEY (or CLAUDE_PLUGIN_OPTION_MEM0_API_KEY)
Env vars optional: MEM0_RESOLVED_USER_ID, MEM0_PROJECT_ID, MEM0_BRANCH
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from _identity import resolve_api_key, resolve_user_id

try:
    from _project import resolve_branch, resolve_project_id
except ImportError:
    def resolve_project_id() -> str:
        return os.path.basename(os.getcwd())

    def resolve_branch() -> str:
        return "unknown"


def get_commit_message() -> str:
    """Read the current commit message from COMMIT_EDITMSG (pre-commit context).

    Falls back to HEAD's message if COMMIT_EDITMSG doesn't exist yet
    (e.g., when invoked outside the git hook context).
    """
    try:
        git_dir = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, timeout=5,
        )
        if git_dir.returncode == 0:
            editmsg = os.path.join(git_dir.stdout.strip(), "COMMIT_EDITMSG")
            if os.path.isfile(editmsg):
                with open(editmsg) as f:
                    first_line = f.readline().strip()
                    if first_line and not first_line.startswith("#"):
                        return first_line
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def get_staged_summary() -> str:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def main() -> int:
    api_key = resolve_api_key()
    if not api_key:
        return 0

    diff_input = sys.stdin.read().strip() if not sys.stdin.isatty() else ""
    staged = diff_input or get_staged_summary()
    if not staged or len(staged) < 10:
        return 0

    user_id = os.environ.get("MEM0_RESOLVED_USER_ID") or resolve_user_id()
    project_id = os.environ.get("MEM0_PROJECT_ID") or resolve_project_id()
    branch = os.environ.get("MEM0_BRANCH") or resolve_branch()
    commit_msg = get_commit_message()

    lines = staged.splitlines()
    if len(lines) > 30:
        staged = "\n".join(lines[:30]) + f"\n... ({len(lines) - 30} more lines)"

    content = f"## Commit Context\n\nBranch: {branch}\n"
    if commit_msg:
        content += f"Message: {commit_msg}\n"
    content += f"\n### Staged Changes\n```\n{staged}\n```"

    body = json.dumps({
        "messages": [{"role": "user", "content": content}],
        "user_id": user_id,
        "app_id": project_id,
        "metadata": {
            "type": "commit_context",
            "branch": branch,
            "source": "pre-commit",
        },
        "infer": False,
    }).encode()

    req = urllib.request.Request(
        "https://api.mem0.ai/v3/memories/add/",
        data=body,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10):
            pass
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
