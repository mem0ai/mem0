import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "server"))

from server_state import _merge_config


def test_merge_config_replaces_provider_specific_config_when_provider_changes():
    base = {
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "host": "localhost",
                "port": 5432,
                "dbname": "postgres",
                "user": "postgres",
                "password": "",
                "collection_name": "memories",
            },
        },
    }
    updates = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "path": r"C:\tmp\qdrant",
                "collection_name": "memories",
            },
        },
    }

    merged = _merge_config(base, updates)

    assert merged["vector_store"] == updates["vector_store"]


def test_merge_config_deep_merges_same_provider_config():
    base = {
        "llm": {
            "provider": "openai",
            "config": {
                "api_key": "sk-test",
                "temperature": 0.2,
                "model": "gpt-4.1-nano-2025-04-14",
            },
        },
    }
    updates = {
        "llm": {
            "provider": "openai",
            "config": {
                "temperature": 0.1,
            },
        },
    }

    merged = _merge_config(base, updates)

    assert merged["llm"]["config"] == {
        "api_key": "sk-test",
        "temperature": 0.1,
        "model": "gpt-4.1-nano-2025-04-14",
    }
