#!/usr/bin/env python3
"""Replace mem0's default category taxonomy with one tuned for coding workflows.

mem0 auto-tags every memory with one or more `categories`. By default the list
is consumer-oriented (food, hobbies, music, ...), which is meaningless for code.
This script replaces the project's category list with a coding-focused one.

Uses the mem0ai SDK (client.project.update). The SDK is installed into a
persistent venv at ${CLAUDE_PLUGIN_DATA}/venv by the ensure_deps.sh hook.

Usage:
  python setup_coding_categories.py            # dry-run: show current vs proposed
  python setup_coding_categories.py --apply    # actually call project.update()

Requires MEM0_API_KEY (or CLAUDE_PLUGIN_OPTION_MEM0_API_KEY).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _script_dir)
from _identity import resolve_api_key  # noqa: E402

_plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", os.path.join(_script_dir, ".."))
_data_dir = os.environ.get("CLAUDE_PLUGIN_DATA", os.path.join(os.path.expanduser("~"), ".mem0", "plugin-data"))
_venv_site = os.path.join(_data_dir, "venv", "lib")
if os.path.isdir(_venv_site):
    for d in sorted(os.listdir(_venv_site)):
        sp = os.path.join(_venv_site, d, "site-packages")
        if os.path.isdir(sp) and sp not in sys.path:
            sys.path.insert(1, sp)

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
    {
        "dependency_decisions": (
            "Why specific libraries, frameworks, or package versions were chosen or replaced, "
            "including the alternatives considered and the reasoning behind the selection."
        )
    },
    {
        "performance_findings": (
            "Profiling results, bottlenecks identified, optimisations applied, and measurable "
            "improvements achieved -- useful for avoiding regressions and guiding future work."
        )
    },
    {
        "security_constraints": (
            "Security requirements, authentication and authorisation rules, data-handling "
            "constraints, compliance obligations, and known threat mitigations in effect."
        )
    },
    {
        "testing_patterns": (
            "Test strategies, frameworks chosen, coverage targets, fixture patterns, mocking "
            "approaches, and how the test suite is structured for this project."
        )
    },
    {
        "data_model": (
            "Schema definitions, database column semantics, domain object relationships, "
            "field constraints, and how data flows between storage and application layers."
        )
    },
    {
        "api_contracts": (
            "API endpoint shapes, request and response schemas, authentication requirements, "
            "versioning policy, and any breaking-change commitments or deprecation timelines."
        )
    },
    {
        "deployment_runbook": (
            "How to build, release, deploy, and roll back the project. CI/CD pipeline steps, "
            "environment-specific configuration, and on-call runbook entries."
        )
    },
    {
        "team_norms": (
            "Team working agreements, PR review etiquette, branching strategy, on-call "
            "rotation, and other social or process conventions the team has agreed on."
        )
    },
    {
        "domain_glossary": (
            "Domain-specific terms, abbreviations, and acronyms with their precise meanings "
            "in this project -- prevents misunderstandings across code, docs, and discussion."
        )
    },
    {
        "experiment_results": (
            "Results from A/B tests, feature-flag experiments, spikes, or proof-of-concept "
            "work -- what was tried, what was measured, and what conclusion was reached."
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

    api_key = resolve_api_key()
    if not api_key:
        print("ERROR: MEM0_API_KEY is not set. Export it or configure it via plugin userConfig.", file=sys.stderr)
        return 1
    os.environ["MEM0_API_KEY"] = api_key

    try:
        from mem0 import MemoryClient
    except ImportError:
        print(
            "ERROR: mem0ai SDK not found. The plugin's ensure_deps.sh hook should\n"
            "install it automatically on session start. Try restarting Claude Code,\n"
            "or run manually:  pip install mem0ai",
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
