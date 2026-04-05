import json
import os
from unittest.mock import MagicMock

from mem0 import Memory


USER = os.environ.get("CONFLICT_USER", "alice")


def _make_memory(strategy: str):
    config = {
        "llm": {
            "provider": "openai",
            "config": {"model": "gpt-4o-mini"},
        },
        "conflict_detection": {
            "similarity_threshold": 0.70,
            "auto_resolve_strategy": strategy,
            "hitl_enabled": False,
        },
    }
    return Memory.from_config(config)


def _make_mock_memory(strategy: str, proposed_action: str):
    """
    Build a Memory instance with a mock LLM that returns a controlled
    proposed_action value.  Used by the follow-llm e2e scenario tests.
    """
    from unittest.mock import MagicMock, patch

    with patch("mem0.utils.factory.EmbedderFactory.create") as mock_emb, \
         patch("mem0.utils.factory.VectorStoreFactory.create") as mock_vs, \
         patch("mem0.utils.factory.LlmFactory.create") as mock_llm_factory, \
         patch("mem0.memory.storage.SQLiteManager"):

        mock_emb.return_value.embed.return_value = [0.1, 0.2, 0.3]

        old_mem = MagicMock()
        old_mem.id = "old-mem-uuid"
        old_mem.payload = {"data": "User is vegetarian"}
        old_mem.score = 0.92
        mock_vs_instance = MagicMock()
        mock_vs_instance.search.return_value = [old_mem]
        mock_vs.side_effect = [mock_vs_instance, MagicMock()]

        mock_llm = MagicMock()
        mock_llm_factory.return_value = mock_llm

        memory = Memory()

    memory.config.conflict_detection.auto_resolve_strategy = strategy
    memory.config.conflict_detection.hitl_enabled = False
    memory.config.conflict_detection.similarity_threshold = 0.70
    memory._delete_memory = MagicMock(return_value="old-mem-uuid")
    memory._create_memory = MagicMock(return_value="new-mem-uuid")

    # Wire the mock LLM to return controlled classification with the given proposed_action
    memory.llm.generate_response.side_effect = [
        '{"facts": ["User eats steak"]}',
        json.dumps({
            "conflict_class": "CONTRADICTION",
            "explanation": "conflicting dietary info",
            "proposed_action": proposed_action,
            "confidence_new": 0.5,
            "confidence_old": 0.5,
        }),
    ]
    return memory


def run_keep_higher_confidence_demo():
    m = _make_memory("keep-higher-confidence")
    m.add("I live in New York City", user_id=USER)
    print("[keep-higher-confidence] after first add:", m.get_all(user_id=USER))
    m.add("I moved to San Francisco last month.", user_id=USER)
    print("[keep-higher-confidence] after contradiction:", m.get_all(user_id=USER))


def run_delete_old_demo():
    m = _make_memory("delete-old")
    m.add("User is a strict vegetarian and never eats meat", user_id=USER)
    print("[delete-old] after first add:", m.get_all(user_id=USER))
    m.add("User eats chicken and steak regularly", user_id=USER)
    print("[delete-old] after contradiction:", m.get_all(user_id=USER))


def test_follow_llm_keep_new_routes_correctly():
    """
    follow-llm strategy: LLM returns proposed_action=KEEP_NEW →
    _delete_memory called once, _create_memory called once.
    """
    memory = _make_mock_memory("follow-llm", "KEEP_NEW")
    memory._add_to_vector_store(
        messages=[{"role": "user", "content": "I eat steak"}],
        metadata={}, filters={}, infer=True,
    )
    assert memory._delete_memory.call_count == 1, "expected _delete_memory to be called once"
    assert memory._create_memory.call_count == 1, "expected _create_memory to be called once"
    print("[follow-llm KEEP_NEW] ✓ delete + create called as expected")


def test_follow_llm_keep_old_routes_correctly():
    """
    follow-llm strategy: LLM returns proposed_action=KEEP_OLD →
    neither _delete_memory nor _create_memory called.
    """
    memory = _make_mock_memory("follow-llm", "KEEP_OLD")
    memory._add_to_vector_store(
        messages=[{"role": "user", "content": "I eat steak"}],
        metadata={}, filters={}, infer=True,
    )
    assert memory._delete_memory.call_count == 0, "expected _delete_memory NOT to be called"
    assert memory._create_memory.call_count == 0, "expected _create_memory NOT to be called"
    print("[follow-llm KEEP_OLD] ✓ neither delete nor create called as expected")


def test_follow_llm_delete_old_routes_correctly():
    """
    follow-llm strategy: LLM returns proposed_action=DELETE_OLD →
    _delete_memory called once, _create_memory NOT called.
    """
    memory = _make_mock_memory("follow-llm", "DELETE_OLD")
    memory._add_to_vector_store(
        messages=[{"role": "user", "content": "I eat steak"}],
        metadata={}, filters={}, infer=True,
    )
    assert memory._delete_memory.call_count == 1, "expected _delete_memory to be called once"
    assert memory._create_memory.call_count == 0, "expected _create_memory NOT to be called"
    print("[follow-llm DELETE_OLD] ✓ only delete called as expected")


def run_follow_llm_demo():
    """
    Live demo of follow-llm strategy. Requires OPENAI_API_KEY and a real memory.
    The LLM's own proposed_action from classification drives the resolution.
    """
    m = _make_memory("follow-llm")
    m.add("User is a strict vegetarian and never eats meat", user_id=USER)
    print("[follow-llm] after first add:", m.get_all(user_id=USER))
    m.add("User eats chicken and steak regularly", user_id=USER)
    print("[follow-llm] after contradiction:", m.get_all(user_id=USER))


if __name__ == "__main__":
    run_keep_higher_confidence_demo()
    run_delete_old_demo()
    run_follow_llm_demo()
