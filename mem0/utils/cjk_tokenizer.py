"""CJK tokenization for BM25 keyword matching.

Pure-Python, zero dependencies. Handles Chinese/Japanese/Korean text that
space-based tokenizers (Postgres ``to_tsvector('simple')``, spaCy English
lemmatizer) cannot segment: a Chinese sentence like ``我们最近配置的 rerank``
has no spaces, so naive tokenizers treat the whole run as one token and the
BM25 leg never matches.

Approach:
- Split text into contiguous CJK chunks and latin/number words.
- For each CJK chunk, emit **unigrams + bigrams** (e.g. ``混合检索`` ->
  ``混``, ``合``, ``检``, ``索``, ``混合``, ``合检``, ``检索``). No dictionary,
  no jieba, no spaCy.
- Latin/number words (``9router``, ``memobase-use``, ``GOALS.md``) are kept
  as exact tokens with trailing ``._-`` stripped.
- Single-char CJK stopwords (的/是/了/在/和…) are dropped from the index.

Two modes:
- ``tokenize(text)`` — document side: unigrams + bigrams (max recall).
- ``tokenize(text, query_mode=True)`` — query side: bigrams only, because
  single-char unigrams are high-df noise for short queries (生日/模型 match
  almost every doc); single-char chunks fall back to unigram.
"""

from __future__ import annotations

import re
from typing import List

# Latin/number word: allow inner dots/hyphens/underscores but never trailing.
_LATIN_RE = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", re.IGNORECASE)
# Contiguous CJK runs (ideographs only — no CJK punctuation).
_CJK_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+")
# Single-char CJK stopwords (function words / pronouns / particles).
_CJK_STOPWORDS = frozenset(
    "的了是在和有我你他她它这那就都而及与着或个们把被让对从向为以于"
)


def _has_cjk(text: str) -> bool:
    """True if the text contains any CJK ideograph."""
    return _CJK_RE.search(text) is not None


def tokenize(text: str, query_mode: bool = False) -> List[str]:
    """CJK unigram+bigram (per contiguous chunk) + latin words. Lowercased.

    Args:
        text: Input text.
        query_mode: If True, CJK chunks of len>=2 emit bigrams only (cuts
            high-df unigram noise for short queries); single-char chunks fall
            back to unigram. Document side keeps unigram+bigram for recall.

    Returns:
        List of tokens (lowercased).
    """
    if not text:
        return []
    tokens: List[str] = []
    t = text.lower()
    for m in _LATIN_RE.finditer(t):
        w = m.group(0).rstrip("._-")
        if len(w) >= 2:
            tokens.append(w)
    for chunk in _CJK_RE.findall(t):
        n = len(chunk)
        if n == 1:
            if chunk not in _CJK_STOPWORDS:
                tokens.append(chunk)
            continue
        if query_mode:
            # bigrams only — unigrams are high-df noise for queries
            for i in range(n - 1):
                tokens.append(chunk[i : i + 2])
        else:
            for ch in chunk:
                if ch not in _CJK_STOPWORDS:
                    tokens.append(ch)
            for i in range(n - 1):
                tokens.append(chunk[i : i + 2])
    return tokens


def tokenize_for_bm25(text: str, query_mode: bool = False) -> str:
    """Space-joined token string for BM25/full-text search.

    Mirrors ``lemmatize_for_bm25``'s contract (space-joined tokens) so it can
    be used as a drop-in for the CJK path.
    """
    return " ".join(tokenize(text, query_mode=query_mode))
