#!/usr/bin/env python3
"""Run the shared handoff engine locally or from its verified immutable cache."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.request import urlopen

ENGINE_FILES = {"handoff_engine.py", "handoff_sources.py"}
SOURCE_URL = "https://raw.githubusercontent.com/mem0ai/mem0"


def _verified(path: Path, digest: str) -> bool:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() == digest
    except FileNotFoundError:
        return False


def runtime_root(launcher_dir: Path | None = None) -> Path:
    here = launcher_dir or Path(__file__).resolve().parent
    if all((here / name).is_file() for name in ENGINE_FILES):
        return here  # The canonical development checkout already has both engines.
    manifest = json.loads((here / "handoff-runtime.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("invalid handoff runtime manifest")
    revision, files = manifest.get("revision"), manifest.get("files")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("handoff runtime revision must be an immutable commit SHA")
    if (
        not isinstance(files, dict)
        or set(files) != ENGINE_FILES
        or any(not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) for digest in files.values())
    ):
        raise ValueError("invalid handoff runtime file hashes")
    cache = Path.home() / ".mem0" / "handoff-runtime" / revision
    missing = {name: digest for name, digest in files.items() if not _verified(cache / name, digest)}
    if not missing:
        return cache
    cache.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix=f".{revision}-", dir=cache.parent) as temporary:
        staged = Path(temporary)
        for name, digest in missing.items():
            url = f"{SOURCE_URL}/{revision}/integrations/agent-plugin-core/python/{name}"
            try:
                with urlopen(url, timeout=30) as response:
                    body = response.read()
            except OSError as exc:
                raise OSError(f"could not download pinned handoff runtime {name}: {exc}") from exc
            if hashlib.sha256(body).hexdigest() != digest:
                raise ValueError(f"SHA256 mismatch for pinned handoff runtime {name}; refusing to execute it")
            (staged / name).write_bytes(body)
        # All downloads are verified before publishing; each replacement is atomic.
        cache.mkdir(exist_ok=True, mode=0o700)
        for name in missing:
            os.replace(staged / name, cache / name)
    if not all(_verified(cache / name, digest) for name, digest in files.items()):
        raise ValueError("handoff runtime cache changed during installation; refusing to execute it")
    return cache


def main(argv: list[str] | None = None) -> int:
    try:
        root = runtime_root()
    except (OSError, ValueError) as exc:
        print(f"handoff runtime unavailable: {exc}", file=sys.stderr)
        return 1
    sys.path.insert(0, str(root))
    from handoff_engine import main as engine_main

    return engine_main(argv, default_source=None)


if __name__ == "__main__":
    raise SystemExit(main())
