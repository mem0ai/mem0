#!/usr/bin/env python3
"""Boundary check: enforce that mem0 calls go through ScopedMemoryClient.

Pre-commit hook that fails the commit if any of these files contain a
direct call to ``memory_client.<method>`` (for the methods that need user_id
isolation). Every such call must instead go through
``app.utils.scoped_client.ScopedMemoryClient``.

See README_Local.md §"Backend hardening" for the rationale.

Usage::

    python scripts/check_scoped_client_boundary.py

Exits 0 on success, 1 on violation.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

GUARDED_FILES = [
    "openmemory/api/app/mcp_server.py",
    "openmemory/api/app/routers/memories.py",
]

# Match e.g.  memory_client.add(  ,  memory_client.search( ,
# memory_client.vector_store... , memory_client.embedding_model... .
# Any direct attribute access on `memory_client` is a violation in the
# guarded files — the wrapper is the only sanctioned interface.
PATTERN = re.compile(
    r"\bmemory_client\.(add|search|get_all|delete|vector_store|embedding_model)\b"
)


def check(file_path: Path) -> list[tuple[int, str]]:
    if not file_path.exists():
        return []
    violations: list[tuple[int, str]] = []
    for lineno, line in enumerate(file_path.read_text(encoding="utf-8").splitlines(), 1):
        # Allow this hook itself and the wrapper module.
        if PATTERN.search(line):
            violations.append((lineno, line.rstrip()))
    return violations


def main() -> int:
    failed = False
    for rel in GUARDED_FILES:
        path = REPO_ROOT / rel
        violations = check(path)
        if violations:
            failed = True
            print(f"\n[boundary] {rel} contains direct memory_client calls:")
            for lineno, line in violations:
                print(f"  {rel}:{lineno}: {line}")
    if failed:
        print()
        print(
            "Every memory operation in these files must go through "
            "app.utils.scoped_client.ScopedMemoryClient."
        )
        print("See README_Local.md §'Backend hardening' for context.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
