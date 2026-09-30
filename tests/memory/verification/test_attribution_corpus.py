"""
Validates attribution regression corpus integrity (attribution_corpus.py).

Schema-only: this validates the corpus's shape, not the underlying
guard's behavior. Behavioral verification against MiniEval's real
attribution guard lives in MiniEval's own test suite (the project this
corpus was developed alongside) -- keeping this file free of that
dependency matches "the corpus is fixtures plus machine-checkable
verdicts" as requested by @chenhz01 on mem0ai/mem0#7283.

Run with:
    pytest tests/memory/test_attribution_corpus.py -v
"""

import pytest
from tests.memory.verification.attribution_corpus import CORPUS


@pytest.mark.parametrize("case", CORPUS, ids=[c.id for c in CORPUS])
def test_corpus_schema(case):
    """Verify each corpus item has required fields and a valid tri-state
    expected verdict."""
    assert hasattr(case, "id")
    assert hasattr(case, "candidate")
    assert hasattr(case, "source_text")
    assert hasattr(case, "expected")
    assert case.expected in {"accepted", "rejected_with_reason", "uncertain"}


def test_corpus_covers_required_categories():
    """
    Confirms required categories requested by maintainers:
    sibling/family possession and reported speech coverage.
    """
    categories = {c.category for c in CORPUS}
    assert "sibling_family_possession" in categories
    assert "reported_speech" in categories

    family_count = sum(1 for c in CORPUS if c.category == "sibling_family_possession")
    reported_count = sum(1 for c in CORPUS if c.category == "reported_speech")
    assert family_count >= 3, "Too few family-possession cases to call this a corpus"
    assert reported_count >= 3, "Too few reported-speech cases to call this a corpus"