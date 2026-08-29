"""Smoke tests for the two v3 retrieval-signal producers.

``extract_entities`` (and its batch variant) drive entity linking, while
``lemmatize_for_bm25`` produces the lemmatized text fed to keyword search.
Both degrade to silent no-ops when spaCy is absent, and the unit tests that
cover them skip in that case — so a missing ``nlp`` dependency lets the whole
suite pass green while these signals stop working.

These smoke tests are gated behind ``MEM0_REQUIRE_NLP=1`` (set in CI, see
``.github/workflows/ci.yml``) so local runs without the optional ``nlp``
extra keep passing, but CI fails loudly if either producer returns empty or
identity output.
"""

from __future__ import annotations

import os

import pytest

from mem0.utils.entity_extraction import extract_entities
from mem0.utils.lemmatization import lemmatize_for_bm25

pytestmark = pytest.mark.skipif(
    os.environ.get("MEM0_REQUIRE_NLP") != "1",
    reason="set MEM0_REQUIRE_NLP=1 (as CI does) to run the nlp producer smoke tests",
)


def test_entity_extraction_produces_entities():
    entities = extract_entities("John Smith works at Google on machine learning projects")
    assert entities, "extract_entities returned no entities; spaCy pipeline is not functioning"


def test_lemmatization_normalizes_text():
    source = "User is attending meetings about memories"
    lemmas = lemmatize_for_bm25(source)
    assert lemmas, "lemmatize_for_bm25 returned empty output"
    assert lemmas != source, "lemmatize_for_bm25 returned its input unchanged (identity fallback)"
