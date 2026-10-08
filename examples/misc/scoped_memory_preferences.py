"""
Scoped memory preferences with Mem0 Platform.

This example shows how to keep long-term memories from leaking across users,
apps, sessions, and agent-level rules. It uses a badminton venue recommender
because recommendation agents often mix personal preferences, negative
constraints, and domain-specific policies.

Setup:
    pip install -e .
    export MEM0_API_KEY="your-mem0-api-key"
    python examples/misc/scoped_memory_preferences.py

Optional cleanup for the demo app:
    python examples/misc/scoped_memory_preferences.py --cleanup

Re-run searches without creating new demo memories:
    python examples/misc/scoped_memory_preferences.py --skip-add
"""

from __future__ import annotations

import argparse
import os
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mem0 import MemoryClient

APP_ID = "scoped-memory-preferences-demo"
BADMINTON_RUN_ID = "badminton-venue-recommendation"
WORK_RUN_ID = "work-collaboration-preferences"
VENUE_AGENT_ID = "venue-recommender"


def require_api_key() -> None:
    if not os.getenv("MEM0_API_KEY"):
        raise SystemExit(
            "MEM0_API_KEY is not set. Create an API key in the Mem0 dashboard, "
            "then run: export MEM0_API_KEY='your-mem0-api-key'"
        )


def add_demo_memories(client: MemoryClient) -> None:
    """Write user and agent memories with explicit scopes."""

    alice_badminton_messages = [
        {
            "role": "user",
            "content": (
                "Badminton venue preference: I prefer quiet venues after 8 PM with wooden courts. "
                "Badminton venue constraint: do not recommend Smash Arena anymore because it is too noisy."
            ),
        }
    ]
    client.add(
        alice_badminton_messages,
        user_id="alice",
        app_id=APP_ID,
        run_id=BADMINTON_RUN_ID,
        metadata={"domain": "badminton", "preference_type": "venue"},
    )

    alice_work_messages = [
        {
            "role": "user",
            "content": (
                "Work collaboration preference: I prefer energetic rooms, lively brainstorming, "
                "and detailed meeting agendas before the session starts."
            ),
        }
    ]
    client.add(
        alice_work_messages,
        user_id="alice",
        app_id=APP_ID,
        run_id=WORK_RUN_ID,
        metadata={"domain": "work", "preference_type": "collaboration"},
    )

    bob_badminton_messages = [
        {
            "role": "user",
            "content": (
                "Badminton venue preference: I care most about low prices and venues near the subway. "
                "Noise does not bother me much."
            ),
        }
    ]
    client.add(
        bob_badminton_messages,
        user_id="bob",
        app_id=APP_ID,
        run_id=BADMINTON_RUN_ID,
        metadata={"domain": "badminton", "preference_type": "venue"},
    )

    agent_policy_messages = [
        {
            "role": "user",
            "content": (
                "Venue recommendation policy: treat explicit dislikes as hard constraints. "
                "If a user says not to recommend a venue, do not rank it above preferred venues."
            ),
        }
    ]
    client.add(
        agent_policy_messages,
        agent_id=VENUE_AGENT_ID,
        app_id=APP_ID,
        metadata={"domain": "badminton", "memory_type": "agent_policy"},
    )


def search_results(client: MemoryClient, query: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
    """Search scoped memories and normalize the Platform response shape."""

    response = client.search(query=query, filters=filters, top_k=5)
    if isinstance(response, dict):
        return response.get("results", [])
    return response


def print_memories(title: str, memories: list[dict[str, Any]]) -> None:
    print(f"\n{title}")
    print("-" * len(title))

    if not memories:
        print("No memories returned.")
        return

    for index, memory in enumerate(memories, start=1):
        text = memory.get("memory") or memory.get("text") or str(memory)
        score = memory.get("score")
        suffix = f" (score={score:.3f})" if isinstance(score, float) else ""
        print(f"{index}. {text}{suffix}")


def run_scoped_searches(client: MemoryClient) -> None:
    """Compare broad retrieval with scoped retrieval."""

    broad_alice_scope = {
        "AND": [
            {"user_id": "alice"},
            {"app_id": APP_ID},
            {
                "OR": [
                    {"run_id": BADMINTON_RUN_ID},
                    {"run_id": WORK_RUN_ID},
                ]
            },
        ]
    }
    alice_badminton_scope = {
        "AND": [
            {"user_id": "alice"},
            {"app_id": APP_ID},
            {"run_id": BADMINTON_RUN_ID},
            {"metadata": {"domain": "badminton"}},
        ]
    }
    alice_work_scope = {
        "AND": [
            {"user_id": "alice"},
            {"app_id": APP_ID},
            {"run_id": WORK_RUN_ID},
            {"metadata": {"domain": "work"}},
        ]
    }
    bob_badminton_scope = {
        "AND": [
            {"user_id": "bob"},
            {"app_id": APP_ID},
            {"run_id": BADMINTON_RUN_ID},
            {"metadata": {"domain": "badminton"}},
        ]
    }
    venue_agent_scope = {
        "AND": [
            {"agent_id": VENUE_AGENT_ID},
            {"app_id": APP_ID},
            {"metadata": {"memory_type": "agent_policy"}},
        ]
    }

    print_memories(
        "Broad Alice search: useful for audit, risky for a specific task",
        search_results(client, "What environment does Alice prefer?", broad_alice_scope),
    )
    print_memories(
        "Alice badminton scope: venue preferences only",
        search_results(
            client,
            "What are Alice's badminton venue preferences and constraints?",
            alice_badminton_scope,
        ),
    )
    print_memories(
        "Alice work scope: collaboration preferences only",
        search_results(
            client,
            "What work collaboration and meeting agenda preferences does Alice have?",
            alice_work_scope,
        ),
    )
    print_memories(
        "Bob badminton scope: Bob's preferences stay separate from Alice's",
        search_results(
            client,
            "What are Bob's badminton venue preferences?",
            bob_badminton_scope,
        ),
    )
    print_memories(
        "Agent policy scope: retrieve rules separately from user memories",
        search_results(client, "How should negative venue preferences affect ranking?", venue_agent_scope),
    )


def cleanup_demo_memories(client: MemoryClient) -> None:
    """Delete memories written for this demo app."""

    client.delete_all(app_id=APP_ID)
    print(f"Deleted demo memories for app_id={APP_ID}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Demonstrate scoped memory retrieval with Mem0.")
    parser.add_argument(
        "--skip-add",
        action="store_true",
        help="Only run scoped searches against memories that were already added.",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete memories for this demo app_id and exit.",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=5.0,
        help="Seconds to wait after adding memories before searching.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require_api_key()

    from mem0 import MemoryClient

    client = MemoryClient()

    if args.cleanup:
        cleanup_demo_memories(client)
        return

    if not args.skip_add:
        add_demo_memories(client)
        if args.wait > 0:
            print(f"Waiting {args.wait:g}s for memories to be indexed...")
            time.sleep(args.wait)

    run_scoped_searches(client)


if __name__ == "__main__":
    main()
