"""Replay buffer for preventing catastrophic forgetting in synaptic memory."""

from __future__ import annotations

from datetime import datetime

from synaptic_memory.memory_db import MemoryMetricsDB
from synaptic_memory.models import ReplayItem
from synaptic_memory.synapse_db import SynapseDB


class ReplayBuffer:
    def __init__(self, synapse_db: SynapseDB, memory_db: MemoryMetricsDB) -> None:
        self._synapse_db = synapse_db
        self._memory_db = memory_db

    async def populate_queue(self) -> int:
        added = 0

        weak_synapses = await self._synapse_db.get_weakening(threshold=0.2)
        for syn in weak_synapses:
            priority = 1.0 - syn.strength
            replay_id = ReplayItem.new_id()
            await self._memory_db.add_to_replay(
                replay_id,
                syn.source_id,
                synapse_id=syn.id,
                priority=priority,
                reason="weakening",
                due_at=datetime.now(),
            )
            added += 1

        isolated = await self._memory_db.get_isolated()
        for metrics in isolated:
            priority = max(0.0, min(1.0, 1.0 - metrics.total_strength))
            replay_id = ReplayItem.new_id()
            await self._memory_db.add_to_replay(
                replay_id,
                metrics.memory_id,
                synapse_id=None,
                priority=priority,
                reason="isolated",
                due_at=datetime.now(),
            )
            added += 1

        return added

    async def generate_review_prompt(
        self, item: dict, memories: dict[str, str]
    ) -> str:
        memory_id: str = item["memory_id"]
        synapse_id: str | None = item.get("synapse_id")

        if synapse_id:
            synapse = await self._synapse_db.get(synapse_id)
            if synapse:
                mem_a = memories.get(synapse.source_id, f"[{synapse.source_id}]")
                mem_b = memories.get(synapse.target_id, f"[{synapse.target_id}]")
                return f"How do these memories connect? A: {mem_a} / B: {mem_b}"

        mem_text = memories.get(memory_id, f"[{memory_id}]")
        return f"This memory seems disconnected: {mem_text}. What else relates?"

    async def get_due_reviews(self, limit: int = 10) -> list[dict]:
        items = await self._memory_db.get_due_replays(limit=limit)
        return [
            {
                "id": item.id,
                "memory_id": item.memory_id,
                "synapse_id": item.synapse_id,
                "priority": item.priority,
                "reason": item.reason,
                "presented_count": item.presented_count,
            }
            for item in items
        ]

    async def mark_reviewed(self, replay_id: str, was_useful: bool) -> None:
        items = await self._memory_db.get_due_replays(limit=1000)
        item = next((r for r in items if r.id == replay_id), None)

        presented_count = (item.presented_count + 1) if item else 1

        if was_useful:
            await self._memory_db.update_replay(replay_id, presented_count)
        else:
            await self._memory_db.delete_replay(replay_id)
