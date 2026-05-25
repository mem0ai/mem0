#!/usr/bin/env python3
"""
End-to-end test for the SingleStore mem0 connector.

Requires:
  - SingleStore accessible (local via docker-compose or remote)
  - OPENAI_API_KEY set in environment (for embeddings)

Environment variables:
  SINGLESTORE_HOST     (default: 127.0.0.1)
  SINGLESTORE_PORT     (default: 3306)
  SINGLESTORE_USER     (default: root)
  SINGLESTORE_PASSWORD (required)
  SINGLESTORE_DATABASE (default: mem0db)
  OPENAI_API_KEY       (required)

Usage:
  pip install mem0ai singlestoredb openai
  export SINGLESTORE_PASSWORD=...
  export OPENAI_API_KEY=sk-...
  python test_e2e.py
"""
import os
import sys
import time

import singlestoredb as s2

HOST = os.environ.get("SINGLESTORE_HOST", "127.0.0.1")
PORT = int(os.environ.get("SINGLESTORE_PORT", "3306"))
USER = os.environ.get("SINGLESTORE_USER", "root")
PASSWORD = os.environ.get("SINGLESTORE_PASSWORD")
DATABASE = os.environ.get("SINGLESTORE_DATABASE", "mem0db")

if not PASSWORD:
    print("❌ SINGLESTORE_PASSWORD environment variable is required")
    sys.exit(1)

# Wait for SingleStore to be ready
print("⏳ Waiting for SingleStore to be ready...")
for attempt in range(30):
    try:
        conn = s2.connect(host=HOST, port=PORT, user=USER, password=PASSWORD)
        conn.cursor().execute("SELECT 1")
        conn.close()
        print("✅ SingleStore is ready")
        break
    except Exception:
        time.sleep(2)
else:
    print("❌ SingleStore did not become ready in time")
    sys.exit(1)

# Ensure database exists
conn = s2.connect(host=HOST, port=PORT, user=USER, password=PASSWORD)
cur = conn.cursor()
cur.execute(f"CREATE DATABASE IF NOT EXISTS {DATABASE}")
conn.commit()
conn.close()
print(f"✅ Database {DATABASE} ready")

# Now test mem0 with SingleStore
from mem0 import Memory

config = {
    "vector_store": {
        "provider": "singlestore",
        "config": {
            "host": HOST,
            "port": PORT,
            "user": USER,
            "password": PASSWORD,
            "database": DATABASE,
            "collection_name": "test_memories",
            "embedding_model_dims": 1536,
        },
    }
}

print("\n📦 Initializing mem0 with SingleStore backend...")
m = Memory.from_config(config)
print("✅ Memory initialized")

# Test 1: Add memories
print("\n--- Test 1: Add memories ---")
messages = [
    {"role": "user", "content": "I love hiking in the mountains on weekends."},
    {"role": "assistant", "content": "That sounds wonderful! Do you have a favorite trail?"},
    {"role": "user", "content": "Yes, I really enjoy the Appalachian Trail near my home in Virginia."},
]
result = m.add(messages, user_id="test_user")
print(f"✅ Added {len(result.get('results', []))} memories")
for r in result.get("results", []):
    print(f"   - [{r['event']}] {r['memory'][:80]}")

# Test 2: Search memories
print("\n--- Test 2: Search memories ---")
search_result = m.search("outdoor activities", user_id="test_user")
print(f"✅ Found {len(search_result.get('results', []))} results")
for r in search_result.get("results", []):
    print(f"   - (score={r.get('score', 'N/A'):.3f}) {r['memory'][:80]}")

# Test 3: Get all memories
print("\n--- Test 3: Get all memories ---")
all_memories = m.get_all(user_id="test_user")
print(f"✅ Total memories: {len(all_memories.get('results', []))}")

# Test 4: Update a memory
print("\n--- Test 4: Update a memory ---")
if all_memories.get("results"):
    mem_id = all_memories["results"][0]["id"]
    update_result = m.update(memory_id=mem_id, data="I love hiking and trail running in the mountains.")
    print(f"✅ Updated memory {mem_id[:8]}...")

# Test 5: Get history
print("\n--- Test 5: Memory history ---")
if all_memories.get("results"):
    mem_id = all_memories["results"][0]["id"]
    history = m.history(memory_id=mem_id)
    print(f"✅ History entries: {len(history)}")
    for h in history:
        print(f"   - [{h['event']}] {h.get('new_value', h.get('old_value', ''))[:60]}")

# Test 6: Delete a memory
print("\n--- Test 6: Delete a memory ---")
if all_memories.get("results") and len(all_memories["results"]) > 1:
    del_id = all_memories["results"][-1]["id"]
    m.delete(memory_id=del_id)
    print(f"✅ Deleted memory {del_id[:8]}...")

# Test 7: Reset
print("\n--- Test 7: Reset ---")
m.reset()
print("✅ Reset complete")

# Verify reset
final = m.get_all(user_id="test_user")
assert len(final.get("results", [])) == 0, "Reset failed — memories still exist"
print("✅ Verified: no memories after reset")

print("\n🎉 All tests passed!")
