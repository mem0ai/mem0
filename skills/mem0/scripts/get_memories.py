#!/usr/bin/env python3
"""
Mem0 Platform -- Get Memories Tool
Retrieves memories by ID, filters, or lists all for a given scope.

Usage:
    python get_memories.py --memory_id UUID
    python get_memories.py --user_id alice
    python get_memories.py --user_id alice --enable_graph
    python get_memories.py --filters '{"AND": [{"user_id": "alice"}, {"categories": {"contains": "finance"}}]}'
    python get_memories.py --user_id alice --page 1 --page_size 50
    python get_memories.py --history --memory_id UUID

Requires: MEM0_API_KEY environment variable
"""

import argparse
import json
import os
import sys

from mem0 import MemoryClient


def main():
    parser = argparse.ArgumentParser(description="Get Mem0 Platform memories")
    parser.add_argument("--memory_id", help="Specific memory UUID")
    parser.add_argument("--user_id", help="User identifier for get_all")
    parser.add_argument("--filters", help="JSON string of V2 filters for get_all")
    parser.add_argument("--enable_graph", action="store_true", help="Include graph data")
    parser.add_argument("--page", type=int, default=1, help="Page number")
    parser.add_argument("--page_size", type=int, default=100, help="Items per page")
    parser.add_argument("--history", action="store_true", help="Get memory history")

    args = parser.parse_args()

    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        print("Error: MEM0_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    client = MemoryClient(api_key=api_key)

    if args.history and args.memory_id:
        result = client.history(memory_id=args.memory_id)
    elif args.memory_id and not args.history:
        result = client.get(memory_id=args.memory_id)
    elif args.filters:
        kwargs = {
            "filters": json.loads(args.filters),
            "page": args.page,
            "page_size": args.page_size,
        }
        if args.enable_graph:
            kwargs["enable_graph"] = True
        result = client.get_all(**kwargs)
    elif args.user_id:
        kwargs = {
            "filters": {"AND": [{"user_id": args.user_id}]},
            "page": args.page,
            "page_size": args.page_size,
        }
        if args.enable_graph:
            kwargs["enable_graph"] = True
        result = client.get_all(**kwargs)
    else:
        print("Error: Provide --memory_id, --user_id, or --filters", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
