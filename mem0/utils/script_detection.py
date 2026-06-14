"""Script detection for retrieval preprocessing.

The English spaCy pipeline used by :mod:`mem0.utils.lemmatization` and
:mod:`mem0.utils.entity_extraction` silently produces degenerate output
on non-Latin input: single-token BM25 lemmas for CJK / Arabic /
Cyrillic, empty output for Thai, and no entities for any of them.

Instead of changing retrieval behaviour here, this module only provides
a lightweight detector so callers can emit a single warning and surface
the issue to operators. See GitHub issue #4884 for background.
"""

from __future__ import annotations

# Latin Unicode blocks we treat as "supported by the English pipeline":
# Basic Latin, Latin-1 Supplement, Latin Extended A/B, IPA, plus the
# Latin Extended Additional / -C / -D / -E ranges. Together these cover
# essentially every language written with a Latin alphabet.
_LATIN_RANGES: tuple[tuple[int, int], ...] = (
    (0x0000, 0x007F),  # Basic Latin (ASCII)
    (0x0080, 0x00FF),  # Latin-1 Supplement
    (0x0100, 0x017F),  # Latin Extended-A
    (0x0180, 0x024F),  # Latin Extended-B
    (0x0250, 0x02AF),  # IPA Extensions
    (0x02B0, 0x02FF),  # Spacing Modifier Letters
    (0x1E00, 0x1EFF),  # Latin Extended Additional
    (0x2C60, 0x2C7F),  # Latin Extended-C
    (0xA720, 0xA7FF),  # Latin Extended-D
    (0xAB30, 0xAB6F),  # Latin Extended-E
)


def _is_latin_codepoint(cp: int) -> bool:
    for start, end in _LATIN_RANGES:
        if start <= cp <= end:
            return True
    return False


def contains_non_latin_letters(text: str) -> bool:
    """Return True if *text* contains any letter outside the Latin script.

    Only cased / alphabetic characters count - spaces, digits, and
    punctuation are ignored so that strings like ``"2024-Q1"`` or
    ``"price: $100"`` don't trigger a warning.
    """
    if not text:
        return False
    for ch in text:
        if not ch.isalpha():
            continue
        if not _is_latin_codepoint(ord(ch)):
            return True
    return False
