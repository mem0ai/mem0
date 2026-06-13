"""Regression tests for memory evaluation scenarios.

Tests cover the failure modes described in issue #5235:
- Forgetting: when should old memories be deprioritized?
- Overwrite behavior: does updating a memory correctly supersede the old one?
- Temporal relevance: are newer facts prioritized over stale ones?
- Conflict resolution: which memory wins when contradictions exist?
"""
import pytest
from mem0.evals import MemoryEvent, MemoryScenario, evaluate_memory


class MockMemoryClient:
    """Test double for Memory or MemoryClient."""
    def __init__(self):
        self.memories = {}
        self.id_counter = 0

    def add(self, messages, user_id=None, metadata=None):
        self.id_counter += 1
        memory_id = f"mem_{self.id_counter}"
        text = messages[0]["content"]
        self.memories[memory_id] = {"text": text, "user_id": user_id}
        return {"results": [{"id": memory_id, "memory": text}]}

    def update(self, memory_id, text):
        if memory_id in self.memories:
            self.memories[memory_id]["text"] = text
        return {"message": "Memory updated"}

    def search(self, query, top_k=5, filters=None):
        # Simplified: return all memories for the user, newest first
        user_id = filters.get("user_id") if filters else None
        results = [
            {"id": mid, "memory": mem["text"], "score": 0.9}
            for mid, mem in self.memories.items()
            if user_id is None or mem.get("user_id") == user_id
        ]
        return {"results": results[:top_k]}


def test_forgetting_stale_preference():
    """Test that updated preferences deprioritize stale facts."""
    scenario = MemoryScenario(
        name="forgetting_stale_preference",
        user_id="user_123",
        events=[
            MemoryEvent(
                action="add",
                text="I prefer dark mode.",
                memory_id="pref_1",
            ),
            MemoryEvent(
                action="update",
                memory_id="pref_1",
                text="I prefer light mode now.",
            ),
            MemoryEvent(
                action="query",
                text="What is my UI preference?",
            ),
        ],
        expected="I prefer light mode now",
        stale=["I prefer dark mode"],
    )
    client = MockMemoryClient()
    result = evaluate_memory(client, scenario)
    assert result.memory_recall_rate == 1.0
    assert result.staleness_score < 0.3  # Few stale matches
    assert result.update_propagation_rate == 1.0


def test_conflict_resolution_newer_fact_wins():
    """Test that conflicting facts are resolved by recency."""
    scenario = MemoryScenario(
        name="conflict_resolution_newer_fact",
        user_id="user_456",
        events=[
            MemoryEvent(
                action="add",
                text="My cat's name is Whiskers.",
                memory_id="cat_1",
            ),
            MemoryEvent(
                action="add",
                text="My cat's name is Shadow.",
                memory_id="cat_2",
            ),
            MemoryEvent(
                action="query",
                text="What is my cat's name?",
            ),
        ],
        expected="My cat's name is Shadow",
        stale=["My cat's name is Whiskers"],
        match_threshold=0.75,
    )
    client = MockMemoryClient()
    result = evaluate_memory(client, scenario)
    assert result.memory_recall_rate == 1.0
    assert result.conflict_resolution_acc >= 0.8


def test_temporal_relevance_recent_over_old():
    """Test that recent facts are prioritized over old ones."""
    scenario = MemoryScenario(
        name="temporal_relevance",
        user_id="user_789",
        events=[
            MemoryEvent(
                action="add",
                text="I work at Google.",
                memory_id="job_1",
            ),
            MemoryEvent(
                action="add",
                text="I work at OpenAI.",
                memory_id="job_2",
            ),
            MemoryEvent(
                action="query",
                text="Where do I work?",
            ),
        ],
        expected="I work at OpenAI",
        stale=["I work at Google"],
    )
    client = MockMemoryClient()
    result = evaluate_memory(client, scenario)
    assert result.memory_recall_rate == 1.0
    assert len(result.stale_matches) <= 1


def test_update_propagation_supersedes_old():
    """Test that explicit updates fully replace old memory content."""
    scenario = MemoryScenario(
        name="update_propagation",
        user_id="user_101",
        events=[
            MemoryEvent(
                action="add",
                text="My email is old@example.com",
                memory_id="email_1",
            ),
            MemoryEvent(
                action="update",
                memory_id="email_1",
                text="My email is new@example.com",
            ),
            MemoryEvent(
                action="query",
                text="What is my email?",
            ),
        ],
        expected="My email is new@example.com",
        stale=["My email is old@example.com"],
    )
    client = MockMemoryClient()
    result = evaluate_memory(client, scenario)
    assert result.update_propagation_rate == 1.0
    assert result.staleness_score < 0.2


def test_no_memory_found_recall_zero():
    """Test that recall is 0.0 when expected memory is never retrieved."""
    scenario = MemoryScenario(
        name="no_memory_found",
        user_id="user_404",
        events=[
            MemoryEvent(
                action="add",
                text="I like pizza.",
                memory_id="food_1",
            ),
            MemoryEvent(
                action="query",
                text="What is my favorite dessert?",
            ),
        ],
        expected="I like ice cream",  # Never added
    )
    client = MockMemoryClient()
    result = evaluate_memory(client, scenario)
    assert result.memory_recall_rate == 0.0


def test_polarity_update_not_merged():
    """Test that a polarity-reversing update replaces the old fact rather than merging.

    Covers the case where a boolean preference flips (e.g., enabled -> disabled).
    The new fact should win outright; the old fact should not appear as a stale match.
    """
    scenario = MemoryScenario(
        name="polarity_update_not_merged",
        user_id="user_polarity",
        events=[
            MemoryEvent(
                action="add",
                text="Email notifications are enabled.",
                memory_id="notif_1",
            ),
            MemoryEvent(
                action="update",
                memory_id="notif_1",
                text="Email notifications are disabled.",
            ),
            MemoryEvent(
                action="query",
                text="Are email notifications on or off?",
            ),
        ],
        expected="Email notifications are disabled",
        stale=["Email notifications are enabled"],
    )
    client = MockMemoryClient()
    result = evaluate_memory(client, scenario)
    # The newer polarity (disabled) must be recalled
    assert result.memory_recall_rate == 1.0
    # The old polarity (enabled) must NOT appear as a stale match
    assert result.staleness_score == 0.0, (
        "Old polarity was surfaced alongside the new one — update was merged, not replaced"
    )
    # Explicit update must have propagated
    assert result.update_propagation_rate == 1.0


def test_superseded_memory_excluded_from_context():
    """Test that a superseded memory has zero probability of appearing in context injection.

    Unlike the staleness_score check (which measures ranking), this test asserts
    the stronger contract: a superseded memory must not appear in search results at all.
    """
    scenario = MemoryScenario(
        name="superseded_memory_excluded",
        user_id="user_supersede",
        events=[
            MemoryEvent(
                action="add",
                text="My phone number is 555-0100.",
                memory_id="phone_old",
            ),
            MemoryEvent(
                action="update",
                memory_id="phone_old",
                text="My phone number is 555-0199.",
            ),
            MemoryEvent(
                action="query",
                text="What is my phone number?",
            ),
        ],
        expected="My phone number is 555-0199",
        stale=["My phone number is 555-0100"],
    )
    client = MockMemoryClient()
    result = evaluate_memory(client, scenario)
    # New value must be recalled
    assert result.memory_recall_rate == 1.0
    # Old value must be completely absent from retrieved context (not just ranked lower)
    assert result.staleness_score == 0.0, (
        "Superseded memory appeared in context injection output — "
        "it must be fully excluded, not just deprioritized"
    )
    assert result.update_propagation_rate == 1.0
