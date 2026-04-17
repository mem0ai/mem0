#!/usr/bin/env python3
"""Check docs/llms.txt coverage against docs/**/*.mdx.

Two-way diff:
  - pages present in docs/ but not linked in docs/llms.txt  -> "missing"
  - URLs linked in docs/llms.txt that point to no page      -> "stale"

Modes:
  default   read-only; exits 1 if any drift is found.
  --write   appends placeholder entries for missing pages under a
            "## Unclassified - needs triage" H2 at the end of
            docs/llms.txt. Stale URLs are reported but never removed
            automatically (human decides whether a page was renamed
            or genuinely deleted). Exits 1 if anything was written,
            0 if the file was already in sync.

Exit codes:
  0  in sync, or --write mode completed (workflow continues to open a PR)
  1  read-only drift detected

The script has no third-party dependencies; stdlib only.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"
LLMS_TXT = DOCS_DIR / "llms.txt"
IGNORE_FILE = REPO_ROOT / "scripts" / "llms-txt-ignore.txt"

BASE_URL = "https://docs.mem0.ai/"
TRIAGE_HEADER = "## Unclassified - needs triage"
URL_RE = re.compile(r"\(https://docs\.mem0\.ai/([^)\s#]*)")


def load_ignore_prefixes() -> list[str]:
    if not IGNORE_FILE.exists():
        return []
    prefixes: list[str] = []
    for raw in IGNORE_FILE.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            prefixes.append(line)
    return prefixes


def canonical_repo_pages(ignore_prefixes: list[str]) -> tuple[set[str], set[str]]:
    all_pages: set[str] = set()
    included_pages: set[str] = set()
    for path in DOCS_DIR.rglob("*.mdx"):
        rel = path.relative_to(DOCS_DIR).with_suffix("").as_posix()
        all_pages.add(rel)
        if not any(rel.startswith(p) for p in ignore_prefixes):
            included_pages.add(rel)
    return all_pages, included_pages


def indexed_urls(text: str) -> set[str]:
    urls: set[str] = set()
    for match in URL_RE.finditer(text):
        path = match.group(1).rstrip("/")
        if path:
            urls.add(path)
    return urls


def format_placeholder(page: str) -> str:
    title = page.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ").title()
    return (
        f"- [{title}]({BASE_URL}{page}) [TODO: Platform|OSS|Both]: "
        "TODO - rewrite as 'Use when ...' and move into the correct section."
    )


def append_triage_block(text: str, missing_pages: list[str]) -> str:
    entries = "\n".join(format_placeholder(p) for p in missing_pages)
    if TRIAGE_HEADER in text:
        return text.rstrip() + "\n" + entries + "\n"
    preamble = (
        "> New docs pages were detected by CI. For each entry below: replace "
        "the scope tag with `[Platform]`, `[OSS]`, or `[Both]`; rewrite the "
        "description as `Use when ...`; move it into the correct section; "
        "then delete this H2 once empty.\n"
    )
    return text.rstrip() + "\n\n" + TRIAGE_HEADER + "\n\n" + preamble + "\n" + entries + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="scaffold placeholder entries in docs/llms.txt for missing pages",
    )
    args = parser.parse_args()

    if not LLMS_TXT.exists():
        print(f"ERROR: {LLMS_TXT} not found.", file=sys.stderr)
        return 1

    ignore_prefixes = load_ignore_prefixes()
    all_pages, included_pages = canonical_repo_pages(ignore_prefixes)
    text = LLMS_TXT.read_text()
    linked = indexed_urls(text)

    missing = sorted(included_pages - linked)
    stale = sorted(linked - all_pages)

    if missing:
        print(f"Pages missing from docs/llms.txt ({len(missing)}):")
        for p in missing:
            print(f"  + {p}")
    if stale:
        print(f"\nURLs in docs/llms.txt with no matching .mdx page ({len(stale)}):")
        for p in stale:
            print(f"  - {p}")
        print(
            "\n(Stale URLs are never auto-removed: check whether the page was "
            "renamed, and update the link by hand.)"
        )

    if not missing and not stale:
        print("docs/llms.txt is in sync with docs/**/*.mdx.")
        return 0

    if args.write:
        if missing:
            new_text = append_triage_block(text, missing)
            LLMS_TXT.write_text(new_text)
            print(
                f"\nAppended {len(missing)} placeholder entries under "
                f"'{TRIAGE_HEADER}' in docs/llms.txt."
            )
        else:
            print("\nNo additions to scaffold; stale URLs surfaced above require manual cleanup.")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
