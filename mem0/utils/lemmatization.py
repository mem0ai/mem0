"""
BM25 lemmatization for consistent keyword matching.

For CJK text (Chinese/Japanese/Korean), uses jieba segmentation.
For other text, uses spaCy's lemmatizer for better handling of:
- Verb forms: attending/attends/attended -> attend
- Comparatives/superlatives: older/oldest -> old
- Plurals: memories -> memory
- Avoids over-stemming: organization != organize

Also includes original -ing forms alongside lemmas to handle cases
where spaCy's context-dependent lemmatization produces inconsistent
results (e.g., "meeting" as noun vs verb -> different lemmas).
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")


def _has_cjk(text: str) -> bool:
    """Check if text contains CJK characters."""
    return bool(_CJK_RE.search(text))


def _jieba_segment(text: str) -> str:
    """Segment CJK text using jieba."""
    import jieba

    return " ".join(jieba.cut(text))


def lemmatize_for_bm25(text: str) -> str:
    """Lemmatize text for BM25 matching.

    For CJK text, uses jieba segmentation.
    For other text, uses spaCy lemmatization. Falls back to
    the original text if spaCy is unavailable.
    """
    if _has_cjk(text):
        return _jieba_segment(text)

    from mem0.utils.spacy_models import get_nlp_lemma

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
