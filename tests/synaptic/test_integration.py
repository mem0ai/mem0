"""Integration tests for SynapticMemorySystem."""

import pytest

from synaptic_memory.system import SynapticMemorySystem


@pytest.mark.asyncio
async def test_add_memory_basic(system: SynapticMemorySystem):
    """Adding a single memory returns correct metadata."""
    result = await system.add_memory("m1", "Hello world")
    assert result["memory_id"] == "m1"
    assert result["synapses_created"] == 0


@pytest.mark.asyncio
async def test_add_memory_with_citations(system: SynapticMemorySystem):
    """Adding memory with cited_ids creates explicit synapses."""
    await system.add_memory("m1", "Python supports type hints")
    result = await system.add_memory("m2", "Type hints help analysis", cited_ids=["m1"])

    assert result["synapses_created"] == 1
    assert result["outbound_count"] == 1


@pytest.mark.asyncio
async def test_add_memory_with_context(system: SynapticMemorySystem):
    """Adding memory with context_memories may detect citations."""
    await system.add_memory("m1", "Python is great")
    result = await system.add_memory(
        "m2",
        "As mentioned previously, Python helps productivity",
        context_memories=[
            {"id": "m1", "memory": "Python is great for productivity and development"},
        ],
    )
    assert result["synapses_created"] >= 0


@pytest.mark.asyncio
async def test_on_search_tracks_citations(system: SynapticMemorySystem):
    """on_search creates co-citation synapses between result pairs."""
    await system.add_memory("m1", "First memory")
    await system.add_memory("m2", "Second memory")

    results = await system.on_search("query", [
        {"id": "m1", "memory": "First"},
        {"id": "m2", "memory": "Second"},
    ])

    assert len(results) == 2

    s = await system.synapse_db.get_by_pair("m1", "m2")
    assert s is not None


@pytest.mark.asyncio
async def test_get_network(system: SynapticMemorySystem):
    """get_network returns inbound/outbound synapse info."""
    await system.add_memory("m1", "Source memory")
    await system.add_memory("m2", "Target memory", cited_ids=["m1"])

    net = await system.get_network("m1")
    assert net["memory_id"] == "m1"
    assert len(net["inbound"]) == 1


@pytest.mark.asyncio
async def test_run_pagerank(system: SynapticMemorySystem):
    """PageRank assigns highest score to most-cited memory."""
    await system.add_memory("m1", "A")
    await system.add_memory("m2", "B", cited_ids=["m1"])
    await system.add_memory("m3", "C", cited_ids=["m1"])

    scores = await system.run_pagerank()
    assert "m1" in scores
    assert scores["m1"] >= scores.get("m2", 0)


@pytest.mark.asyncio
async def test_run_decay(system: SynapticMemorySystem):
    """Decay cycle returns expected stat keys."""
    await system.add_memory("m1", "A")
    await system.add_memory("m2", "B", cited_ids=["m1"])

    stats = await system.run_decay()
    assert "decayed" in stats
    assert "queued_replay" in stats
    assert "deleted" in stats


@pytest.mark.asyncio
async def test_get_stats(system: SynapticMemorySystem):
    """get_stats returns system-wide metrics."""
    await system.add_memory("m1", "A")
    await system.add_memory("m2", "B", cited_ids=["m1"])

    stats = await system.get_stats()
    assert stats["synapse_count"] >= 1
    assert stats["memory_count"] >= 2
    assert "avg_strength" in stats
    assert "citation_type_counts" in stats


@pytest.mark.asyncio
async def test_full_workflow(system: SynapticMemorySystem):
    """End-to-end: add, search, pagerank, decay, replay."""
    await system.add_memory("m1", "Python supports type hints")
    await system.add_memory("m2", "Type hints enable static checking", cited_ids=["m1"])
    await system.add_memory("m3", "Static analysis improves code quality", cited_ids=["m2"])

    await system.on_search("type hints", [
        {"id": "m1"},
        {"id": "m2"},
        {"id": "m3"},
    ])

    scores = await system.run_pagerank()
    assert len(scores) >= 3

    stats = await system.run_decay()
    assert stats["decayed"] >= 0

    replays = await system.run_replay_check()
    assert isinstance(replays, list)

    final = await system.get_stats()
    assert final["synapse_count"] > 0
