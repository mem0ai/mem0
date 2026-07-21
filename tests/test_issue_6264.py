"""Regression test for TS OSS default memory vector-store range filters."""

import json
import re
import shutil
import subprocess
import textwrap
import types
from pathlib import Path
from unittest.mock import patch

import pytest

posthog = types.ModuleType("posthog")
posthog.Posthog = type(
    "Posthog",
    (),
    {
        "__init__": lambda self, *args, **kwargs: None,
        "capture": lambda self, *args, **kwargs: None,
        "shutdown": lambda self: None,
    },
)
qdrant_client = types.ModuleType("qdrant_client")
qdrant_client.QdrantClient = type("QdrantClient", (), {})

with patch.dict("sys.modules", {"posthog": posthog, "qdrant_client": qdrant_client}):
    with patch("importlib.metadata.version", return_value="0.0.0"):
        from mem0 import Memory  # noqa: F401


def _extract_method_body(source, method_name):
    match = re.search(rf"private {method_name}\([^)]*\): [^{{]+{{", source)
    assert match, f"{method_name} method not found"

    start = match.end()
    depth = 1
    index = start
    while index < len(source) and depth:
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
        index += 1

    assert depth == 0, f"{method_name} method body is incomplete"
    return source[start : index - 1]


def test_issue_6264(tmp_path):
    """The TS in-memory store must AND multiple operators on one field."""
    if shutil.which("node") is None:
        pytest.skip("node is not installed")

    repo_root = Path(__file__).resolve().parents[1]
    memory_store = repo_root / "mem0-ts" / "src" / "oss" / "src" / "vector_stores" / "memory.ts"
    method_body = _extract_method_body(memory_store.read_text(encoding="utf-8"), "matchFieldCondition")

    script = tmp_path / "issue_6264.js"
    script.write_text(
        textwrap.dedent(
            f"""
            function matchFieldCondition(payload, key, value) {{{method_body}
            }}

            const records = [
              {{ id: "age-5", payload: {{ user_id: "u1", age: 5 }} }},
              {{ id: "age-15", payload: {{ user_id: "u1", age: 15 }} }},
              {{ id: "age-25", payload: {{ user_id: "u1", age: 25 }} }},
            ];
            const filters = {{ user_id: "u1", age: {{ gte: 10, lte: 20 }} }};

            const ids = records
              .filter((record) => Object.entries(filters).every(([key, value]) => (
                matchFieldCondition(record.payload, key, value)
              )))
              .map((record) => record.id)
              .sort();

            console.log(JSON.stringify(ids));
            """
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        ["node", str(script)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["age-15"]
