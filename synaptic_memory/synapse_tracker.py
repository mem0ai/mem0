"""Citation detection with STDP temporal bias and co-citation tracking."""

from __future__ import annotations

import math
import re
from datetime import datetime

from synaptic_memory.models import CitationType
from synaptic_memory.synapse_db import SynapseDB


class CitationDetector:
    EXPLICIT_PATTERNS = [
        r'\[memory[_\w]+\]',
        r'as (?:noted|mentioned|discussed|above|previously)\s?',
        r'reference:? [\w-]+',
        r'according to (?:the )?(?:memory|note)',
    ]

    TEMPORAL_BEFORE = ['before', 'earlier', 'previously', 'prior to', 'preceding']
    TEMPORAL_AFTER = ['after', 'later', 'subsequently', 'following', 'since']

    _STOPWORDS = frozenset({
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
        'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
        'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
        'will', 'would', 'could', 'should', 'may', 'might', 'shall',
        'it', 'its', 'this', 'that', 'these', 'those', 'i', 'we', 'you',
        'he', 'she', 'they', 'my', 'our', 'your', 'his', 'her', 'their',
    })

    def __init__(self, synapse_db: SynapseDB) -> None:
        self._db = synapse_db
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.EXPLICIT_PATTERNS
        ]

    def _tokenize(self, text: str) -> set[str]:
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        return {w for w in words if w not in self._STOPWORDS}

    def _has_explicit_citation(self, content: str) -> bool:
        return any(p.search(content) for p in self._compiled_patterns)

    def _detect_temporal_direction(self, content: str) -> int:
        lower = content.lower()
        if any(phrase in lower for phrase in self.TEMPORAL_BEFORE):
            return -1
        if any(phrase in lower for phrase in self.TEMPORAL_AFTER):
            return 1
        return 0

    def _semantic_overlap(self, tokens_a: set[str], tokens_b: set[str]) -> float:
        if not tokens_a or not tokens_b:
            return 0.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union)

    def _compute_temporal_bias(
        self,
        source_created: datetime | None,
        target_created: datetime | None,
        temporal_direction: int,
    ) -> float:
        if source_created is not None and target_created is not None:
            if source_created < target_created:
                return 0.1
            else:
                return -0.05

        if temporal_direction == -1:
            return 0.1
        if temporal_direction == 1:
            return -0.05
        return 0.0

    async def detect_citations(
        self,
        content: str,
        context_memories: list[dict],
        current_time: datetime | None = None,
    ) -> list[tuple[str, str, CitationType, float, float]]:
        results: list[tuple[str, str, CitationType, float, float]] = []
        if not context_memories:
            return results

        content_tokens = self._tokenize(content)
        has_explicit = self._has_explicit_citation(content)
        temporal_direction = self._detect_temporal_direction(content)

        current_memory = context_memories[0]
        current_id: str = current_memory['id']
        current_created: datetime | None = _parse_datetime(current_memory.get('created_at'))

        candidates = context_memories[1:]

        for memory in candidates:
            mem_id: str = memory['id']
            if mem_id == current_id:
                continue

            mem_text: str = memory.get('memory') or memory.get('content') or memory.get('text') or ''
            mem_tokens = self._tokenize(mem_text)
            overlap = self._semantic_overlap(content_tokens, mem_tokens)
            shared_count = len(content_tokens & mem_tokens)

            is_explicit = has_explicit
            is_semantic = overlap >= 0.3 or shared_count >= 3

            if not is_explicit and not is_semantic:
                continue

            citation_type = CitationType.EXPLICIT if is_explicit else CitationType.RETRIEVAL
            mem_created = _parse_datetime(memory.get('created_at'))
            temporal_bias = self._compute_temporal_bias(
                mem_created, current_created, temporal_direction
            )

            if is_explicit:
                strength_boost = 0.2
            else:
                strength_boost = min(0.15, overlap * 0.5)
            results.append((mem_id, current_id, citation_type, strength_boost, temporal_bias))

        return results


async def track_co_citations(
    synapse_db: SynapseDB,
    results: list[dict],
) -> None:
    if len(results) < 2:
        return

    ids: list[str] = [r['id'] for r in results if 'id' in r]

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            source_id = ids[i]
            target_id = ids[j]

            synapse = await synapse_db.get_or_create(
                source_id, target_id, citation_type=CitationType.CO_RETRIEVAL
            )

            new_count = synapse.co_citation_count + 1
            boost = 0.1 * math.log(1 + new_count)
            new_strength = min(1.0, synapse.strength + boost)

            await synapse_db.update_strength(
                synapse.id,
                strength=new_strength,
                co_citation_count=new_count,
                last_accessed=datetime.now(),
            )


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None
