"""
BM25 lemmatization for consistent keyword matching.

Uses spaCy's lemmatizer for better handling of:
- Verb forms: attending/attends/attended -> attend
- Comparatives/superlatives: older/oldest -> old
- Plurals: memories -> memory
- Avoids over-stemming: organization != organize

Also includes script-aware preprocessing for mixed Chinese-English text:
- Han spans use character bigrams so queries overlap longer memories.
- Latin spans continue through spaCy's lemmatizer.
- Technical identifiers are preserved as exact normalized tokens.
"""

from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

_HAN_RANGES = (
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x2FA1F),
    (0x30000, 0x323AF),
)

# Preserve connector-based technical identifiers while leaving ordinary
# hyphenated words to spaCy. A hyphen-only token must contain a digit;
# stronger technical separators such as '/', '_', '.', ':', and '#' are
# sufficient on their own.
_IDENTIFIER_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?=[A-Za-z0-9._/:#-]*(?:\d|[._/:#]))"
    r"[A-Za-z0-9]+(?:[-_./:#][A-Za-z0-9]+)+"
    r"(?![A-Za-z0-9])"
)
_SIMPLE_WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)


def _is_han(character: str) -> bool:
    codepoint = ord(character)
    return codepoint == 0x3007 or any(start <= codepoint <= end for start, end in _HAN_RANGES)


def _tokenize_han(span: str) -> list[str]:
    if len(span) < 2:
        return [span]
    return [span[index : index + 2] for index in range(len(span) - 1)]


def _split_han_spans(text: str):
    if not text:
        return

    start = 0
    is_han = _is_han(text[0])
    for index, character in enumerate(text[1:], start=1):
        character_is_han = _is_han(character)
        if character_is_han != is_han:
            yield ("han" if is_han else "text"), text[start:index]
            start = index
            is_han = character_is_han
    yield ("han" if is_han else "text"), text[start:]


def _split_bm25_spans(text: str):
    cursor = 0
    for match in _IDENTIFIER_RE.finditer(text):
        yield from _split_han_spans(text[cursor : match.start()])
        yield "identifier", match.group()
        cursor = match.end()
    yield from _split_han_spans(text[cursor:])


def _lemmatize_text_span(text: str, nlp) -> list[str]:
    if nlp is None:
        return _SIMPLE_WORD_RE.findall(text.lower())

    doc = nlp(text.lower())
    tokens = []

    for token in doc:
        if token.is_punct or token.is_stop:
            continue

        lemma = token.lemma_
        if lemma.isalnum():
            tokens.append(lemma)

        # Also add original if it ends in -ing and differs from lemma.
        # This handles noun/verb ambiguity (meeting/meet, attending/attend).
        if token.text.endswith("ing") and token.text != lemma and token.text.isalnum():
            tokens.append(token.text)

    return tokens


def lemmatize_for_bm25(text: str) -> str:
    """Normalize and tokenize text for BM25 matching.

    Han spans use character bigrams, connector-based identifiers remain
    intact, and other text uses spaCy lemmatization. If spaCy is unavailable,
    non-Han text falls back to lightweight Unicode word tokenization.
    """
    from mem0.utils.spacy_models import get_nlp_lemma

    normalized = unicodedata.normalize("NFKC", text)
    spans = list(_split_bm25_spans(normalized))
    needs_nlp = any(kind == "text" and any(character.isalnum() for character in span) for kind, span in spans)
    nlp = get_nlp_lemma() if needs_nlp else None
    tokens = []

    for kind, span in spans:
        if kind == "han":
            tokens.extend(_tokenize_han(span))
        elif kind == "identifier":
            tokens.append(span.lower())
        else:
            tokens.extend(_lemmatize_text_span(span, nlp))

    return " ".join(tokens)
