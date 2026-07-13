"""Single transport owner for direct hosted Mem0 HTTP requests."""

from __future__ import annotations

import os
import urllib.request

from admission import AdmissionResult, admit


class HostedRequestDenied(RuntimeError):
    def __init__(self, result: AdmissionResult):
        self.result = result
        super().__init__(result.reason or "remote-request-denied")


def require_admission(
    operation: str,
    ingress: str,
    automatic: bool,
    *,
    payload_bytes: int = 0,
) -> AdmissionResult:
    """Admission bridge for hosted SDK calls that do not expose HTTP requests."""
    result = admit(
        operation,
        ingress,
        automatic,
        os.environ.get("MEM0_SESSION_ID", "default"),
        payload_bytes=payload_bytes,
    )
    if not result.admitted:
        raise HostedRequestDenied(result)
    return result


def _operation_for(request: urllib.request.Request) -> str:
    url = request.full_url.lower()
    method = request.get_method().upper()
    if "/search" in url:
        return "search"
    if method == "DELETE":
        return "delete"
    if "/add" in url or method == "POST":
        return "add" if "/add" in url else "list"
    if method in {"PUT", "PATCH"}:
        return "update"
    return "get"


def open_hosted_request(
    request: urllib.request.Request,
    *,
    timeout: float,
    ingress: str,
    automatic: bool,
    operation: str | None = None,
    session_id: str | None = None,
    charge_id: str | None = None,
    coalesce_key: str | None = None,
):
    """Charge atomically, then open a hosted HTTP request.

    The returned object is the ordinary ``urlopen`` response and can be used as
    a context manager. A denied request never reaches the network.
    """
    payload = request.data or b""
    result = admit(
        operation or _operation_for(request), ingress, automatic,
        session_id or os.environ.get("MEM0_SESSION_ID", "default"),
        payload_bytes=len(payload), charge_id=charge_id, coalesce_key=coalesce_key,
    )
    if not result.admitted:
        raise HostedRequestDenied(result)
    return urllib.request.urlopen(request, timeout=timeout)
