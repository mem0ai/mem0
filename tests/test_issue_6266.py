"""Regression test for TS OSS Valkey entity id payload shape.

Valkey must return snake_case entity ids in vector-store payloads so the
TypeScript OSS Memory layer can promote them to top-level result fields instead
of leaking camelCase ids into metadata.
"""

import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.modules.setdefault("posthog", MagicMock(Posthog=MagicMock))
sys.modules.setdefault("qdrant_client", MagicMock(QdrantClient=MagicMock))

with patch("importlib.metadata.version", return_value="0.0.0"):
    from mem0 import Memory


def _to_camel_case(payload):
    return {
        re.sub(r"_([a-z])", lambda match: match.group(1).upper(), key): value
        for key, value in payload.items()
    }


def _valkey_payload_from_source(repo_root, doc):
    """Model ValkeyDB.docToResult using the payload transform in valkey.ts."""
    source = (repo_root / "mem0-ts/src/oss/src/vector_stores/valkey.ts").read_text()

    payload = {
        "hash": doc["hash"],
        "data": doc["memory"],
        "created_at": "2024-01-01T00:00:00.000Z",
        "user_id": doc["user_id"],
        "agent_id": doc["agent_id"],
        "run_id": doc["run_id"],
        "topic": "preferences",
    }

    if re.search(r"payload:\s*toCamelCase\(resultPayload\)", source):
        return _to_camel_case(payload)

    return payload


def _memory_search_result_from_vector_payload(payload):
    """Model Memory.search/getAll result formatting for one vector result."""
    excluded_keys = {
        "user_id",
        "agent_id",
        "run_id",
        "hash",
        "data",
        "createdAt",
        "updatedAt",
        "textLemmatized",
        "attributedTo",
    }

    result = {
        "id": "mem-1",
        "memory": payload["data"],
        "hash": payload["hash"],
        "metadata": {
            key: value for key, value in payload.items() if key not in excluded_keys
        },
    }
    if payload.get("user_id"):
        result["user_id"] = payload["user_id"]
    if payload.get("agent_id"):
        result["agent_id"] = payload["agent_id"]
    if payload.get("run_id"):
        result["run_id"] = payload["run_id"]
    return result


def test_issue_6266():
    assert Memory is not None

    repo_root = Path(__file__).resolve().parents[1]
    valkey_payload = _valkey_payload_from_source(
        repo_root,
        {
            "memory_id": "mem-1",
            "hash": "hash-1",
            "memory": "likes tea",
            "created_at": "1704067200",
            "user_id": "u1",
            "agent_id": "a1",
            "run_id": "r1",
            "metadata": '{"topic":"preferences"}',
        },
    )

    result = _memory_search_result_from_vector_payload(valkey_payload)

    assert result["user_id"] == "u1"
    assert result["agent_id"] == "a1"
    assert result["run_id"] == "r1"
    assert "userId" not in result["metadata"]
    assert "agentId" not in result["metadata"]
    assert "runId" not in result["metadata"]
