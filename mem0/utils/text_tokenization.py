"""Dependency-free text tokenization for BM25 preprocessing."""

from __future__ import annotations

import re
import unicodedata

_LATIN_RANGES: tuple[tuple[int, int], ...] = (
    (0x0000, 0x007F),
    (0x0080, 0x00FF),
    (0x0100, 0x017F),
    (0x0180, 0x024F),
    (0x0250, 0x02AF),
    (0x02B0, 0x02FF),
    (0x1E00, 0x1EFF),
    (0x2C60, 0x2C7F),
    (0xA720, 0xA7FF),
    (0xAB30, 0xAB6F),
)

_CHAR_NGRAM_RANGES: tuple[tuple[int, int], ...] = (
    (0x0E00, 0x0E7F),  # Thai
    (0x1100, 0x11FF),  # Hangul Jamo
    (0x3040, 0x309F),  # Hiragana
    (0x30A0, 0x30FF),  # Katakana
    (0x3130, 0x318F),  # Hangul Compatibility Jamo
    (0x3400, 0x4DBF),  # CJK Extension A
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0xA960, 0xA97F),  # Hangul Jamo Extended-A
    (0xAC00, 0xD7AF),  # Hangul syllables
    (0xD7B0, 0xD7FF),  # Hangul Jamo Extended-B
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
    (0x20000, 0x2A6DF),  # CJK Extension B
    (0x2A700, 0x2B73F),  # CJK Extension C
    (0x2B740, 0x2B81F),  # CJK Extension D
    (0x2B820, 0x2CEAF),  # CJK Extension E
    (0x2CEB0, 0x2EBEF),  # CJK Extension F
    (0x2EBF0, 0x2EE5F),  # CJK Extension I
    (0x2F800, 0x2FA1F),  # CJK Compatibility Ideographs Supplement
    (0x30000, 0x3134F),  # CJK Extension G
    (0x31350, 0x323AF),  # CJK Extension H
)

_CONNECTOR_RE = re.compile(r"[-_./:]+")
_LETTER_OR_NUMBER_CATEGORIES = {"L", "N", "M"}


def _in_ranges(ch: str, ranges: tuple[tuple[int, int], ...]) -> bool:
    cp = ord(ch)
    return any(start <= cp <= end for start, end in ranges)


def _is_latin_letter(ch: str) -> bool:
    return _in_ranges(ch, _LATIN_RANGES)


def _is_char_ngram_script(ch: str) -> bool:
    return _in_ranges(ch, _CHAR_NGRAM_RANGES)


def _is_word_char(ch: str) -> bool:
    return unicodedata.category(ch)[0] in _LETTER_OR_NUMBER_CATEGORIES


def contains_non_latin_letters(text: str) -> bool:
    """Return True when text contains at least one alphabetic non-Latin character."""
    for ch in unicodedata.normalize("NFKC", text):
        if ch.isalpha() and not _is_latin_letter(ch):
            return True
    return False


def _append_identifier_tokens(tokens: list[str], raw: str) -> None:
    token = raw.strip("-_./:")
    if not token:
        return

    tokens.append(token)
    for part in _CONNECTOR_RE.split(token):
        if part and part != token:
            tokens.append(part)


def _append_char_ngrams(tokens: list[str], raw: str) -> None:
    chars = [ch for ch in raw if _is_word_char(ch)]
    if not chars:
        return

    tokens.extend(chars)
    if len(chars) > 1:
        tokens.extend("".join(chars[i : i + 2]) for i in range(len(chars) - 1))


def tokenize_for_bm25(text: str) -> list[str]:
    """Tokenize text into a BM25-friendly stream without external dependencies."""
    normalized = text.casefold()
    tokens: list[str] = []
    word_run: list[str] = []
    char_run: list[str] = []

    def flush_word() -> None:
        if word_run:
            _append_identifier_tokens(tokens, "".join(word_run))
            word_run.clear()

    def flush_char_run() -> None:
        if char_run:
            _append_char_ngrams(tokens, "".join(char_run))
            char_run.clear()

    for idx, ch in enumerate(normalized):
        if _is_char_ngram_script(ch):
            flush_word()
            char_run.append(ch)
            continue

        if _is_word_char(ch):
            flush_char_run()
            word_run.append(ch)
            continue

        if ch in "-_./:" and word_run:
            next_ch = normalized[idx + 1] if idx + 1 < len(normalized) else ""
            if next_ch and (_is_word_char(next_ch) or _is_char_ngram_script(next_ch)):
                word_run.append(ch)
                continue

        flush_word()
        flush_char_run()

    flush_word()
    flush_char_run()

    if not tokens and any(_is_word_char(ch) for ch in normalized):
        compact = "".join(ch for ch in normalized if _is_word_char(ch))
        if compact:
            tokens.append(compact)

    return tokens
