"""Async SQLite storage for Synapse objects."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiosqlite

from synaptic_memory.models import CitationType, Synapse

_SCHEMA = """
CREATE TABLE IF NOT EXISTS synapses (
    id                  TEXT PRIMARY KEY,
    source_id           TEXT NOT NULL,
    target_id           TEXT NOT NULL,
    strength            REAL NOT NULL DEFAULT 0.1,
    base_strength       REAL NOT NULL DEFAULT 0.1,
    created_at          TEXT NOT NULL,
    last_accessed       TEXT NOT NULL,
    last_strength_update TEXT NOT NULL,
    access_count        INTEGER NOT NULL DEFAULT 0,
    co_citation_count   INTEGER NOT NULL DEFAULT 0,
    decay_rate          REAL NOT NULL DEFAULT 0.01,
    citation_type       TEXT NOT NULL DEFAULT 'retrieval',
    temporal_bias       REAL NOT NULL DEFAULT 0.0,
    metadata            TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, target_id)
);

CREATE INDEX IF NOT EXISTS idx_synapses_source   ON synapses(source_id);
CREATE INDEX IF NOT EXISTS idx_synapses_target   ON synapses(target_id);
CREATE INDEX IF NOT EXISTS idx_synapses_strength ON synapses(strength);
CREATE INDEX IF NOT EXISTS idx_synapses_type     ON synapses(citation_type);
"""


def _now_iso() -> str:
    return datetime.now().isoformat()


def _row_to_synapse(row: aiosqlite.Row) -> Synapse:
    return Synapse(
        id=row["id"],
        source_id=row["source_id"],
        target_id=row["target_id"],
        strength=row["strength"],
        base_strength=row["base_strength"],
        created_at=datetime.fromisoformat(row["created_at"]),
        last_accessed=datetime.fromisoformat(row["last_accessed"]),
        last_strength_update=datetime.fromisoformat(row["last_strength_update"]),
        access_count=row["access_count"],
        co_citation_count=row["co_citation_count"],
        decay_rate=row["decay_rate"],
        citation_type=CitationType(row["citation_type"]),
        temporal_bias=row["temporal_bias"],
        metadata=json.loads(row["metadata"]),
    )


class SynapseDB:
    """Async SQLite-backed store for Synapse records."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db: Optional[aiosqlite.Connection] = None

    @property
    def db(self) -> aiosqlite.Connection:
        if self._db is None:
            raise RuntimeError("SynapseDB is not connected — call connect() first")
        return self._db

    async def connect(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def get(self, synapse_id: str) -> Optional[Synapse]:
        async with self.db.execute(
            "SELECT * FROM synapses WHERE id = ?", (synapse_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_synapse(row) if row else None

    async def get_by_pair(
        self, source_id: str, target_id: str
    ) -> Optional[Synapse]:
        async with self.db.execute(
            "SELECT * FROM synapses WHERE source_id = ? AND target_id = ?",
            (source_id, target_id),
        ) as cur:
            row = await cur.fetchone()
        return _row_to_synapse(row) if row else None

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    async def get_or_create(
        self,
        source_id: str,
        target_id: str,
        citation_type: CitationType = CitationType.RETRIEVAL,
        temporal_bias: float = 0.0,
    ) -> Synapse:
        existing = await self.get_by_pair(source_id, target_id)
        if existing is not None:
            return existing

        now = _now_iso()
        synapse_id = Synapse.new_id()
        await self.db.execute(
            """
            INSERT INTO synapses
                (id, source_id, target_id, strength, base_strength,
                 created_at, last_accessed, last_strength_update,
                 access_count, co_citation_count, decay_rate,
                 citation_type, temporal_bias, metadata)
            VALUES (?, ?, ?, 0.1, 0.1, ?, ?, ?, 0, 0, 0.01, ?, ?, '{}')
            """,
            (
                synapse_id,
                source_id,
                target_id,
                now,
                now,
                now,
                citation_type.value,
                temporal_bias,
            ),
        )
        await self.db.commit()

        result = await self.get(synapse_id)
        assert result is not None
        return result

    async def update_strength(
        self,
        synapse_id: str,
        *,
        strength: Optional[float] = None,
        last_accessed: Optional[datetime] = None,
        access_count: Optional[int] = None,
        co_citation_count: Optional[int] = None,
        last_strength_update: Optional[datetime] = None,
    ) -> None:
        sets: list[str] = []
        params: list[object] = []

        if strength is not None:
            clamped = max(0.0, min(1.0, strength))
            sets.append("strength = ?")
            params.append(clamped)
            sets.append("last_strength_update = ?")
            params.append(
                last_strength_update.isoformat()
                if last_strength_update is not None
                else _now_iso()
            )
        elif last_strength_update is not None:
            sets.append("last_strength_update = ?")
            params.append(last_strength_update.isoformat())

        if last_accessed is not None:
            sets.append("last_accessed = ?")
            params.append(last_accessed.isoformat())

        if access_count is not None:
            sets.append("access_count = ?")
            params.append(access_count)

        if co_citation_count is not None:
            sets.append("co_citation_count = ?")
            params.append(co_citation_count)

        if not sets:
            return

        params.append(synapse_id)
        await self.db.execute(
            f"UPDATE synapses SET {', '.join(sets)} WHERE id = ?",  # noqa: S608
            params,
        )
        await self.db.commit()

    # ------------------------------------------------------------------
    # Bulk queries
    # ------------------------------------------------------------------

    async def get_inbound(self, memory_id: str) -> list[Synapse]:
        async with self.db.execute(
            "SELECT * FROM synapses WHERE target_id = ?", (memory_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_synapse(r) for r in rows]

    async def get_outbound(self, memory_id: str) -> list[Synapse]:
        async with self.db.execute(
            "SELECT * FROM synapses WHERE source_id = ?", (memory_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_synapse(r) for r in rows]

    async def outbound_count(self, memory_id: str) -> int:
        async with self.db.execute(
            "SELECT COUNT(*) FROM synapses WHERE source_id = ?", (memory_id,)
        ) as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def get_all(self) -> list[Synapse]:
        async with self.db.execute("SELECT * FROM synapses") as cur:
            rows = await cur.fetchall()
        return [_row_to_synapse(r) for r in rows]

    async def get_weakening(self, threshold: float = 0.2) -> list[Synapse]:
        """Return synapses below threshold but above the dead-zone (> 0.01)."""
        async with self.db.execute(
            "SELECT * FROM synapses WHERE strength < ? AND strength > 0.01",
            (threshold,),
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_synapse(r) for r in rows]

    async def delete_below_threshold(self, threshold: float = 0.01) -> int:
        async with self.db.execute(
            "DELETE FROM synapses WHERE strength < ?", (threshold,)
        ) as cur:
            deleted = cur.rowcount
        await self.db.commit()
        return deleted

    async def get_all_memory_ids(self) -> set[str]:
        async with self.db.execute(
            "SELECT source_id, target_id FROM synapses"
        ) as cur:
            rows = await cur.fetchall()
        ids: set[str] = set()
        for row in rows:
            ids.add(row["source_id"])
            ids.add(row["target_id"])
        return ids
