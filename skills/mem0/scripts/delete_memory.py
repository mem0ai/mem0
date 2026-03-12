#!/usr/bin/env python3
"""
Mem0 Platform -- Delete Memory Tool
Deletes a specific memory or all memories for a given scope.

Usage:
    python delete_memory.py --memory_id UUID
    python delete_memory.py --delete_all --user_id alice
    python delete_memory.py --delete_all --agent_id nutrition-agent

Requires: MEM0_API_KEY environment variable
"""

import argparse
import json
import os
import sys

from mem0 import MemoryClient


def main():
    parser = argparse.ArgumentParser(description="Delete Mem0 Platform memories")
    parser.add_argument("--memory_id", help="Specific memory UUID to delete")
    parser.add_argument("--delete_all", action="store_true", help="Delete all memories for scope")
    parser.add_argument("--user_id", help="User scope for delete_all")
    parser.add_argument("--agent_id", help="Agent scope for delete_all")
    parser.add_argument("--app_id", help="App scope for delete_all")
    parser.add_argument("--run_id", help="Run scope for delete_all")

    args = parser.parse_args()

    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        print("Error: MEM0_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    client = MemoryClient(api_key=api_key)

    if args.memory_id:
        result = client.delete(memory_id=args.memory_id)
        print(json.dumps(result, indent=2, default=str))
    elif args.delete_all:
        kwargs = {}
        if args.user_id:
            kwargs["user_id"] = args.user_id
        elif args.agent_id:
            kwargs["agent_id"] = args.agent_id
        elif args.app_id:
            kwargs["app_id"] = args.app_id
        elif args.run_id:
            kwargs["run_id"] = args.run_id
        else:
            print("Error: Provide --user_id, --agent_id, --app_id, or --run_id with --delete_all", file=sys.stderr)
            sys.exit(1)
        result = client.delete_all(**kwargs)
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Error: Provide --memory_id or --delete_all", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
