"""Validation script: exercise full Mem0 CRUD lifecycle against a ScyllaDB cluster.

Usage:
    Set environment variables, then run:
        python examples/verify_scylla.py

Required environment variables:
    OPENAI_API_KEY          - OpenAI API key for embedding generation
    SCYLLA_CONTACT_POINTS   - Comma-separated list of node hostnames/IPs
                              e.g. "node-0.aws-eu-west-1.abc123.clusters.scylla.cloud"
    SCYLLA_USERNAME         - CQL username (default: scylla)
    SCYLLA_PASSWORD         - CQL password
    SCYLLA_KEYSPACE         - Keyspace name (default: mem0_test)
    SCYLLA_DATACENTER       - Datacenter name for DC-aware routing (optional)
"""

import os
import sys

from mem0 import Memory

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

openai_key = os.environ.get("OPENAI_API_KEY")
if not openai_key:
    sys.exit("ERROR: OPENAI_API_KEY is not set.")
os.environ["OPENAI_API_KEY"] = openai_key

contact_points_raw = os.environ.get("SCYLLA_CONTACT_POINTS", "127.0.0.1")
contact_points = [h.strip() for h in contact_points_raw.split(",")]

username = os.environ.get("SCYLLA_USERNAME", "scylla")
password = os.environ.get("SCYLLA_PASSWORD", "")
keyspace = os.environ.get("SCYLLA_KEYSPACE", "mem0_test")
datacenter = os.environ.get("SCYLLA_DATACENTER", "")

vector_config: dict = {
    "contact_points": contact_points,
    "port": 9042,
    "keyspace": keyspace,
    "collection_name": "agent_memories",
}
if username:
    vector_config["username"] = username
if password:
    vector_config["password"] = password
if datacenter:
    from cassandra.policies import DCAwareRoundRobinPolicy
    vector_config["load_balancing_policy"] = DCAwareRoundRobinPolicy(local_dc=datacenter)

config = {
    "vector_store": {
        "provider": "cassandra",
        "config": vector_config,
    }
}

TEST_USER = "verify_scylla_user"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def step(label: str) -> None:
    print(f"\n[{label}]")


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def fail(msg: str) -> None:
    print(f"  FAIL  {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

step("INIT")
print(f"  Connecting to ScyllaDB at {contact_points} ...")
memory = Memory.from_config(config)
ok("Memory layer initialized.")

# 1. CREATE
step("CREATE")
result = memory.add(
    "Prefers dark mode and custom keybindings in the IDE.",
    user_id=TEST_USER,
)
if not result:
    fail("add() returned an empty result.")
memory_id = result["results"][0]["id"] if isinstance(result, dict) else result[0]["id"]
ok(f"Memory added — id={memory_id}")

# 2. READ / SEARCH
step("SEARCH")
results = memory.search("What are the developer's IDE preferences?", user_id=TEST_USER)
if not results:
    fail("search() returned no results.")
ok(f"Search returned {len(results)} result(s).")

# 3. GET ALL
step("GET ALL")
all_memories = memory.get_all(user_id=TEST_USER)
if not all_memories:
    fail("get_all() returned no results.")
ok(f"get_all() returned {len(all_memories)} memory/memories.")

# 4. GET BY ID
step("GET BY ID")
fetched = memory.get(memory_id)
if not fetched:
    fail(f"get({memory_id}) returned nothing.")
ok(f"Fetched memory: {fetched}")

# 5. UPDATE
step("UPDATE")
memory.update(memory_id, "Prefers dark mode, custom keybindings, and Vim motions.")
updated = memory.get(memory_id)
if not updated:
    fail("get() after update returned nothing.")
ok("Memory updated successfully.")

# 6. DELETE
step("DELETE")
memory.delete(memory_id)
deleted = memory.get(memory_id)
if deleted:
    fail("Memory still exists after delete().")
ok("Memory deleted successfully.")

# 7. DELETE ALL (cleanup)
step("CLEANUP")
memory.delete_all(user_id=TEST_USER)
remaining = memory.get_all(user_id=TEST_USER)
if remaining:
    fail(f"delete_all() left {len(remaining)} record(s) behind.")
ok("All test memories removed.")

# ---------------------------------------------------------------------------
print("\n========================================")
print(" All validation stages passed! ")
print("========================================")
