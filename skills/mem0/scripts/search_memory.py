#!/usr/bin/env python3
"""
Mem0 Platform -- Search Memory Tool
Searches memories by semantic query with optional filters.

Usage:
    python search_memory.py --query "dietary preferences" --user_id alice
    python search_memory.py --query "hobbies" --filters '{"OR": [{"user_id": "alice"}, {"agent_id": "sports"}]}'
    python search_memory.py --query "goals" --user_id alice --category finance --rerank
    python search_memory.py --query "name" --user_id alice --enable_graph

Requires: MEM0_API_KEY environment variable
"""

import argparse
import json
import os
import sys

from mem0 import MemoryClient


def main():
    parser = argparse.ArgumentParser(description="Search Mem0 Platform memories")
    parser.add_argument("--query", required=True, help="Search query")
    parser.add_argument("--user_id", help="User identifier (simple filter)")
    parser.add_argument("--filters", help="JSON string of V2 filters")
    parser.add_argument("--top_k", type=int, default=10, help="Number of results")
    parser.add_argument("--rerank", action="store_true", help="Enable reranking")
    parser.add_argument("--threshold", type=float, help="Minimum similarity threshold")
    parser.add_argument("--keyword_search", action="store_true", help="Use keyword search")
    parser.add_argument("--enable_graph", action="store_true", help="Include graph relations")
    parser.add_argument("--category", help="Filter by category (contains match)")

    args = parser.parse_args()

    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        print("Error: MEM0_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    client = MemoryClient(api_key=api_key)

    # Build kwargs
    kwargs = {"query": args.query, "top_k": args.top_k}

    if args.filters:
        kwargs["filters"] = json.loads(args.filters)
    elif args.user_id and args.category:
        kwargs["filters"] = {
            "AND": [
                {"user_id": args.user_id},
                {"categories": {"contains": args.category}},
            ]
        }
    elif args.user_id:
        kwargs["user_id"] = args.user_id

    if args.rerank:
        kwargs["rerank"] = True
    if args.threshold is not None:
        kwargs["threshold"] = args.threshold
    if args.keyword_search:
        kwargs["keyword_search"] = True
    if args.enable_graph:
        kwargs["enable_graph"] = True

    results = client.search(**kwargs)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
