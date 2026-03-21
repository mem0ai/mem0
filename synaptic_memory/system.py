"""Main SynapticMemorySystem integration class."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from synaptic_memory.decay import decay_all_synapses
from synaptic_memory.memory_db import MemoryMetricsDB
from synaptic_memory.models import CitationType, Synapse
from synaptic_memory.pagerank import calculate_network_centrality
from synaptic_memory.replay import ReplayBuffer
from synaptic_memory.strength import apply_homeostatic_scaling, on_citation
from synaptic_memory.synapse_db import SynapseDB
from synaptic_memory.synapse_tracker import CitationDetector, track_co_citations


class SynapticMemorySystem:
    def __init__(
        self,
        db_dir: str | Path | None = None,
        mem0_url: str | None = None,
    ) -> None:
        self.db_dir = Path(
            db_dir
            or os.environ.get(
                "SYNAPTIC_DB_DIR",
                Path.home() / "projects" / "mem0" / "synaptic_memory" / "data",
            )
        )
        self.mem0_url = mem0_url or os.environ.get("MEM0_URL", "")

        self.synapse_db = SynapseDB(self.db_dir / "synapses.db")
        self.memory_db = MemoryMetricsDB(self.db_dir / "memory_metrics.db")
        self.detector: CitationDetector | None = None
        self.replay: ReplayBuffer | None = None

    async def connect(self) -> None:
        self.db_dir.mkdir(parents=True, exist_ok=True)
        await self.synapse_db.connect()
        await self.memory_db.connect()
        self.detector = CitationDetector(self.synapse_db)
        self.replay = ReplayBuffer(self.synapse_db, self.memory_db)

    async def close(self) -> None:
        await self.synapse_db.close()
        await self.memory_db.close()

    async def __aenter__(self) -> SynapticMemorySystem:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def add_memory(
        self,
        memory_id: str,
        content: str,
        context_memories: list[dict] | None = None,
        cited_ids: list[str] | None = None,
    ) -> dict:
        metrics = await self.memory_db.get_or_create(memory_id)
        now = datetime.now()
        synapse_ids_created: list[str] = []

        if cited_ids:
            for target_id in cited_ids:
                await self.memory_db.get_or_create(target_id)
                synapse = await self.synapse_db.get_or_create(
                    source_id=memory_id,
                    target_id=target_id,
                    citation_type=CitationType.EXPLICIT,
                    temporal_bias=0.0,
                )
                synapse_ids_created.append(synapse.id)
                await on_citation(
                    self.synapse_db,
                    memory_id,
                    target_id,
                    CitationType.EXPLICIT,
                    temporal_bias=0.0,
                )

        if context_memories and self.detector is not None:
            current_ctx = {"id": memory_id, "memory": content, "created_at": now.isoformat()}
            detected = await self.detector.detect_citations(
                content, [current_ctx, *context_memories], now
            )
            for source_id, target_id, citation_type, strength_boost, temporal_bias in detected:
                await self.memory_db.get_or_create(source_id)
                await self.memory_db.get_or_create(target_id)
                synapse = await self.synapse_db.get_or_create(
                    source_id=source_id,
                    target_id=target_id,
                    citation_type=citation_type,
                    temporal_bias=temporal_bias,
                )
                if synapse.id not in synapse_ids_created:
                    synapse_ids_created.append(synapse.id)
                await on_citation(
                    self.synapse_db,
                    source_id,
                    target_id,
                    citation_type,
                    temporal_bias=temporal_bias,
                )

        await apply_homeostatic_scaling(self.synapse_db, memory_id)

        updated = await self.memory_db.get(memory_id)
        outbound_count = await self.synapse_db.outbound_count(memory_id)

        return {
            "memory_id": memory_id,
            "content_length": len(content),
            "synapses_created": len(synapse_ids_created),
            "outbound_count": outbound_count,
            "importance_score": (updated or metrics).importance_score,
        }

    async def on_search(self, query: str, results: list[dict]) -> list[dict]:
        if not results:
            return results

        result_ids = [r["id"] for r in results if "id" in r]

        for rid in result_ids:
            await self.memory_db.get_or_create(rid)
            await self.memory_db.update_access(rid)

        for i in range(len(result_ids) - 1):
            source_id = result_ids[i]
            target_id = result_ids[i + 1]
            await self.synapse_db.get_or_create(
                source_id=source_id,
                target_id=target_id,
                citation_type=CitationType.RETRIEVAL,
                temporal_bias=0.0,
            )
            await on_citation(
                self.synapse_db,
                source_id,
                target_id,
                CitationType.RETRIEVAL,
                temporal_bias=0.0,
            )

        await track_co_citations(self.synapse_db, results)

        return results

    async def get_network(self, memory_id: str) -> dict:
        metrics = await self.memory_db.get(memory_id)
        inbound = await self.synapse_db.get_inbound(memory_id)
        outbound = await self.synapse_db.get_outbound(memory_id)

        def _synapse_dict(s: Synapse) -> dict:
            return {
                "id": s.id,
                "source_id": s.source_id,
                "target_id": s.target_id,
                "strength": s.strength,
                "citation_type": s.citation_type.value,
                "access_count": s.access_count,
                "co_citation_count": s.co_citation_count,
                "created_at": s.created_at.isoformat(),
                "last_accessed": s.last_accessed.isoformat(),
            }

        metrics_dict: dict = {}
        if metrics is not None:
            metrics_dict = {
                "incoming_strength": metrics.incoming_strength,
                "outgoing_strength": metrics.outgoing_strength,
                "total_strength": metrics.total_strength,
                "page_rank": metrics.page_rank,
                "hub_score": metrics.hub_score,
                "importance_score": metrics.importance_score,
                "total_access_count": metrics.total_access_count,
                "in_replay_buffer": metrics.in_replay_buffer,
                "replay_count": metrics.replay_count,
            }

        return {
            "memory_id": memory_id,
            "metrics": metrics_dict,
            "inbound": [_synapse_dict(s) for s in inbound],
            "outbound": [_synapse_dict(s) for s in outbound],
        }

    async def run_decay(self) -> dict:
        return await decay_all_synapses(self.synapse_db, self.memory_db)

    async def run_pagerank(self) -> dict[str, float]:
        return await calculate_network_centrality(
            self.synapse_db,
            self.memory_db,
            damping=0.85,
            iterations=50,
        )

    async def run_replay_check(self) -> list[dict]:
        if self.replay is None:
            raise RuntimeError("System not connected. Call connect() first.")
        await self.replay.populate_queue()
        return await self.replay.get_due_reviews()

    async def get_stats(self) -> dict:
        all_synapses = await self.synapse_db.get_all()
        all_memories = await self.memory_db.get_all()
        due_replays = await self.memory_db.get_due_replays(limit=100)
        weakening = await self.synapse_db.get_weakening(threshold=0.2)
        isolated = await self.memory_db.get_isolated()

        synapse_count = len(all_synapses)
        memory_count = len(all_memories)
        avg_strength = (
            sum(s.strength for s in all_synapses) / synapse_count
            if synapse_count > 0
            else 0.0
        )
        max_strength = max((s.strength for s in all_synapses), default=0.0)
        avg_pagerank = (
            sum(m.page_rank for m in all_memories) / memory_count
            if memory_count > 0
            else 0.0
        )
        avg_importance = (
            sum(m.importance_score for m in all_memories) / memory_count
            if memory_count > 0
            else 0.0
        )

        citation_type_counts: dict[str, int] = {}
        for s in all_synapses:
            ct = s.citation_type.value
            citation_type_counts[ct] = citation_type_counts.get(ct, 0) + 1

        return {
            "synapse_count": synapse_count,
            "memory_count": memory_count,
            "avg_strength": round(avg_strength, 4),
            "max_strength": round(max_strength, 4),
            "avg_pagerank": round(avg_pagerank, 6),
            "avg_importance": round(avg_importance, 4),
            "weakening_synapses": len(weakening),
            "isolated_memories": len(isolated),
            "due_replays": len(due_replays),
            "citation_type_counts": citation_type_counts,
        }
