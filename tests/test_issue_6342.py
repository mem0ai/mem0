"""Regression test for TypeScript OSS update() tenant scope metadata.

Issue #6342: caller metadata passed to memory.update() must not be able to
overwrite the stored user_id, agent_id, or run_id values. Those fields define
the tenant scope used by getAll(), search(), and deleteAll().
"""

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

with (
    patch("importlib.metadata.version", return_value="0.0.0"),
    patch.dict("sys.modules", {"posthog": MagicMock(), "qdrant_client": MagicMock()}),
):
    from mem0 import Memory


def test_issue_6342():
    """updateMemory() must re-pin tenant identity after caller metadata."""
    assert Memory is not None

    source = Path("mem0-ts/src/oss/src/memory/index.ts").read_text()
    match = re.search(r"const newMetadata = \{(?P<body>.*?)\n\s*\};", source, re.DOTALL)

    assert match is not None

    body = match.group("body")
    metadata_spread_index = body.index("...metadata")

    for identity_key in ("user_id", "agent_id", "run_id"):
        repin = f"{identity_key}: existingMemory.payload.{identity_key}"

        assert repin in body
        assert body.index(repin) > metadata_spread_index
