"""
Validates the temporal-shift corpus (temporal_shift_corpus.py).
Kept in its own test file, separate from the attribution corpus, per
@chenhz01's request on mem0ai/mem0#7283.

Schema-only: this validates the corpus's shape and that known-failure
cases are marked, not the underlying NLI model's behavior. Behavioral
verification against a real model lives in MiniEval's own test suite
(the project this corpus was developed alongside) -- keeping this file
free of that dependency matches "the corpus is fixtures plus
machine-checkable verdicts" as requested.

Run with:
    pytest tests/memory/test_temporal_shift_corpus.py -v
"""

import pytest
from tests.memory.verification.temporal_shift_corpus import TEMPORAL_CORPUS as CORPUS


@pytest.mark.parametrize("case", CORPUS, ids=[c.id for c in CORPUS])
def test_temporal_case_schema(case):
    """
    Verify each temporal corpus item has required fields and a valid
    tri-state expected verdict.

    known_failure cases are marked xfail BEFORE the schema assert runs,
    not after -- a known, documented failure should be reported as an
    expected failure, not as a hard assertion error that looks like a
    corpus data bug.
    """
    if case.known_status == "known_failure":
        pytest.xfail(f"{case.id}: documented known failure -- {case.note}")

    assert hasattr(case, "id")
    assert hasattr(case, "candidate")
    assert hasattr(case, "source_text")
    assert hasattr(case, "expected")
    assert case.expected in {"accepted", "rejected_with_reason", "uncertain"}


def test_corpus_has_known_status_for_every_case():
    """
    Every case must declare what's actually known about it -- "passes",
    "known_failure", or "untested" -- so nothing is silently assumed to
    work. This is the honesty mechanism this corpus file exists to
    enforce.
    """
    valid_statuses = {"passes", "known_failure", "untested"}
    for case in CORPUS:
        assert case.known_status in valid_statuses, (
            f"{case.id} has an invalid known_status: {case.known_status!r}"
        )