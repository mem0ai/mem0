#!/usr/bin/env python3
"""
Mem0 Platform -- Add Memory Tool
Adds memories from conversation messages via the Mem0 Platform API.

Usage:
    python add_memory.py --user_id USER_ID --message "message content"
    python add_memory.py --user_id USER_ID --messages_file messages.json
    python add_memory.py --user_id USER_ID --message "content" --enable_graph
    python add_memory.py --user_id USER_ID --message "content" --metadata '{"source": "cli"}'

Requires: MEM0_API_KEY environment variable
"""

import argparse
import json
import os
import sys

from mem0 import MemoryClient


def main():
    parser = argparse.ArgumentParser(description="Add memories to Mem0 Platform")
    parser.add_argument("--user_id", required=True, help="User identifier")
    parser.add_argument("--message", help="Single message content (role=user)")
    parser.add_argument("--messages_file", help="JSON file with messages array")
    parser.add_argument("--agent_id", help="Agent identifier")
    parser.add_argument("--run_id", help="Run/session identifier")
    parser.add_argument("--metadata", help="JSON string of metadata key-value pairs")
    parser.add_argument("--enable_graph", action="store_true", help="Enable graph memory (Pro plan)")
    parser.add_argument("--immutable", action="store_true", help="Make memory immutable")
    parser.add_argument("--expiration_date", help="Expiration date (YYYY-MM-DD)")
    parser.add_argument("--sync", action="store_true", help="Synchronous processing")
    parser.add_argument("--no_infer", action="store_true", help="Store text as-is without inference")

    args = parser.parse_args()

    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        print("Error: MEM0_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    client = MemoryClient(api_key=api_key)

    # Build messages
    if args.messages_file:
        with open(args.messages_file) as f:
            messages = json.load(f)
    elif args.message:
        messages = [{"role": "user", "content": args.message}]
    else:
        print("Error: Provide --message or --messages_file", file=sys.stderr)
        sys.exit(1)

    # Build kwargs
    kwargs = {"user_id": args.user_id}
    if args.agent_id:
        kwargs["agent_id"] = args.agent_id
    if args.run_id:
        kwargs["run_id"] = args.run_id
    if args.metadata:
        kwargs["metadata"] = json.loads(args.metadata)
    if args.enable_graph:
        kwargs["enable_graph"] = True
    if args.immutable:
        kwargs["immutable"] = True
    if args.expiration_date:
        kwargs["expiration_date"] = args.expiration_date
    if args.sync:
        kwargs["async_mode"] = False
    if args.no_infer:
        kwargs["infer"] = False

    result = client.add(messages, **kwargs)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
