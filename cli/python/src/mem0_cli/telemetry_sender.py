"""Standalone telemetry sender — runs as a detached subprocess.

Usage: python -m mem0_cli.telemetry_sender '<json context>'

This module is spawned by telemetry.capture_event() and runs independently
of the parent CLI process. It:

1. Resolves the user's email via /v1/ping/ if not already cached
2. Caches the email in ~/.mem0/config.json for future runs
3. Sends the PostHog event

All errors are silently swallowed — this process must never produce output
or affect the user experience.
"""

from __future__ import annotations

import json
import sys
import urllib.request


def main() -> None:
    ctx = json.loads(sys.argv[1])
    payload = ctx["payload"]

    if ctx.get("needs_email") and ctx.get("mem0_api_key"):
        _resolve_and_cache_email(ctx, payload)

    # Fire $identify *after* email resolution so PostHog links the stored
    # anonymous id directly to the final identity (email, not the api-key
    # hash). The regular event is sent next so it lands under the merged
    # profile.
    anon_id = ctx.get("anon_distinct_id_to_alias")
    if anon_id:
        _send_identify_event(ctx, payload, anon_id)

    _send_posthog_event(ctx["posthog_host"], payload)


def _send_identify_event(ctx: dict, payload: dict, anon_id: str) -> None:
    """Send a PostHog $identify event aliasing anon_id → payload['distinct_id']."""
    identify_payload = {
        "api_key": payload["api_key"],
        "event": "$identify",
        "distinct_id": payload["distinct_id"],
        "properties": {
            "$anon_distinct_id": anon_id,
            "$lib": payload.get("properties", {}).get("$lib", "posthog-python"),
        },
    }
    _send_posthog_event(ctx["posthog_host"], identify_payload)


def _resolve_and_cache_email(ctx: dict, payload: dict) -> None:
    """Call /v1/ping/ to get the user's email, update the payload, and cache it."""
    try:
        ping_url = ctx["mem0_base_url"].rstrip("/") + "/v1/ping/"
        req = urllib.request.Request(
            ping_url,
            headers={
                "Authorization": "Token " + ctx["mem0_api_key"],
                "Content-Type": "application/json",
            },
        )
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        email = data.get("user_email")
        if email:
            payload["distinct_id"] = email
            _cache_email(ctx.get("config_path"), email)
    except Exception:
        pass


def _cache_email(config_path: str | None, email: str) -> None:
    """Write user_email into the config file for future runs."""
    if not config_path:
        return
    try:
        with open(config_path) as f:
            cfg = json.load(f)
        cfg.setdefault("platform", {})["user_email"] = email
        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def _send_posthog_event(posthog_host: str, payload: dict) -> None:
    """POST the event to PostHog."""
    try:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            posthog_host,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


if __name__ == "__main__":
    import contextlib

    with contextlib.suppress(Exception):
        main()
