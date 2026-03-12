#!/usr/bin/env python3
"""
Mem0 Platform -- Update Memory Tool
Updates an existing memory's text or metadata.

Usage:
    python update_memory.py --memory_id UUID --text "New text content"
    python update_memory.py --memory_id UUID --metadata '{"verified": true}'
    python update_memory.py --memory_id UUID --text "New text" --metadata '{"source": "correction"}'

Requires: MEM0_API_KEY environment variable
"""

import argparse
import json
import os
import sys

from mem0 import MemoryClient


def main():
    parser = argparse.ArgumentParser(description="Update a Mem0 Platform memory")
    parser.add_argument("--memory_id", required=True, help="Memory UUID to update")
    parser.add_argument("--text", help="New text content")
    parser.add_argument("--metadata", help="JSON string of metadata to update")

    args = parser.parse_args()

    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        print("Error: MEM0_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    client = MemoryClient(api_key=api_key)

    kwargs = {"memory_id": args.memory_id}
    if args.text:
        kwargs["text"] = args.text
    if args.metadata:
        kwargs["metadata"] = json.loads(args.metadata)

    if not args.text and not args.metadata:
        print("Error: Provide --text and/or --metadata", file=sys.stderr)
        sys.exit(1)

    result = client.update(**kwargs)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
