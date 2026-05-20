#!/usr/bin/env python3
"""Replace mem0's default category taxonomy with one tuned for coding workflows.

mem0 auto-tags every memory with one or more `categories`. By default the list
is consumer-oriented (food, hobbies, music, ...), which is meaningless for code.
This script replaces the project's category list with a coding-focused one.

The change is project-level (per the platform docs, per-request overrides are
not supported on the managed API). Run once per project; future memories will
be tagged using the new list automatically.

Usage:
  python setup_coding_categories.py            # dry-run: show current vs proposed, no changes
  python setup_coding_categories.py --apply    # actually update the project

Requires MEM0_API_KEY to be set. No external dependencies (stdlib only).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.mem0.ai"

CODING_CATEGORIES = [
    {
        "architecture_decisions": (
            "Design choices, system structure, technology selection, trade-offs evaluated, "
            "and architectural patterns adopted in the project."
        )
    },
    {
        "anti_patterns": (
            "Approaches that failed, debugging dead-ends, common mistakes to avoid, "
            "and lessons learned from things that didn't work."
        )
    },
    {
        "task_learnings": (
            "Strategies and approaches that succeeded for specific tasks, including tooling "
            "tricks, workflow shortcuts, and effective problem-solving patterns."
        )
    },
    {
        "tooling_setup": (
            "Development environment, build tools, dependencies, package managers, deploy "
            "pipelines, and configuration steps for the project."
        )
    },
    {
        "bug_fixes": (
            "Specific bug fixes with root cause analysis, the fix applied, and how the bug "
            "was diagnosed -- useful for recognising similar issues later."
        )
    },
    {
        "coding_conventions": (
            "Code style, naming patterns, file organisation, error-handling conventions, "
            "and team agreements about how code is written in this project."
        )
    },
    {
        "user_preferences": (
            "User's stated preferences for tools, libraries, languages, formatting, "
            "and ways of working."
        )
    },
]


def _api_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }


def _resolve_org_project(api_key: str) -> tuple[str, str]:
    """Call GET /v1/ping/ to resolve org_id and project_id from API key."""
    req = urllib.request.Request(
        f"{API_BASE}/v1/ping/",
        headers=_api_headers(api_key),
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            org_id = data.get("org_id", "")
            project_id = data.get("project_id", "")
            if not org_id or not project_id:
                print("ERROR: API key did not return org_id/project_id.", file=sys.stderr)
                sys.exit(1)
            return org_id, project_id
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace") if e.fp else ""
        print(f"ERROR: ping failed (HTTP {e.code}): {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"ERROR: cannot reach API: {e}", file=sys.stderr)
        sys.exit(1)


def _get_project(api_key: str, org_id: str, project_id: str) -> dict:
    """GET project details including custom_categories."""
    url = f"{API_BASE}/api/v1/orgs/organizations/{org_id}/projects/{project_id}/"
    req = urllib.request.Request(url, headers=_api_headers(api_key), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace") if e.fp else ""
        print(f"ERROR: get project failed (HTTP {e.code}): {body}", file=sys.stderr)
        sys.exit(1)


def _update_project(api_key: str, org_id: str, project_id: str, categories: list) -> dict:
    """PATCH project to set custom_categories."""
    url = f"{API_BASE}/api/v1/orgs/organizations/{org_id}/projects/{project_id}/"
    payload = json.dumps({"custom_categories": categories}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=_api_headers(api_key), method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace") if e.fp else ""
        print(f"ERROR: update project failed (HTTP {e.code}): {body}", file=sys.stderr)
        sys.exit(1)


def _print_categories(label: str, cats):
    print(f"=== {label} ===")
    if cats:
        print(json.dumps(cats, indent=2))
    else:
        print("(none / using mem0 defaults)")
    print()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually update the project. Without this flag, runs in dry-run mode.",
    )
    args = ap.parse_args()

    api_key = os.environ.get("MEM0_API_KEY", "")
    if not api_key:
        print("ERROR: MEM0_API_KEY is not set. Export it and try again.", file=sys.stderr)
        return 1

    print("Resolving org/project from API key...")
    org_id, project_id = _resolve_org_project(api_key)
    print(f"org={org_id} project={project_id}\n")

    project = _get_project(api_key, org_id, project_id)
    current_cats = project.get("custom_categories") if isinstance(project, dict) else None

    _print_categories("Current project categories", current_cats)
    _print_categories("Proposed coding categories", CODING_CATEGORIES)

    if not args.apply:
        print("Dry-run only -- no changes made. Re-run with --apply to write.")
        return 0

    print("Applying coding categories...")
    response = _update_project(api_key, org_id, project_id, CODING_CATEGORIES)
    print("Done.", response if response else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
