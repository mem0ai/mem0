"""Tests for PageRank + HITS network centrality."""

import pytest

from synaptic_memory.memory_db import MemoryMetricsDB
from synaptic_memory.pagerank import calculate_network_centrality
from synaptic_memory.synapse_db import SynapseDB


@pytest.mark.asyncio
async def test_empty_graph(synapse_db: SynapseDB, memory_db: MemoryMetricsDB):
    """Empty graph returns empty scores."""
    scores = await calculate_network_centrality(synapse_db, memory_db)
    assert scores == {}


@pytest.mark.asyncio
async def test_simple_chain(synapse_db: SynapseDB, memory_db: MemoryMetricsDB):
    """A -> B -> C: C should have highest PageRank."""
    await synapse_db.get_or_create("a", "b")
    await synapse_db.get_or_create("b", "c")

    scores = await calculate_network_centrality(synapse_db, memory_db)

    assert "a" in scores
    assert "b" in scores
    assert "c" in scores
    assert scores["c"] > scores["a"]


@pytest.mark.asyncio
async def test_hub_topology(synapse_db: SynapseDB, memory_db: MemoryMetricsDB):
    """Hub A -> B, A -> C, A -> D: A should have high hub score."""
    for target in ["b", "c", "d"]:
        await synapse_db.get_or_create("a", target)

    scores = await calculate_network_centrality(synapse_db, memory_db)

    assert "a" in scores

    metrics_a = await memory_db.get("a")
    assert metrics_a is not None
    assert metrics_a.hub_score > 0


@pytest.mark.asyncio
async def test_convergence(synapse_db: SynapseDB, memory_db: MemoryMetricsDB):
    """PageRank should converge within tolerance."""
    await synapse_db.get_or_create("a", "b")
    await synapse_db.get_or_create("b", "c")
    await synapse_db.get_or_create("c", "a")

    scores_30 = await calculate_network_centrality(synapse_db, memory_db, iterations=30)
    scores_50 = await calculate_network_centrality(synapse_db, memory_db, iterations=50)

    for key in scores_30:
        assert abs(scores_30[key] - scores_50[key]) < 0.01


@pytest.mark.asyncio
async def test_importance_updates_memory_db(synapse_db: SynapseDB, memory_db: MemoryMetricsDB):
    """Centrality calculation should update importance scores."""
    await synapse_db.get_or_create("a", "b")
    await synapse_db.get_or_create("c", "b")

    await calculate_network_centrality(synapse_db, memory_db)

    metrics_b = await memory_db.get("b")
    metrics_a = await memory_db.get("a")

    assert metrics_b is not None
    assert metrics_a is not None
    assert metrics_b.importance_score > 0
