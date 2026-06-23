"""Unit tests for the whole-word substring entity filter.

Pure-Python (no spaCy required): exercises ``_remove_whole_word_substring_entities``
directly and pins it to the exact behavior of the original inline O(n^2) filter.
"""

import re

from mem0.utils.entity_extraction import _remove_whole_word_substring_entities


def _reference(entities):
    """The original inline O(n^2) filter, kept as a parity oracle."""
    all_lower = [e[1].lower() for e in entities]
    return [
        (t, e)
        for t, e in entities
        if not any(e.lower() != o and re.search(rf"\b{re.escape(e.lower())}\b", o) for o in all_lower)
    ]


def test_drops_whole_word_substring():
    ents = [("NOUN", "machine"), ("COMPOUND", "machine learning")]
    result = _remove_whole_word_substring_entities(ents)
    assert ("COMPOUND", "machine learning") in result
    assert ("NOUN", "machine") not in result


def test_keeps_leading_substring_not_on_word_boundary():
    # "Sam" is only a leading substring of "Samsung" (not a whole word) -> both kept.
    ents = [("PROPER", "Sam"), ("PROPER", "Samsung")]
    assert _remove_whole_word_substring_entities(ents) == ents


def test_case_insensitive():
    ents = [("PROPER", "Google"), ("COMPOUND", "google cloud"), ("NOUN", "cloud")]
    # "Google" and "cloud" are whole-word substrings of "google cloud" (case-insensitive).
    assert _remove_whole_word_substring_entities(ents) == [("COMPOUND", "google cloud")]


def test_empty_and_single():
    assert _remove_whole_word_substring_entities([]) == []
    assert _remove_whole_word_substring_entities([("NOUN", "alone")]) == [("NOUN", "alone")]


def test_parity_with_reference_naive_filter():
    cases = [
        [("A", "ai"), ("B", "ai model"), ("C", "model"), ("D", "open ai"), ("E", "ai"), ("F", "deep")],
        [("P", "New York"), ("Q", "York"), ("R", "New"), ("S", "New Yorker")],
        [("X", "c++"), ("Y", "c"), ("Z", "c++ guide")],  # regex special chars must be escaped
        [("M", "data"), ("N", "database"), ("O", "data lake")],
        [("U", "Sam"), ("V", "Samsung"), ("W", "Sam Altman")],
    ]
    for ents in cases:
        assert _remove_whole_word_substring_entities(ents) == _reference(ents), ents
