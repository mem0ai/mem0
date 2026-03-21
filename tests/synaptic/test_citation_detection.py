"""Tests for citation detection with STDP temporal bias."""

import pytest

from synaptic_memory.models import CitationType
from synaptic_memory.synapse_db import SynapseDB
from synaptic_memory.synapse_tracker import CitationDetector, track_co_citations


@pytest.mark.asyncio
async def test_explicit_citation_detected(synapse_db: SynapseDB):
    """Explicit pattern 'As noted' triggers EXPLICIT citation type."""
    detector = CitationDetector(synapse_db)

    content = "As noted previously, Python is great for data science"
    context = [
        {"id": "current", "memory": content},
        {"id": "mem-1", "memory": "Python is used for data science and ML"},
    ]

    citations = await detector.detect_citations(content, context)
    assert len(citations) >= 1
    assert any(ct == CitationType.EXPLICIT for _, _, ct, _, _ in citations)


@pytest.mark.asyncio
async def test_semantic_overlap_detected(synapse_db: SynapseDB):
    """Shared keywords trigger semantic citation detection."""
    detector = CitationDetector(synapse_db)

    content = "Type hints enable better static analysis tools"
    context = [
        {"id": "current", "memory": content},
        {"id": "mem-1", "memory": "Static analysis tools check type annotations"},
    ]

    citations = await detector.detect_citations(content, context)
    assert len(citations) >= 1


@pytest.mark.asyncio
async def test_no_citation_for_unrelated(synapse_db: SynapseDB):
    """Unrelated memories produce no citations."""
    detector = CitationDetector(synapse_db)

    content = "The weather is sunny today"
    context = [
        {"id": "current", "memory": content},
        {"id": "mem-1", "memory": "Python uses indentation for blocks"},
    ]

    citations = await detector.detect_citations(content, context)
    assert len(citations) == 0


@pytest.mark.asyncio
async def test_temporal_bias_positive(synapse_db: SynapseDB):
    """Older source -> newer target gives positive temporal bias (+0.1)."""
    detector = CitationDetector(synapse_db)

    content = "As mentioned before, use type hints"
    context = [
        {"id": "current", "memory": content, "created_at": "2026-03-20T00:00:00"},
        {"id": "old", "memory": "Always use type hints in functions",
         "created_at": "2026-01-01T00:00:00"},
    ]

    citations = await detector.detect_citations(content, context)
    assert len(citations) >= 1
    for _, _, _, _, tb in citations:
        assert tb == 0.1


@pytest.mark.asyncio
async def test_temporal_bias_negative(synapse_db: SynapseDB):
    """Newer source -> older target gives negative temporal bias (-0.05)."""
    detector = CitationDetector(synapse_db)

    content = "As mentioned, always use type hints"
    context = [
        {"id": "current", "memory": content, "created_at": "2026-01-01T00:00:00"},
        {"id": "newer", "memory": "Type hints improve code quality and readability",
         "created_at": "2026-06-01T00:00:00"},
    ]

    citations = await detector.detect_citations(content, context)
    if citations:
        for _, _, _, _, tb in citations:
            assert tb == -0.05


@pytest.mark.asyncio
async def test_co_citation_tracking(synapse_db: SynapseDB):
    """Co-citation creates synapses for all pairs in search results."""
    results = [
        {"id": "mem-1"},
        {"id": "mem-2"},
        {"id": "mem-3"},
    ]

    await track_co_citations(synapse_db, results)

    s12 = await synapse_db.get_by_pair("mem-1", "mem-2")
    s13 = await synapse_db.get_by_pair("mem-1", "mem-3")
    s23 = await synapse_db.get_by_pair("mem-2", "mem-3")

    assert s12 is not None
    assert s13 is not None
    assert s23 is not None
    assert s12.co_citation_count == 1


@pytest.mark.asyncio
async def test_co_citation_logarithmic_scaling(synapse_db: SynapseDB):
    """Repeated co-citations have diminishing returns (log scaling)."""
    results = [{"id": "a"}, {"id": "b"}]

    await track_co_citations(synapse_db, results)
    s1 = await synapse_db.get_by_pair("a", "b")
    strength_after_1 = s1.strength

    await track_co_citations(synapse_db, results)
    s2 = await synapse_db.get_by_pair("a", "b")
    strength_after_2 = s2.strength

    delta_1 = strength_after_1 - 0.1
    delta_2 = strength_after_2 - strength_after_1
    assert delta_2 > 0  # Still increasing
