#!/usr/bin/env python3
"""Verify that a built TypeScript plugin is self-contained and publishable."""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from typing import Any


CORE_ROOT = Path(__file__).resolve().parents[1]
INTEGRATIONS_ROOT = CORE_ROOT.parent
TYPESCRIPT_ARTIFACTS = {
    "openclaw": (INTEGRATIONS_ROOT / "openclaw", ("dist/index.js", "dist/index.d.ts")),
    "opencode": (INTEGRATIONS_ROOT / "opencode-plugin", ("dist/index.js", "index.d.ts")),
    "pi-agent": (
        INTEGRATIONS_ROOT / "pi-agent-plugin",
        ("dist/index.js", "dist/index.d.ts", "dist/entry.js", "dist/entry.d.ts"),
    ),
    "deepseek": (INTEGRATIONS_ROOT / "deepseek-plugin", ("dist/index.js", "dist/index.d.ts")),
}
MONOREPO_IMPORT = re.compile(
    r"(?:from\s+|import\s*\(|require\s*\()\s*['\"][^'\"]*agent-plugin-core"
)


def verify_artifact(group: str, package: Path, required: tuple[str, ...]) -> dict[str, Any]:
    started = time.monotonic()
    errors = [f"missing package artifact: {name}" for name in required if not (package / name).is_file()]
    dist = package / "dist"
    for pattern in ("*.js", "*.mjs", "*.cjs", "*.d.ts"):
        for artifact in dist.rglob(pattern) if dist.is_dir() else ():
            if MONOREPO_IMPORT.search(artifact.read_text(encoding="utf-8")):
                errors.append(f"monorepo source import in package artifact: {artifact.relative_to(package)}")
    return {
        "name": f"{group}-artifact",
        "group": group,
        "status": "failed" if errors else "passed",
        "duration_seconds": round(time.monotonic() - started, 3),
        **({"output": "\n".join(errors)} if errors else {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=tuple(TYPESCRIPT_ARTIFACTS))
    args = parser.parse_args()
    package, required = TYPESCRIPT_ARTIFACTS[args.group]
    result = verify_artifact(args.group, package, required)
    if result.get("output"):
        print(result["output"])
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
