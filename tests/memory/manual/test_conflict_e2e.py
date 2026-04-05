import os

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


if __name__ == "__main__":
    run_keep_higher_confidence_demo()
    run_delete_old_demo()
