"""URL validation helpers to mitigate SSRF via attacker-controlled provider URLs.

The OpenMemory config API accepts an ``ollama_base_url`` that the server later
dials when the memory client is used. Without validation, a caller can point it
at internal-only addresses (e.g. the cloud metadata endpoint
``http://169.254.169.254/``) and turn the server into an SSRF proxy. See
https://github.com/mem0ai/mem0/issues/6081.

These helpers enforce a scheme allowlist and reject hostnames that resolve to
private, loopback, link-local, or otherwise non-public IP ranges.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# Only plain HTTP(S) provider URLs are meaningful for Ollama-style endpoints.
ALLOWED_SCHEMES = ("http", "https")


class UnsafeURLError(ValueError):
    """Raised when a provided URL is malformed or points at a non-public host."""


def _is_disallowed_ip(ip: ipaddress._BaseAddress) -> bool:
    """Return True when the address is not a routable public address."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_public_base_url(url: str) -> str:
    """Validate that ``url`` is an http(s) URL pointing at a public host.

    Returns the URL unchanged when it is safe. Raises :class:`UnsafeURLError`
    when the scheme is not allowed, the host is missing, or the host resolves
    to a private/loopback/link-local/reserved address (SSRF guard).
    """
    if not isinstance(url, str) or not url.strip():
        raise UnsafeURLError("URL must be a non-empty string")

    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError(
            f"URL scheme '{parsed.scheme}' is not allowed; "
            f"use one of {ALLOWED_SCHEMES}"
        )

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError("URL must include a host")

    # If the host is a literal IP, validate it directly.
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        ip = None

    if ip is not None:
        if _is_disallowed_ip(ip):
            raise UnsafeURLError(
                f"URL host '{hostname}' resolves to a non-public address range"
            )
        return url

    # Otherwise resolve the hostname and check every returned address.
    try:
        addr_infos = socket.getaddrinfo(hostname, parsed.port or None)
    except socket.gaierror as exc:
        raise UnsafeURLError(f"URL host '{hostname}' could not be resolved") from exc

    for family, _type, _proto, _canonname, sockaddr in addr_infos:
        resolved = ipaddress.ip_address(sockaddr[0])
        if _is_disallowed_ip(resolved):
            raise UnsafeURLError(
                f"URL host '{hostname}' resolves to a non-public address "
                f"({resolved})"
            )

    return url
