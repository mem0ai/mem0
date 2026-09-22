"""Anonymous usage telemetry for the Strands memory store.

Events ride the Mem0 SDK's own PostHog client, so they need no extra dependency
and join the account's other Mem0 usage: on the hosted platform the distinct id
is the account email, and on a self-hosted OSS backend it is the machine-local
anonymous id the SDK already keeps. Unlike the SDK's OSS hot-path events these
are never sampled, because a store call is an agent-level action, not a loop.

Only names, counts, durations, and coarse failure kinds are sent: never queries,
memory text, message content, entity ids, metadata, or API keys.

Opt out with MEM0_TELEMETRY=false.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING, Any

from mem0.memory.telemetry import client_telemetry

if TYPE_CHECKING:
    from mem0_strands.client import Mem0ServiceClient

SOURCE = "STRANDS"

try:
    _VERSION = version("mem0-strands")
except PackageNotFoundError:  # pragma: no cover - only when running from a source tree
    _VERSION = "0.0.0+unknown"


def error_kind(exc: BaseException) -> str:
    """Coarse, content-free label for a failure, safe to send."""
    text = f"{type(exc).__name__}: {exc}".lower()
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "401" in text or "403" in text or "unauthor" in text or "forbidden" in text:
        return "auth"
    if "429" in text or "rate limit" in text:
        return "rate-limited"
    if any(code in text for code in ("500", "502", "503", "504")):
        return "server-error"
    if "400" in text or "422" in text:
        return "bad-request"
    return type(exc).__name__


def _distinct_id(client: Mem0ServiceClient) -> str | None:
    """The account email to attribute events to, or None to fall back to the SDK's anonymous id."""
    email = getattr(client.mem0, "user_email", None)
    return email if isinstance(email, str) and email else None


def record(event: str, client: Mem0ServiceClient, **properties: Any) -> None:
    """Send one strands.* usage event. Never raises."""
    try:
        client_telemetry.capture_event(
            f"strands.{event}",
            {
                "source": SOURCE,
                "language": "python",
                "strands_store_version": _VERSION,
                "backend": "platform" if client.is_platform else "oss",
                **properties,
            },
            _distinct_id(client),
        )
    except Exception:
        pass
