"""Demo: 1-hop graph expansion over LLM-asserted memory links.

This script demonstrates the PR that adds optional 1-hop graph expansion
at search time. It runs entirely offline — no LLM, no vector store, no
network access. A tiny in-memory stand-in is used to drive the algorithm
end-to-end so reviewers can quickly see the behaviour without setting up
any dependencies.

The scenario is the canonical multi-hop allergy case:

    Memory A: "Sarah told Alice she's allergic to peanuts."
    Memory B: "Alice baked peanut butter cookies for the party."

When Sarah's assistant asks "Can Sarah eat the cookies?", pure semantic
retrieval typically returns B (word overlap on "cookies" / "party") but
misses A (lexically distant). The LLM, at extraction time, has already
linked B -> A via ``linked_memory_ids`` — we just need to follow the edge.

Run with:

    python examples/misc/graph_expansion_demo.py
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Dict, List

from mem0.memory.graph_expansion import expand_with_links, make_vector_store_fetcher


# ---------------------------------------------------------------------------
# Tiny in-memory stand-in for a vector store.
# Only the interface used by graph_expansion.py is implemented.
# ---------------------------------------------------------------------------


class TinyStore:
    def __init__(self, memories: Dict[str, dict]):
        self._mem = memories

    def get(self, vector_id: str):
        payload = self._mem.get(vector_id)
        if payload is None:
            return None
        return SimpleNamespace(id=vector_id, payload=payload, score=None)


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------


def main() -> None:
    # Memory B links back to Memory A (LLM-asserted, stored in payload).
    memories = {
        "mem-A": {
            "data": "Sarah told Alice she's allergic to peanuts.",
        },
        "mem-B": {
            "data": "Alice baked peanut butter cookies for the party.",
            "linked_memory_ids": ["mem-A"],
        },
    }
    store = TinyStore(memories)

    # Simulated output of score_and_rank: pure semantic retrieval for query
    # "Can Sarah eat the cookies Alice baked for the party?" ranks B high
    # (word overlap) but fails to surface A.
    scored_results = [
        {
            "id": "mem-B",
            "score": 0.91,
            "payload": memories["mem-B"],
        },
    ]

    print("=" * 72)
    print("Baseline (pure semantic retrieval)")
    print("=" * 72)
    for c in scored_results:
        print(f"  {c['id']:<6}  score={c['score']:.3f}  {c['payload']['data']}")
    print()

    fetcher = make_vector_store_fetcher(store)
    expanded = expand_with_links(
        scored_results,
        fetcher,
        seed_k=5,
        max_links_per_seed=5,
        max_expanded=20,
        expansion_score_weight=0.85,
    )

    print("=" * 72)
    print("After 1-hop graph expansion (via linked_memory_ids)")
    print("=" * 72)
    for c in expanded:
        tag = " (expanded)" if c.get("_source") == "graph_expansion" else ""
        data = (c.get("payload") or {}).get("data", "")
        print(f"  {c['id']:<6}  score={c['score']:.3f}{tag}  {data}")
    print()

    expanded_ids = {c["id"] for c in expanded}
    if "mem-A" in expanded_ids:
        print("SUCCESS: bridging memory mem-A recovered via 1-hop expansion.")
    else:
        print("FAILURE: expected mem-A to be recovered but it was not.")


if __name__ == "__main__":
    main()
