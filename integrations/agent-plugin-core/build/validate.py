#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from skills_ref import validate as validate_skill

SCHEMAS = Path(__file__).resolve().parent / "schemas"


def _schema_errors(path: Path, schema_name: str) -> list[str]:
    if not path.is_file():
        return [f"{path.name}: file is required"]

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{path.name}: {error}"]

    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    errors = Draft202012Validator(schema).iter_errors(value)
    return [
        f"{path.name}{''.join(f'.{part}' for part in error.absolute_path)}: {error.message}"
        for error in sorted(errors, key=lambda item: tuple(str(part) for part in item.absolute_path))
    ]


def validate_bundle(root: Path, kind: str) -> list[str]:
    errors: list[str] = []
    if not root.is_dir():
        return [f"{root}: directory is required"]

    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            errors.append(f"{path.relative_to(root)}: symlinks are not allowed in release bundles")

    if kind == "portable":
        errors.extend(_schema_errors(root / "plugin.json", "plugin.schema.json"))
        if (root / "mcp.json").exists():
            errors.extend(_schema_errors(root / "mcp.json", "mcp.schema.json"))
        skills = root / "skills"
        if skills.is_dir():
            for skill in sorted(path for path in skills.iterdir() if path.is_dir()):
                errors.extend(f"skills/{skill.name}: {error}" for error in validate_skill(skill))
    elif kind == "native":
        for path in sorted(root.rglob("*.json")):
            relative = path.relative_to(root)
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                errors.append(f"{relative}: {error}")
    return sorted(errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a generated Mem0 plugin bundle")
    parser.add_argument("root", type=Path)
    parser.add_argument("--kind", choices=("portable", "native"), required=True)
    args = parser.parse_args()

    errors = validate_bundle(args.root, args.kind)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"Validated {args.kind} bundle: {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
