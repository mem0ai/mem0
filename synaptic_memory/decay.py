"""Adaptive decay for synapses with importance-weighted rates and replay queuing."""

from __future__ import annotations

from datetime import datetime, timedelta

from synaptic_memory.memory_db import MemoryMetricsDB
from synaptic_memory.models import ReplayItem
from synaptic_memory.synapse_db import SynapseDB

_BASE_DECAY_RATE = 0.01
_WEAKENING_THRESHOLD = 0.2
_DEAD_THRESHOLD = 0.01
_REPLAY_DUE_DAYS = 1


async def decay_all_synapses(
    synapse_db: SynapseDB,
    memory_db: MemoryMetricsDB,
) -> dict[str, int]:
    stats = {"decayed": 0, "queued_replay": 0, "deleted": 0}

    all_synapses = await synapse_db.get_all()
    if not all_synapses:
        return stats

    now = datetime.now()
    importance_cache: dict[str, float] = {}

    for synapse in all_synapses:
        source_id = synapse.source_id

        if source_id not in importance_cache:
            metrics = await memory_db.get(source_id)
            importance_cache[source_id] = (
                metrics.importance_score if metrics is not None else 0.5
            )

        importance = importance_cache[source_id]
        decay_rate = _BASE_DECAY_RATE * (1.0 - importance * 0.5)

        delta = now - synapse.last_strength_update
        days_elapsed = max(0.0, delta.total_seconds() / 86400.0)

        if days_elapsed == 0.0:
            continue

        new_strength = synapse.strength * ((1.0 - decay_rate) ** days_elapsed)
        new_strength = max(0.0, new_strength)

        await synapse_db.update_strength(
            synapse.id,
            strength=new_strength,
            last_strength_update=now,
        )
        stats["decayed"] += 1

        if _DEAD_THRESHOLD < new_strength < _WEAKENING_THRESHOLD:
            due = now + timedelta(days=_REPLAY_DUE_DAYS)
            replay_id = ReplayItem.new_id()
            await memory_db.add_to_replay(
                replay_id,
                synapse.target_id,
                synapse_id=synapse.id,
                priority=1.0 - new_strength,
                reason="weakening",
                due_at=due,
            )
            stats["queued_replay"] += 1

    deleted = await synapse_db.delete_below_threshold(_DEAD_THRESHOLD)
    stats["deleted"] = deleted

    return stats
