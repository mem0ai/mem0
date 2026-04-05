"""
Interactive HITL terminal demo.

Spins up a Memory instance with hitl_enabled=True, stores a baseline memory,
then adds a contradicting fact so the HITL prompt appears in your terminal.

Usage:
    python tests/memory/manual/test_hitl_terminal.py

Optional env vars:
    CONFLICT_USER   user_id for the memory (default: "hitl-demo-user")
    OPENAI_API_KEY  required for real LLM + embeddings

To trigger a second conflict after the first (so you can test always:* session
overrides), the script runs two contradiction adds in a row.
"""
import os

from mem0 import Memory

USER = os.environ.get("CONFLICT_USER", "hitl-demo-user")
DB_PATH = os.environ.get("CONFLICT_DB_PATH", ":memory:")


def _extract_memories(get_all_result):
    if isinstance(get_all_result, dict):
        return get_all_result.get("results", [])
    if isinstance(get_all_result, list):
        return get_all_result
    return []


def _get_history_rows(db):
    cur = db.connection.execute(
        """
        SELECT id, memory_id, old_memory, new_memory, event,
               created_at, updated_at, is_deleted, actor_id, role
        FROM history
        ORDER BY rowid ASC
        """
    )
    rows = cur.fetchall()
    return [
        {
            "id": r[0],
            "memory_id": r[1],
            "old_memory": r[2],
            "new_memory": r[3],
            "event": r[4],
            "created_at": r[5],
            "updated_at": r[6],
            "is_deleted": bool(r[7]),
            "actor_id": r[8],
            "role": r[9],
        }
        for r in rows
    ]


def _print_history(rows, label):
    bar = "─" * 66
    print(f"\n  ┌{bar}┐")
    print(f"  │  SQLite history — {label:<47}│")
    print(f"  ├{bar}┤")
    if not rows:
        print(f"  │  (no rows written){'':<47}│")
    for i, row in enumerate(rows, 1):
        print(f"  │  [{i}] event      : {str(row['event']):<47}│")
        print(f"  │      memory_id  : {str(row['memory_id']):<47}│")
        print(f"  │      old_memory : {str(row['old_memory'] or '')[:47]:<47}│")
        print(f"  │      new_memory : {str(row['new_memory'] or '')[:47]:<47}│")
        print(f"  │      is_deleted : {str(row['is_deleted']):<47}│")
        print(f"  │      actor_id   : {str(row['actor_id']):<47}│")
        print(f"  │      role       : {str(row['role']):<47}│")
        print(f"  │      created_at : {str(row['created_at']):<47}│")
        if i < len(rows):
            print(f"  │{'':<66}│")
    print(f"  └{bar}┘")


def _reset_history_db(db):
    db.connection.execute("DELETE FROM history")
    try:
        db.connection.execute("DELETE FROM sqlite_sequence WHERE name = 'history'")
    except Exception:
        # sqlite_sequence may not exist depending on table definition.
        pass
    db.connection.commit()


def _reset_user_memories(memory_client, user_id):
    existing = _extract_memories(memory_client.get_all(user_id=user_id))
    for mem in existing:
        mem_id = mem.get("id")
        if mem_id:
            memory_client.delete(mem_id)


def main() -> None:
    config = {
        "llm": {
            "provider": "openai",
            "config": {"model": "gpt-4o-mini"},
        },
        "conflict_detection": {
            "similarity_threshold": 0.70,
            "hitl_enabled": True,
        },
        "history_db_path": DB_PATH,
    }
    m = Memory.from_config(config)
    _reset_user_memories(m, USER)
    _reset_history_db(m.db)

    print("\n=== Step 1: storing baseline memory ===")
    m.add("User is a strict vegetarian and never eats meat", user_id=USER)
    print("Baseline stored:", [x["memory"] for x in _extract_memories(m.get_all(user_id=USER))])
    _print_history(_get_history_rows(m.db), "after step 1")

    print("\n=== Step 2: adding first contradiction — HITL prompt will appear ===")
    m.add("User eats chicken and steak regularly", user_id=USER)
    print("After first conflict:", [x["memory"] for x in _extract_memories(m.get_all(user_id=USER))])
    _print_history(_get_history_rows(m.db), "after step 2")

    print("\n=== Step 3: adding second contradiction (tests session override if set) ===")
    m.add("User is vegan and avoids all animal products", user_id=USER)
    print("After second conflict:", [x["memory"] for x in _extract_memories(m.get_all(user_id=USER))])
    _print_history(_get_history_rows(m.db), "after step 3")


if __name__ == "__main__":
    main()
