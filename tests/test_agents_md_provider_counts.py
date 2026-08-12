"""Drift test: the provider counts in AGENTS.md must match the factory registries."""

import re
from pathlib import Path

import pytest

from mem0.utils.factory import (
    EmbedderFactory,
    LlmFactory,
    RerankerFactory,
    VectorStoreFactory,
)

AGENTS_MD = Path(__file__).resolve().parents[1] / "AGENTS.md"

ROW_TO_FACTORY = {
    "LLMs": LlmFactory,
    "Vector Stores": VectorStoreFactory,
    "Embeddings": EmbedderFactory,
    "Rerankers": RerankerFactory,
}


def _documented_counts() -> dict[str, int]:
    rows = re.findall(r"^\|\s*\*\*(.+?)\*\*\s*\|\s*(\d+)\s*\|", AGENTS_MD.read_text(), re.M)
    return {name: int(count) for name, count in rows}


@pytest.mark.parametrize("row_name,factory", ROW_TO_FACTORY.items())
def test_documented_count_matches_registry(row_name, factory):
    documented = _documented_counts()
    assert row_name in documented, f"AGENTS.md provider table has no {row_name!r} row"
    assert documented[row_name] == len(factory.provider_to_class), (
        f"AGENTS.md says {documented[row_name]} {row_name} but "
        f"{factory.__name__}.provider_to_class has {len(factory.provider_to_class)}"
    )
