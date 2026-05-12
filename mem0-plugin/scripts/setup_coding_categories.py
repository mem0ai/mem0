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
  python setup_coding_categories.py --apply    # actually call project.update()

Requires the mem0ai Python SDK and MEM0_API_KEY to be set.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

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
        help="Actually call project.update(). Without this flag, runs in dry-run mode.",
    )
    args = ap.parse_args()

    if not os.environ.get("MEM0_API_KEY"):
        print("ERROR: MEM0_API_KEY is not set. Export it and try again.", file=sys.stderr)
        return 1

    try:
        from mem0 import MemoryClient
    except ImportError:
        print(
            "ERROR: the mem0ai Python SDK is not installed.\n"
            "Install with: pip install mem0ai\n"
            "Then re-run this script.",
            file=sys.stderr,
        )
        return 1

    try:
        client = MemoryClient()
    except Exception as e:
        print(
            f"ERROR initialising MemoryClient: {e}\n"
            "Most commonly this is an invalid MEM0_API_KEY -- check the key at "
            "https://app.mem0.ai/dashboard/api-keys",
            file=sys.stderr,
        )
        return 1

    try:
        current = client.project.get(fields=["custom_categories"])
        current_cats = current.get("custom_categories") if isinstance(current, dict) else None
    except Exception as e:
        print(f"ERROR fetching current categories: {e}", file=sys.stderr)
        return 1

    _print_categories("Current project categories", current_cats)
    _print_categories("Proposed coding categories", CODING_CATEGORIES)

    if not args.apply:
        print("Dry-run only -- no changes made. Re-run with --apply to write.")
        return 0

    print("Applying coding categories...")
    try:
        response = client.project.update(custom_categories=CODING_CATEGORIES)
    except Exception as e:
        print(f"ERROR applying update: {e}", file=sys.stderr)
        return 1

    print("Done.", response if response else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
