"""Async SQLite store for per-memory metrics and replay queue."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from synaptic_memory.models import MemoryAugmented, ReplayItem


def _now_iso() -> str:
    return datetime.now().isoformat()


def _row_to_metrics(row: aiosqlite.Row) -> MemoryAugmented:
    last_accessed_raw = row["last_accessed"]
    last_accessed: Optional[datetime] = (
        datetime.fromisoformat(last_accessed_raw) if last_accessed_raw else None
    )
    updated_at_raw = row["updated_at"]
    updated_at = (
        datetime.fromisoformat(updated_at_raw) if updated_at_raw else datetime.now()
    )
    return MemoryAugmented(
        memory_id=row["memory_id"],
        incoming_strength=row["incoming_strength"],
        outgoing_strength=row["outgoing_strength"],
        total_strength=row["total_strength"],
        page_rank=row["page_rank"],
        hub_score=row["hub_score"],
        total_access_count=row["total_access_count"],
        last_accessed=last_accessed,
        decay_rate=row["decay_rate"],
        importance_score=row["importance_score"],
        in_replay_buffer=bool(row["in_replay_buffer"]),
        replay_count=row["replay_count"],
        replay_effectiveness=row["replay_effectiveness"],
        updated_at=updated_at,
    )


def _row_to_replay(row: aiosqlite.Row) -> ReplayItem:
    return ReplayItem(
        id=row["id"],
        memory_id=row["memory_id"],
        synapse_id=row["synapse_id"],
        priority=row["priority"],
        reason=row["reason"],
        created_at=datetime.fromisoformat(row["created_at"]),
        due_at=datetime.fromisoformat(row["due_at"]),
        presented_count=row["presented_count"],
        effectiveness_boost=row["effectiveness_boost"],
    )


_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_metrics (
    memory_id        TEXT PRIMARY KEY,
    incoming_strength REAL NOT NULL DEFAULT 0.0,
    outgoing_strength REAL NOT NULL DEFAULT 0.0,
    total_strength   REAL NOT NULL DEFAULT 0.0,
    page_rank        REAL NOT NULL DEFAULT 0.0,
    hub_score        REAL NOT NULL DEFAULT 0.0,
    total_access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed    TEXT,
    decay_rate       REAL NOT NULL DEFAULT 0.01,
    importance_score REAL NOT NULL DEFAULT 0.5,
    in_replay_buffer INTEGER NOT NULL DEFAULT 0,
    replay_count     INTEGER NOT NULL DEFAULT 0,
    replay_effectiveness REAL NOT NULL DEFAULT 0.0,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS replay_queue (
    id               TEXT PRIMARY KEY,
    memory_id        TEXT NOT NULL,
    synapse_id       TEXT,
    priority         REAL NOT NULL DEFAULT 0.0,
    reason           TEXT NOT NULL DEFAULT 'weakening',
    created_at       TEXT NOT NULL,
    due_at           TEXT NOT NULL,
    presented_count  INTEGER NOT NULL DEFAULT 0,
    effectiveness_boost REAL NOT NULL DEFAULT 0.0
);

CREATE INDEX IF NOT EXISTS idx_replay_priority ON replay_queue (priority DESC);
CREATE INDEX IF NOT EXISTS idx_replay_due_at   ON replay_queue (due_at);
"""


class MemoryMetricsDB:
    """Async SQLite store for per-memory metrics and replay queue."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db: Optional[aiosqlite.Connection] = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("MemoryMetricsDB is not connected — call connect() first")
        return self._db

    async def connect(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    # ------------------------------------------------------------------
    # Core memory metrics
    # ------------------------------------------------------------------

    async def get_or_create(self, memory_id: str) -> MemoryAugmented:
        existing = await self.get(memory_id)
        if existing is not None:
            return existing

        now = _now_iso()
        await self.db.execute(
            """
            INSERT INTO memory_metrics
                (memory_id, incoming_strength, outgoing_strength, total_strength,
                 page_rank, hub_score, total_access_count, last_accessed,
                 decay_rate, importance_score, in_replay_buffer, replay_count,
                 replay_effectiveness, updated_at)
            VALUES (?, 0.0, 0.0, 0.0, 0.0, 0.0, 0, NULL, 0.01, 0.5, 0, 0, 0.0, ?)
            """,
            (memory_id, now),
        )
        await self.db.commit()

        result = await self.get(memory_id)
        assert result is not None
        return result

    async def get(self, memory_id: str) -> Optional[MemoryAugmented]:
        async with self.db.execute(
            "SELECT * FROM memory_metrics WHERE memory_id = ?", (memory_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return None
        return _row_to_metrics(row)

    async def update_access(self, memory_id: str) -> None:
        now = _now_iso()
        await self.db.execute(
            """
            UPDATE memory_metrics
               SET total_access_count = total_access_count + 1,
                   last_accessed = ?,
                   updated_at = ?
             WHERE memory_id = ?
            """,
            (now, now, memory_id),
        )
        await self.db.commit()

    async def update_strengths(
        self, memory_id: str, *, incoming: float, outgoing: float
    ) -> None:
        now = _now_iso()
        await self.db.execute(
            """
            UPDATE memory_metrics
               SET incoming_strength = ?,
                   outgoing_strength = ?,
                   total_strength    = ?,
                   updated_at        = ?
             WHERE memory_id = ?
            """,
            (incoming, outgoing, incoming + outgoing, now, memory_id),
        )
        await self.db.commit()

    async def update_centrality(
        self, memory_id: str, *, page_rank: float, hub_score: float
    ) -> None:
        now = _now_iso()
        await self.db.execute(
            """
            UPDATE memory_metrics
               SET page_rank   = ?,
                   hub_score   = ?,
                   updated_at  = ?
             WHERE memory_id = ?
            """,
            (page_rank, hub_score, now, memory_id),
        )
        await self.db.commit()

    async def update_importance(self, memory_id: str, importance: float) -> None:
        now = _now_iso()
        decay_rate = 0.01 * (1.0 - importance * 0.5)
        await self.db.execute(
            """
            UPDATE memory_metrics
               SET importance_score = ?,
                   decay_rate       = ?,
                   updated_at       = ?
             WHERE memory_id = ?
            """,
            (importance, decay_rate, now, memory_id),
        )
        await self.db.commit()

    async def get_all(self) -> list[MemoryAugmented]:
        async with self.db.execute("SELECT * FROM memory_metrics") as cursor:
            rows = await cursor.fetchall()
        return [_row_to_metrics(r) for r in rows]

    async def get_isolated(
        self, min_connections: int = 2, max_centrality: float = 0.1
    ) -> list[MemoryAugmented]:
        """Return memories with low connectivity and low centrality."""
        async with self.db.execute(
            """
            SELECT * FROM memory_metrics
             WHERE (incoming_strength + outgoing_strength) < ?
               AND page_rank < ?
            """,
            (float(min_connections), max_centrality),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_metrics(r) for r in rows]

    # ------------------------------------------------------------------
    # Replay queue
    # ------------------------------------------------------------------

    async def add_to_replay(
        self,
        replay_id: str,
        memory_id: str,
        *,
        synapse_id: Optional[str],
        priority: float,
        reason: str,
        due_at: datetime,
    ) -> None:
        now = _now_iso()
        await self.db.execute(
            """
            INSERT OR REPLACE INTO replay_queue
                (id, memory_id, synapse_id, priority, reason,
                 created_at, due_at, presented_count, effectiveness_boost)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0.0)
            """,
            (replay_id, memory_id, synapse_id, priority, reason, now, due_at.isoformat()),
        )
        # Mark memory as in replay buffer
        await self.db.execute(
            "UPDATE memory_metrics SET in_replay_buffer = 1, updated_at = ? WHERE memory_id = ?",
            (now, memory_id),
        )
        await self.db.commit()

    async def get_due_replays(self, limit: int = 10) -> list[ReplayItem]:
        now = _now_iso()
        async with self.db.execute(
            """
            SELECT * FROM replay_queue
             WHERE due_at <= ?
             ORDER BY priority DESC
             LIMIT ?
            """,
            (now, limit),
        ) as cursor:
            rows = await cursor.fetchall()
        return [_row_to_replay(r) for r in rows]

    async def update_replay(self, replay_id: str, presented_count: int) -> None:
        await self.db.execute(
            """
            UPDATE replay_queue
               SET presented_count = ?
             WHERE id = ?
            """,
            (presented_count, replay_id),
        )
        await self.db.commit()

    async def delete_replay(self, replay_id: str) -> None:
        # Fetch memory_id so we can clear in_replay_buffer if no other entries
        async with self.db.execute(
            "SELECT memory_id FROM replay_queue WHERE id = ?", (replay_id,)
        ) as cursor:
            row = await cursor.fetchone()

        await self.db.execute("DELETE FROM replay_queue WHERE id = ?", (replay_id,))

        if row is not None:
            memory_id: str = row["memory_id"]
            async with self.db.execute(
                "SELECT COUNT(*) AS cnt FROM replay_queue WHERE memory_id = ?",
                (memory_id,),
            ) as cursor:
                count_row = await cursor.fetchone()
            remaining = count_row["cnt"] if count_row else 0
            if remaining == 0:
                now = _now_iso()
                await self.db.execute(
                    "UPDATE memory_metrics SET in_replay_buffer = 0, updated_at = ? WHERE memory_id = ?",
                    (now, memory_id),
                )

        await self.db.commit()
