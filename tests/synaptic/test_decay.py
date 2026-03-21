"""Tests for adaptive decay."""

from datetime import datetime, timedelta

import pytest

from synaptic_memory.decay import decay_all_synapses
from synaptic_memory.memory_db import MemoryMetricsDB
from synaptic_memory.synapse_db import SynapseDB


@pytest.mark.asyncio
async def test_decay_reduces_strength(synapse_db: SynapseDB, memory_db: MemoryMetricsDB):
    """Decay reduces strength of old synapses."""
    s = await synapse_db.get_or_create("a", "b")
    await synapse_db.update_strength(s.id, strength=0.8)

    old_time = datetime.now() - timedelta(days=30)
    await synapse_db.update_strength(s.id, last_accessed=old_time)

    stats = await decay_all_synapses(synapse_db, memory_db)
    assert stats["decayed"] >= 1

    updated = await synapse_db.get(s.id)
    assert updated is not None
    assert updated.strength < 0.8


@pytest.mark.asyncio
async def test_important_memories_decay_slower(synapse_db: SynapseDB, memory_db: MemoryMetricsDB):
    """Important memories (high importance_score) decay slower than normal ones."""
    s_important = await synapse_db.get_or_create("important", "target")
    s_normal = await synapse_db.get_or_create("normal", "target")

    await synapse_db.update_strength(s_important.id, strength=0.8)
    await synapse_db.update_strength(s_normal.id, strength=0.8)

    await memory_db.get_or_create("important")
    await memory_db.update_importance("important", 0.9)
    await memory_db.get_or_create("normal")
    await memory_db.update_importance("normal", 0.1)

    old_time = datetime.now() - timedelta(days=60)
    await synapse_db.update_strength(s_important.id, last_accessed=old_time)
    await synapse_db.update_strength(s_normal.id, last_accessed=old_time)

    await decay_all_synapses(synapse_db, memory_db)

    imp = await synapse_db.get(s_important.id)
    norm = await synapse_db.get(s_normal.id)

    assert imp is not None and norm is not None
    assert imp.strength > norm.strength


@pytest.mark.asyncio
async def test_decay_queues_replay_for_weak(synapse_db: SynapseDB, memory_db: MemoryMetricsDB):
    """Weakening synapses (<0.2) get queued for replay."""
    s = await synapse_db.get_or_create("a", "b")
    await synapse_db.update_strength(s.id, strength=0.15)

    old_time = datetime.now() - timedelta(days=5)
    await synapse_db.update_strength(s.id, last_accessed=old_time)

    stats = await decay_all_synapses(synapse_db, memory_db)
    updated = await synapse_db.get(s.id)
    if updated and updated.strength < 0.2:
        assert stats["queued_replay"] >= 1


@pytest.mark.asyncio
async def test_decay_deletes_dead_synapses(synapse_db: SynapseDB, memory_db: MemoryMetricsDB):
    """Synapses below dead threshold are deleted."""
    s = await synapse_db.get_or_create("a", "b")
    await synapse_db.update_strength(s.id, strength=0.005)

    old_time = datetime.now() - timedelta(days=100)
    await synapse_db.update_strength(s.id, last_accessed=old_time)

    stats = await decay_all_synapses(synapse_db, memory_db)
    assert stats["deleted"] >= 1

    remaining = await synapse_db.get_all()
    assert len(remaining) == 0
