#!/usr/bin/env python3
"""JSON CLI bridge for shell and MCP admission hooks."""

from __future__ import annotations

import argparse
import json
import os

from admission import admit


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    charge = subparsers.add_parser("charge")
    charge.add_argument("--operation", required=True)
    charge.add_argument("--ingress", required=True)
    charge.add_argument("--automatic", action="store_true")
    charge.add_argument("--session-id", default=os.environ.get("MEM0_SESSION_ID", "default"))
    charge.add_argument("--payload-bytes", type=int, default=0)
    charge.add_argument("--charge-id")
    charge.add_argument("--coalesce-key")
    args = parser.parse_args()

    result = admit(
        args.operation,
        args.ingress,
        args.automatic,
        args.session_id,
        payload_bytes=args.payload_bytes,
        charge_id=args.charge_id,
        coalesce_key=args.coalesce_key,
    )
    print(json.dumps(result.__dict__, sort_keys=True))
    return 0 if result.admitted else 2


if __name__ == "__main__":
    raise SystemExit(main())

