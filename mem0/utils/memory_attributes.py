"""Lightweight memory attribute inference for retrieval-time safeguards."""

from __future__ import annotations

from typing import Dict


NEGATIVE_CONSTRAINT_BOOST_WEIGHT = 0.35


NEGATIVE_CONSTRAINT_PATTERNS = (
    "do not recommend",
    "don't recommend",
    "does not want",
    "doesn't want",
    "does not like",
    "doesn't like",
    "does not prefer",
    "doesn't prefer",
    "does not want to",
    "doesn't want to",
    "do not want",
    "don't want",
    "should not recommend",
    "must not recommend",
    "never recommend",
    "no longer recommend",
    "not interested in",
    "would rather not",
    "prefers not to",
    "asked not to",
    "requests not to",
    "avoid recommending",
    "avoids recommending",
    "dislikes",
)


POSITIVE_PREFERENCE_PATTERNS = (
    "prefers",
    "likes",
    "enjoys",
    "wants",
    "prioritizes",
    "is interested in",
    "favorite",
    "favourite",
)


RECOMMENDATION_QUERY_PATTERNS = (
    "recommend",
    "suggest",
    "choose",
    "which",
    "best",
    "rank",
    "pick",
    "select",
    "find a",
    "find me",
    "looking for",
    "where should",
    "what should",
)


def infer_memory_attributes(memory_text: str) -> Dict[str, str]:
    """Infer stable, optional attributes from extracted memory text.

    The rules are intentionally conservative. They only tag explicit negative
    preference or exclusion statements as constraints, leaving ambiguous
    negations such as "not bothered by noise" as ordinary facts.
    """
    text = (memory_text or "").lower()

    if any(pattern in text for pattern in NEGATIVE_CONSTRAINT_PATTERNS):
        return {"memory_type": "constraint", "polarity": "negative"}

    if any(pattern in text for pattern in POSITIVE_PREFERENCE_PATTERNS):
        return {"memory_type": "preference", "polarity": "positive"}

    return {"memory_type": "fact", "polarity": "neutral"}


def is_recommendation_query(query: str) -> bool:
    """Return true when a query is likely asking for a choice or recommendation."""
    text = (query or "").lower()
    return any(pattern in text for pattern in RECOMMENDATION_QUERY_PATTERNS)


def get_constraint_boost(query: str, payload: Dict[str, object]) -> float:
    """Boost negative constraints only for recommendation or decision queries."""
    if not is_recommendation_query(query):
        return 0.0

    if payload.get("memory_type") == "constraint" and payload.get("polarity") == "negative":
        return NEGATIVE_CONSTRAINT_BOOST_WEIGHT

    return 0.0
