"""Regression test for issue #6013.

The TypeScript OSS Redis vector store must treat empty and all-null filters as
match-all filters. Otherwise RediSearch receives an invalid empty pre-filter
expression before the vector KNN clause.
"""

import json
import os
import shutil
import subprocess
import sys
import textwrap
import types
from pathlib import Path
from unittest.mock import patch

import pytest

class _Posthog:
    pass


class _QdrantClient:
    pass


_posthog = types.ModuleType("posthog")
_posthog.Posthog = _Posthog
_qdrant_client = types.ModuleType("qdrant_client")
_qdrant_client.QdrantClient = _QdrantClient

with (
    patch("importlib.metadata.version", return_value="0.0.0"),
    patch.dict(os.environ, {"MEM0_TELEMETRY": "False"}),
    patch.dict(sys.modules, {"posthog": _posthog, "qdrant_client": _qdrant_client}),
):
    import mem0


def _extract_filter_block(source: str, method_name: str) -> str:
    method_start = source.index(f"  async {method_name}(")
    block_start = source.index(
        "    const snakeFilters = filters ? toSnakeCase(filters) : undefined;",
        method_start,
    )
    next_statement = "    const queryVector" if method_name == "search" else "    const searchOptions"
    block_end = source.index(next_statement, block_start)
    return textwrap.dedent(source[block_start:block_end]).strip()


def test_issue_6013():
    assert mem0.__version__ == "0.0.0"

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is required to execute the TypeScript Redis query-building logic")

    repo_root = Path(__file__).resolve().parents[1]
    redis_source = repo_root / "mem0-ts" / "src" / "oss" / "src" / "vector_stores" / "redis.ts"
    source = redis_source.read_text()

    search_filter_block = _extract_filter_block(source, "search")
    list_filter_block = _extract_filter_block(source, "list")

    script = f"""
    function escapeRedisTagValue(value) {{
      return String(value).replace(
        /([,.<>{{}}\\[\\]"':;!@#$%^&*()\\-+=~|/\\\\\\s])/g,
        "\\\\$1",
      );
    }}

    function toSnakeCase(obj) {{
      if (typeof obj !== "object" || obj === null) return obj;

      return Object.fromEntries(
        Object.entries(obj).map(([key, value]) => [
          key.replace(/[A-Z]/g, (letter) => `_${{letter.toLowerCase()}}`),
          value,
        ]),
      );
    }}

    function buildSearchQuery(filters, topK) {{
      {textwrap.indent(search_filter_block, "      ")}
      return `${{filterExpr}} =>[KNN ${{topK}} @embedding $vec AS __vector_score]`;
    }}

    function buildListQuery(filters) {{
      {textwrap.indent(list_filter_block, "      ")}
      return filterExpr;
    }}

    const allNullFilters = {{ userId: null, agentId: undefined }};

    console.log(JSON.stringify({{
      searchUndefined: buildSearchQuery(undefined, 5),
      searchEmpty: buildSearchQuery({{}}, 5),
      searchAllNull: buildSearchQuery(allNullFilters, 5),
      searchFiltered: buildSearchQuery({{ userId: "alice" }}, 5),
      listUndefined: buildListQuery(undefined),
      listEmpty: buildListQuery({{}}),
      listAllNull: buildListQuery(allNullFilters),
      listFiltered: buildListQuery({{ userId: "alice" }}),
    }}));
    """

    result = subprocess.run(
        [node, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    queries = json.loads(result.stdout)

    assert queries == {
        "searchUndefined": "* =>[KNN 5 @embedding $vec AS __vector_score]",
        "searchEmpty": "* =>[KNN 5 @embedding $vec AS __vector_score]",
        "searchAllNull": "* =>[KNN 5 @embedding $vec AS __vector_score]",
        "searchFiltered": "@user_id:{alice} =>[KNN 5 @embedding $vec AS __vector_score]",
        "listUndefined": "*",
        "listEmpty": "*",
        "listAllNull": "*",
        "listFiltered": "@user_id:{alice}",
    }
