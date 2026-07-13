#!/usr/bin/env python3
"""Budgeted SessionStart memory count helper."""

from __future__ import annotations

import json
import os
import urllib.request

from hosted_request import open_hosted_request
from load_settings import load_settings


def main() -> None:
    if not load_settings().get("auto_search", False):
        print("not-loaded")
        return
    api_key = os.environ.get("MEM0_API_KEY", "")
    user_id = os.environ.get("MEM0_RESOLVED_USER_ID", "default")
    app_id = os.environ.get("MEM0_PROJECT_ID", "")
    if not api_key:
        print("?")
        return
    if os.environ.get("MEM0_GLOBAL_SEARCH", "false") == "true":
        filters = {"OR": [{"user_id": "*"}]}
    else:
        filters = {"AND": [{"user_id": user_id}, {"app_id": app_id}]}
    body = json.dumps({"filters": filters}).encode()
    request = urllib.request.Request(
        "https://api.mem0.ai/v3/memories/?page=1&page_size=1",
        headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
        data=body,
        method="POST",
    )
    try:
        with open_hosted_request(
            request,
            timeout=5,
            ingress="session-count",
            automatic=True,
            operation="list",
            coalesce_key=f"session-count:{user_id}:{app_id}",
        ) as response:
            data = json.loads(response.read())
        if isinstance(data, dict) and "count" in data:
            print(data["count"])
        elif isinstance(data, list):
            print(len(data))
        else:
            print(0)
    except Exception:
        print("?")


if __name__ == "__main__":
    main()
