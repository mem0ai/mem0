"""Strength update functions with STDP temporal bias and homeostatic scaling."""

from __future__ import annotations

from datetime import datetime

from synaptic_memory.models import CitationType
from synaptic_memory.synapse_db import SynapseDB

BOOSTS: dict[CitationType, float] = {
    CitationType.RETRIEVAL: 0.05,
    CitationType.EXPLICIT: 0.2,
    CitationType.CO_RETRIEVAL: 0.1,
    CitationType.DECISION: 0.5,
    CitationType.MANUAL: 1.0,
    CitationType.TEMPORAL: 0.05,
}

MAX_TOTAL_OUTBOUND_STRENGTH = 10.0


async def on_citation(
    synapse_db: SynapseDB,
    source_id: str,
    target_id: str,
    citation_type: CitationType,
    temporal_bias: float = 0.0,
) -> None:
    base_boost = BOOSTS.get(citation_type, BOOSTS[CitationType.RETRIEVAL])
    final_boost = base_boost * (1.0 + temporal_bias)

    synapse = await synapse_db.get_or_create(
        source_id, target_id, citation_type=citation_type, temporal_bias=temporal_bias
    )

    new_strength = min(1.0, synapse.strength + final_boost)

    await synapse_db.update_strength(
        synapse.id,
        strength=new_strength,
        access_count=synapse.access_count + 1,
        last_accessed=datetime.now(),
        last_strength_update=datetime.now(),
    )

    await apply_homeostatic_scaling(synapse_db, source_id)


async def apply_homeostatic_scaling(synapse_db: SynapseDB, memory_id: str) -> None:
    outbound = await synapse_db.get_outbound(memory_id)
    if not outbound:
        return

    total = sum(s.strength for s in outbound)
    if total <= MAX_TOTAL_OUTBOUND_STRENGTH:
        return

    scale_factor = MAX_TOTAL_OUTBOUND_STRENGTH / total
    now = datetime.now()

    for synapse in outbound:
        scaled = synapse.strength * scale_factor
        await synapse_db.update_strength(
            synapse.id,
            strength=scaled,
            last_strength_update=now,
        )
