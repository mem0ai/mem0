"""Persistent agent memory with Dakera and mem0.

Dakera is a self-hosted, decay-weighted vector memory server.  This example
shows how to wire it into mem0 as the vector store so every agent call gets
durable, semantically-searchable memory — without any cloud dependency.

Prerequisites
-------------
# 1. Start Dakera locally (replace <key> with your own key or use "demo")
docker run -d -p 3300:3300 \\
    -e DAKERA_API_KEY=demo \\
    ghcr.io/dakera-ai/dakera:latest

# 2. Install mem0
pip install mem0ai requests

Run
---
python examples/dakera_memory.py
"""

import os

from mem0 import Memory

# ---------------------------------------------------------------------------
# Configuration — point mem0 at your Dakera server
# ---------------------------------------------------------------------------

config = {
    "vector_store": {
        "provider": "dakera",
        "config": {
            "url": os.getenv("DAKERA_API_URL", "http://localhost:3300"),
            "api_key": os.getenv("DAKERA_API_KEY", "demo"),
            # collection_name maps to the agent_id namespace in Dakera.
            # Use a unique name per agent to keep memories isolated.
            "collection_name": "alice-assistant",
        },
    },
    # Dakera embeds text server-side, so we use a no-op embedder here.
    # mem0 still needs one configured to satisfy its internal checks.
    "embedder": {
        "provider": "openai",
        "config": {
            "model": "text-embedding-3-small",
        },
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": "gpt-4o-mini",
            "api_key": os.getenv("OPENAI_API_KEY", ""),
        },
    },
}

m = Memory.from_config(config)

# ---------------------------------------------------------------------------
# Session 1 — store facts about the user
# ---------------------------------------------------------------------------

print("=== Session 1: storing user preferences ===")

m.add("I prefer Python over JavaScript for backend work.", user_id="alice")
m.add("I always use dark mode in my IDE.", user_id="alice")
m.add("I'm working on a FastAPI service that handles payments.", user_id="alice")
m.add("My team uses GitHub Actions for CI/CD.", user_id="alice")

print("Stored 4 memories for alice.")

# ---------------------------------------------------------------------------
# Session 2 — recall semantically relevant facts
# ---------------------------------------------------------------------------

print("\n=== Session 2: recalling relevant memories ===")

results = m.search("What does Alice know about Python development?", user_id="alice")
print(f"\nRecalled {len(results['results'])} memories:")
for r in results["results"]:
    print(f"  [{r['score']:.3f}] {r['memory']}")

print("\nDone. Memories survive process restart — run again to see cross-session recall.")
