"""Tests for SynapseDB — async SQLite store for synapses."""

import pytest

from synaptic_memory.models import CitationType
from synaptic_memory.synapse_db import SynapseDB


@pytest.mark.asyncio
async def test_get_or_create_new(synapse_db: SynapseDB):
    """Creating a synapse returns correct source/target and default strength."""
    synapse = await synapse_db.get_or_create("a", "b")
    assert synapse.source_id == "a"
    assert synapse.target_id == "b"
    assert synapse.strength == 0.1
    assert synapse.citation_type == CitationType.RETRIEVAL


@pytest.mark.asyncio
async def test_get_or_create_existing(synapse_db: SynapseDB):
    """Getting an existing pair returns the same synapse, not a duplicate."""
    s1 = await synapse_db.get_or_create("a", "b")
    s2 = await synapse_db.get_or_create("a", "b")
    assert s1.id == s2.id


@pytest.mark.asyncio
async def test_get_by_pair(synapse_db: SynapseDB):
    """Lookup by (source, target) pair; reversed pair returns None."""
    await synapse_db.get_or_create("x", "y")
    result = await synapse_db.get_by_pair("x", "y")
    assert result is not None
    assert result.source_id == "x"

    missing = await synapse_db.get_by_pair("y", "x")
    assert missing is None


@pytest.mark.asyncio
async def test_update_strength(synapse_db: SynapseDB):
    """Updating strength persists the new value."""
    s = await synapse_db.get_or_create("a", "b")
    await synapse_db.update_strength(s.id, strength=0.8)

    updated = await synapse_db.get(s.id)
    assert updated is not None
    assert abs(updated.strength - 0.8) < 1e-6


@pytest.mark.asyncio
async def test_strength_clamped(synapse_db: SynapseDB):
    """Strength values above 1.0 are clamped to 1.0."""
    s = await synapse_db.get_or_create("a", "b")
    await synapse_db.update_strength(s.id, strength=1.5)

    updated = await synapse_db.get(s.id)
    assert updated is not None
    assert updated.strength <= 1.0


@pytest.mark.asyncio
async def test_inbound_outbound(synapse_db: SynapseDB):
    """Inbound/outbound queries return correct synapses."""
    await synapse_db.get_or_create("a", "b")
    await synapse_db.get_or_create("a", "c")
    await synapse_db.get_or_create("d", "b")

    outbound_a = await synapse_db.get_outbound("a")
    assert len(outbound_a) == 2

    inbound_b = await synapse_db.get_inbound("b")
    assert len(inbound_b) == 2

    count = await synapse_db.outbound_count("a")
    assert count == 2


@pytest.mark.asyncio
async def test_get_weakening(synapse_db: SynapseDB):
    """Weakening synapses (below threshold, above dead) are returned."""
    s = await synapse_db.get_or_create("a", "b")
    await synapse_db.update_strength(s.id, strength=0.15)

    weak = await synapse_db.get_weakening(threshold=0.2)
    assert len(weak) == 1
    assert weak[0].id == s.id


@pytest.mark.asyncio
async def test_delete_below_threshold(synapse_db: SynapseDB):
    """Dead synapses below threshold are deleted."""
    s = await synapse_db.get_or_create("a", "b")
    await synapse_db.update_strength(s.id, strength=0.005)

    deleted = await synapse_db.delete_below_threshold(0.01)
    assert deleted >= 1

    remaining = await synapse_db.get_all()
    assert len(remaining) == 0


@pytest.mark.asyncio
async def test_get_all_memory_ids(synapse_db: SynapseDB):
    """All unique memory IDs from both source and target are returned."""
    await synapse_db.get_or_create("a", "b")
    await synapse_db.get_or_create("b", "c")

    ids = await synapse_db.get_all_memory_ids()
    assert ids == {"a", "b", "c"}
