"""Drift test: the provider counts in mem0/AGENTS.md must match the factory registries."""

import re
from pathlib import Path

import pytest

from mem0.utils.factory import (
    EmbedderFactory,
    LlmFactory,
    RerankerFactory,
    VectorStoreFactory,
)

AGENTS_MD = Path(__file__).resolve().parents[1] / "mem0" / "AGENTS.md"

ROW_TO_FACTORY = {
    "LLMs": LlmFactory,
    "Vector stores": VectorStoreFactory,
    "Embeddings": EmbedderFactory,
    "Rerankers": RerankerFactory,
}


def _documented_count(row_name: str) -> int:
    match = re.search(rf"^\|\s*{re.escape(row_name)}\s*\|\s*(\d+)\s*\|", AGENTS_MD.read_text(), re.M)
    return int(match.group(1)) if match else None


@pytest.mark.parametrize("row_name,factory", ROW_TO_FACTORY.items())
def test_documented_count_matches_registry(row_name, factory):
    documented = _documented_count(row_name)
    assert documented is not None, f"mem0/AGENTS.md provider table has no {row_name!r} row"
    assert documented == len(factory.provider_to_class), (
        f"mem0/AGENTS.md says {documented} {row_name} but "
        f"{factory.__name__}.provider_to_class has {len(factory.provider_to_class)}"
    )
