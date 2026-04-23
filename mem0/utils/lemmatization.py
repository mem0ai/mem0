"""
BM25 lemmatization for consistent keyword matching.

Uses spaCy's lemmatizer for better handling of:
- Verb forms: attending/attends/attended -> attend
- Comparatives/superlatives: older/oldest -> old
- Plurals: memories -> memory
- Avoids over-stemming: organization != organize

Also includes original -ing forms alongside lemmas to handle cases
where spaCy's context-dependent lemmatization produces inconsistent
results (e.g., "meeting" as noun vs verb -> different lemmas).

The loaded spaCy model is the English ``en_core_web_sm`` pipeline. On
non-Latin input it produces degenerate output (a single unsegmented
token for CJK / Arabic / Cyrillic, empty output for Thai). The
behaviour is intentionally *not* changed here - see GitHub issue #4884
for the broader i18n discussion - but callers are warned once per
process via :func:`mem0.utils.script_detection.contains_non_latin_letters`
so operators know BM25 is silently degraded.
"""

from __future__ import annotations

import logging

from mem0.utils.script_detection import contains_non_latin_letters

logger = logging.getLogger(__name__)

_warned_non_latin_bm25 = False


def _warn_non_latin_once() -> None:
    global _warned_non_latin_bm25
    if _warned_non_latin_bm25:
        return
    _warned_non_latin_bm25 = True
    logger.warning(
        "BM25 lemmatization received non-Latin input; the English spaCy "
        "pipeline will produce a single unsegmented token (or empty "
        "output for some scripts) and keyword-match recall will be near "
        "zero. Semantic retrieval continues to work. See issue #4884 "
        "for multilingual support tracking. This warning is logged once "
        "per process."
    )


def lemmatize_for_bm25(text: str) -> str:
    """Lemmatize text for BM25 matching.

    Returns space-joined lemmas for full-text search. Falls back to
    the original text if spaCy is unavailable.
    """
    from mem0.utils.spacy_models import get_nlp_lemma

    if contains_non_latin_letters(text):
        _warn_non_latin_once()

    nlp = get_nlp_lemma()
    if nlp is None:
        return text

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

    return " ".join(tokens)
