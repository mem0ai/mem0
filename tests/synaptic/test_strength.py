"""Tests for strength updates and homeostatic scaling."""

import pytest

from synaptic_memory.models import CitationType
from synaptic_memory.strength import (
    BOOSTS,
    MAX_TOTAL_OUTBOUND_STRENGTH,
    apply_homeostatic_scaling,
    on_citation,
)
from synaptic_memory.synapse_db import SynapseDB


@pytest.mark.asyncio
async def test_on_citation_creates_synapse(synapse_db: SynapseDB):
    """on_citation creates a synapse and applies the correct boost."""
    await on_citation(synapse_db, "a", "b", CitationType.RETRIEVAL)
    s = await synapse_db.get_by_pair("a", "b")
    assert s is not None
    expected = 0.1 + BOOSTS[CitationType.RETRIEVAL]
    assert abs(s.strength - expected) < 1e-6


@pytest.mark.asyncio
async def test_on_citation_explicit_boost(synapse_db: SynapseDB):
    """Explicit citation gives a bigger boost than retrieval."""
    await on_citation(synapse_db, "a", "b", CitationType.EXPLICIT)
    s = await synapse_db.get_by_pair("a", "b")
    assert s is not None
    assert s.strength > 0.1 + BOOSTS[CitationType.RETRIEVAL]


@pytest.mark.asyncio
async def test_on_citation_temporal_bias_positive(synapse_db: SynapseDB):
    """Source before target -> positive bias -> stronger boost."""
    await on_citation(synapse_db, "a", "b", CitationType.RETRIEVAL, temporal_bias=0.1)
    s = await synapse_db.get_by_pair("a", "b")
    assert s is not None
    expected = 0.1 + BOOSTS[CitationType.RETRIEVAL] * 1.1
    assert abs(s.strength - expected) < 1e-6


@pytest.mark.asyncio
async def test_on_citation_temporal_bias_negative(synapse_db: SynapseDB):
    """Source after target -> negative bias -> weaker boost."""
    await on_citation(synapse_db, "a", "b", CitationType.RETRIEVAL, temporal_bias=-0.05)
    s = await synapse_db.get_by_pair("a", "b")
    assert s is not None
    expected = 0.1 + BOOSTS[CitationType.RETRIEVAL] * 0.95
    assert s.strength < 0.1 + BOOSTS[CitationType.RETRIEVAL]


@pytest.mark.asyncio
async def test_homeostatic_scaling(synapse_db: SynapseDB):
    """Total outbound strength gets capped at MAX_TOTAL_OUTBOUND_STRENGTH."""
    for i in range(20):
        s = await synapse_db.get_or_create("hub", f"target-{i}")
        await synapse_db.update_strength(s.id, strength=1.0)

    await apply_homeostatic_scaling(synapse_db, "hub")

    outbound = await synapse_db.get_outbound("hub")
    total = sum(s.strength for s in outbound)
    assert total <= MAX_TOTAL_OUTBOUND_STRENGTH + 0.01


@pytest.mark.asyncio
async def test_homeostatic_no_scaling_when_under(synapse_db: SynapseDB):
    """No scaling when total is under the cap."""
    s = await synapse_db.get_or_create("a", "b")
    await synapse_db.update_strength(s.id, strength=0.5)

    await apply_homeostatic_scaling(synapse_db, "a")

    updated = await synapse_db.get(s.id)
    assert updated is not None
    assert abs(updated.strength - 0.5) < 1e-6


@pytest.mark.asyncio
async def test_strength_capped_at_one(synapse_db: SynapseDB):
    """Multiple citations should not push strength above 1.0."""
    for _ in range(5):
        await on_citation(synapse_db, "a", "b", CitationType.MANUAL)

    s = await synapse_db.get_by_pair("a", "b")
    assert s is not None
    assert s.strength <= 1.0
