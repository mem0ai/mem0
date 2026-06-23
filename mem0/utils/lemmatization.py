"""
BM25 preprocessing for consistent keyword matching.

English text uses spaCy lemmatization when available. Non-Latin text and
spaCy-unavailable environments use dependency-free multilingual tokenization
so BM25 still has overlapping terms for CJK, Thai, Arabic, Cyrillic, and IDs.
"""

from __future__ import annotations

import unicodedata

from mem0.utils.text_tokenization import contains_non_latin_letters, tokenize_for_bm25


def _fallback_tokenize(text: str) -> str:
    return " ".join(tokenize_for_bm25(text))


def lemmatize_for_bm25(text: str) -> str:
    """Return a space-joined BM25 token string for indexing and search."""
    if not text:
        return ""

    if contains_non_latin_letters(text):
        return _fallback_tokenize(text)

    from mem0.utils.spacy_models import get_nlp_lemma

    nlp = get_nlp_lemma()
    if nlp is None:
        return _fallback_tokenize(text)

    normalized_text = unicodedata.normalize("NFKC", text).casefold()
    doc = nlp(normalized_text)
    tokens = []

    for token in doc:
        if token.is_punct or token.is_stop:
            continue

        lemma = unicodedata.normalize("NFKC", token.lemma_)
        if lemma.isalnum():
            tokens.append(lemma)
        else:
            tokens.extend(tokenize_for_bm25(token.text))

        if token.text.endswith("ing") and token.text != lemma and token.text.isalnum():
            tokens.append(token.text)

    if tokens:
        return " ".join(tokens)

    return _fallback_tokenize(text)
