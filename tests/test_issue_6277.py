import sys
from unittest.mock import MagicMock, patch

sys.modules.setdefault("posthog", MagicMock())
sys.modules.setdefault("qdrant_client", MagicMock())

with patch("importlib.metadata.version", return_value="0.0.0"):
    from mem0 import Memory


class MockVectorMemory:
    def __init__(self, memory_id, payload):
        self.id = memory_id
        self.payload = payload


class InMemoryVectorStore:
    def __init__(self, memories):
        self.memories = memories

    def get(self, vector_id):
        return self.memories.get(vector_id)

    def update(self, vector_id, vector, payload):
        self.memories[vector_id].payload = payload

    def list(self, filters=None, top_k=None):
        filters = filters or {}
        results = [
            memory
            for memory in self.memories.values()
            if all(memory.payload.get(key) == value for key, value in filters.items())
        ]
        return results[:top_k]


def test_issue_6277():
    memory_id = "mem-1"
    vector_store = InMemoryVectorStore(
        {
            memory_id: MockVectorMemory(
                memory_id,
                {
                    "data": "I love pizza",
                    "user_id": "alice",
                    "agent_id": "agent-a",
                    "run_id": "run-a",
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "updated_at": "2024-01-01T00:00:00+00:00",
                },
            )
        }
    )

    with patch.object(Memory, "__init__", return_value=None):
        memory = Memory()

    memory.vector_store = vector_store
    memory.embedding_model = MagicMock()
    memory.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    memory.db = MagicMock()

    with (
        patch("mem0.memory.main.capture_event"),
        patch("mem0.memory.main.display_first_run_notice"),
    ):
        memory.update(
            memory_id,
            metadata={
                "category": "food",
                "user_id": "bob",
                "agent_id": "agent-b",
                "run_id": "run-b",
            },
        )

        alice_memories = memory.get_all(filters={"user_id": "alice"})["results"]
        bob_memories = memory.get_all(filters={"user_id": "bob"})["results"]

    assert len(alice_memories) == 1
    assert alice_memories[0]["id"] == memory_id
    assert alice_memories[0]["user_id"] == "alice"
    assert alice_memories[0]["agent_id"] == "agent-a"
    assert alice_memories[0]["run_id"] == "run-a"
    assert alice_memories[0]["metadata"]["category"] == "food"
    assert bob_memories == []
