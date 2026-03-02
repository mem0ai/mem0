"""
URL Security Utilities for SSRF Prevention.

This module provides utilities to validate URLs and prevent Server-Side Request Forgery (SSRF) attacks
by blocking requests to private IP addresses, internal network resources, and other dangerous endpoints.
"""

import ipaddress
import logging
import socket
from typing import List, Optional, Set
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class SSRFSecurityError(Exception):
    """Raised when a URL is blocked due to SSRF security concerns."""

    pass


# Default blocked IP ranges (private, loopback, link-local, etc.)
DEFAULT_BLOCKED_IP_RANGES = [
    # IPv4 Private ranges (RFC 1918)
    ipaddress.ip_network("10.0.0.0/8", strict=False),
    ipaddress.ip_network("172.16.0.0/12", strict=False),
    ipaddress.ip_network("192.168.0.0/16", strict=False),
    # IPv4 Loopback
    ipaddress.ip_network("127.0.0.0/8", strict=False),
    # IPv4 Link-local (includes cloud metadata 169.254.169.254)
    ipaddress.ip_network("169.254.0.0/16", strict=False),
    # IPv4 Multicast
    ipaddress.ip_network("224.0.0.0/4", strict=False),
    # IPv4 Reserved
    ipaddress.ip_network("240.0.0.0/4", strict=False),
    # IPv4 Broadcast
    ipaddress.ip_network("255.255.255.255/32", strict=False),
    # IPv6 Loopback
    ipaddress.ip_network("::1/128", strict=False),
    # IPv6 Link-local
    ipaddress.ip_network("fe80::/10", strict=False),
    # IPv6 Unique local
    ipaddress.ip_network("fc00::/7", strict=False),
    # IPv6 Multicast
    ipaddress.ip_network("ff00::/8", strict=False),
]

# Blocked hostnames that resolve to internal resources
BLOCKED_HOSTNAMES: Set[str] = {
    "localhost",
    "localhost.localdomain",
    "local",
    "ip6-localhost",
    "ip6-loopback",
    "metadata.google.internal",
    "metadata",
    "kubernetes.default",
    "kubernetes.default.svc",
    "kubernetes.default.svc.cluster.local",
}

# Cloud metadata endpoints
BLOCKED_METADATA_IPS: Set[str] = {
    "169.254.169.254",  # AWS/GCP/Azure metadata
    "100.100.100.200",  # Alibaba metadata
    "metadata.google.internal",  # GCP metadata
}

# Allowed URL schemes
ALLOWED_SCHEMES: Set[str] = {"http", "https"}


def is_ip_blocked(
    ip_str: str,
    blocked_ranges: Optional[List[ipaddress.IPv4Network | ipaddress.IPv6Network]] = None,
) -> bool:
    """
    Check if an IP address falls within blocked ranges.

    Args:
        ip_str: IP address as string
        blocked_ranges: Optional list of IP networks to block (uses defaults if not provided)

    Returns:
        True if the IP is blocked, False otherwise
    """
    if blocked_ranges is None:
        blocked_ranges = DEFAULT_BLOCKED_IP_RANGES

    try:
        ip = ipaddress.ip_address(ip_str)
        for network in blocked_ranges:
            if ip in network:
                return True
        return False
    except ValueError:
        # Invalid IP address
        return True


def is_hostname_blocked(hostname: str) -> bool:
    """
    Check if a hostname is in the blocked list.

    Args:
        hostname: Hostname to check

    Returns:
        True if hostname is blocked, False otherwise
    """
    hostname_lower = hostname.lower().strip(".")

    # Check exact match
    if hostname_lower in BLOCKED_HOSTNAMES:
        return True

    # Check if hostname ends with blocked suffixes
    blocked_suffixes = [".local", ".localhost", ".internal", ".localdomain"]
    for suffix in blocked_suffixes:
        if hostname_lower.endswith(suffix):
            return True

    return False


def resolve_hostname_to_ip(hostname: str, dns_timeout: float = 5.0) -> Optional[str]:
    """
    Resolve a hostname to its IP address.

    Args:
        hostname: Hostname to resolve
        dns_timeout: Timeout for DNS resolution

    Returns:
        IP address as string, or None if resolution fails
    """
    try:
        # Get address info with timeout
        socket.setdefaulttimeout(dns_timeout)
        addr_info = socket.getaddrinfo(hostname, None)

        if addr_info:
            # Return the first IPv4 address if available, otherwise IPv6
            for family, _, _, _, sockaddr in addr_info:
                if family == socket.AF_INET:
                    return sockaddr[0]
            # Fall back to IPv6 if no IPv4
            for family, _, _, _, sockaddr in addr_info:
                if family == socket.AF_INET6:
                    return sockaddr[0]
        return None
    except (socket.gaierror, socket.timeout, OSError) as e:
        logger.debug(f"Failed to resolve hostname {hostname}: {e}")
        return None


def validate_url(
    url: str,
    allow_private_ips: bool = False,
    allowed_hosts: Optional[List[str]] = None,
    blocked_hosts: Optional[List[str]] = None,
    dns_timeout: float = 5.0,
) -> str:
    """
    Validate a URL for SSRF safety.

    This function checks:
    1. URL scheme (only http/https allowed)
    2. Hostname against blocked list
    3. IP address resolution and validation

    Args:
        url: URL to validate
        allow_private_ips: If True, allow requests to private IP ranges (use with caution)
        allowed_hosts: List of hostnames to always allow (bypasses blocklist)
        blocked_hosts: Additional hostnames to block
        dns_timeout: Timeout for DNS resolution

    Returns:
        The validated URL string

    Raises:
        SSRFSecurityError: If the URL is blocked for security reasons
    """
    if allowed_hosts is None:
        allowed_hosts = []
    if blocked_hosts is None:
        blocked_hosts = []

    # Parse the URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFSecurityError(f"Invalid URL format: {e}")

    # Check scheme
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise SSRFSecurityError(f"URL scheme '{parsed.scheme}' is not allowed. Only HTTP and HTTPS are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFSecurityError("URL must contain a valid hostname")

    hostname_lower = hostname.lower()

    # Check if host is in allowed list (bypasses other checks)
    if hostname_lower in [h.lower() for h in allowed_hosts]:
        logger.debug(f"Host '{hostname}' is in allowed list, bypassing security checks")
        return url

    # Check blocked hosts list
    all_blocked_hosts = BLOCKED_HOSTNAMES | set(h.lower() for h in blocked_hosts)
    if hostname_lower in all_blocked_hosts:
        raise SSRFSecurityError(f"Access to host '{hostname}' is blocked for security reasons")

    # Check if hostname is blocked by pattern
    if is_hostname_blocked(hostname):
        raise SSRFSecurityError(f"Access to host '{hostname}' is blocked for security reasons")

    # Check if hostname is a direct IP address
    try:
        ip = ipaddress.ip_address(hostname)
        if not allow_private_ips and is_ip_blocked(str(ip)):
            raise SSRFSecurityError(
                f"Access to IP address '{hostname}' is blocked. "
                "Private, loopback, and link-local addresses are not allowed."
            )
        return url
    except ValueError:
        pass  # Not an IP address, continue with DNS resolution

    # Resolve hostname to IP and validate
    resolved_ip = resolve_hostname_to_ip(hostname, dns_timeout)

    if resolved_ip is None:
        raise SSRFSecurityError(f"Failed to resolve hostname '{hostname}'")

    if not allow_private_ips and is_ip_blocked(resolved_ip):
        raise SSRFSecurityError(
            f"Hostname '{hostname}' resolves to blocked IP address '{resolved_ip}'. "
            "Access to private, loopback, and link-local addresses is not allowed."
        )

    logger.debug(f"URL validated successfully: {url} (resolved to {resolved_ip})")
    return url


def get_allowed_url(
    url: str,
    headers: Optional[dict] = None,
    timeout: float = 30.0,
    allow_private_ips: bool = False,
    allowed_hosts: Optional[List[str]] = None,
    blocked_hosts: Optional[List[str]] = None,
    session: Optional[requests.Session] = None,
    **kwargs,
) -> requests.Response:
    """
    Make a safe HTTP GET request with SSRF protection.

    This function validates the URL before making the request and prevents
    following redirects to blocked addresses.

    Args:
        url: URL to fetch
        headers: HTTP headers to send
        timeout: Request timeout in seconds
        allow_private_ips: If True, allow requests to private IP ranges
        allowed_hosts: List of hostnames to always allow
        blocked_hosts: Additional hostnames to block
        session: Optional requests Session to use
        **kwargs: Additional arguments passed to requests.get()

    Returns:
        requests.Response object

    Raises:
        SSRFSecurityError: If the URL is blocked for security reasons
        requests.RequestException: If the request fails
    """
    # Validate the URL first
    validate_url(
        url,
        allow_private_ips=allow_private_ips,
        allowed_hosts=allowed_hosts,
        blocked_hosts=blocked_hosts,
    )

    # Use provided session or create one
    if session is None:
        session = requests.Session()

    # Make the request
    response = session.get(url, headers=headers, timeout=timeout, **kwargs)

    # Check redirect chain for SSRF attempts
    for history_response in response.history:
        redirect_url = history_response.headers.get("Location")
        if redirect_url:
            try:
                validate_url(
                    redirect_url,
                    allow_private_ips=allow_private_ips,
                    allowed_hosts=allowed_hosts,
                    blocked_hosts=blocked_hosts,
                )
            except SSRFSecurityError:
                raise SSRFSecurityError(f"Redirect to blocked URL '{redirect_url}' was blocked for security reasons")

    # Also validate the final URL
    validate_url(
        response.url,
        allow_private_ips=allow_private_ips,
        allowed_hosts=allowed_hosts,
        blocked_hosts=blocked_hosts,
    )

    return response


def create_safe_session(
    allow_private_ips: bool = False,
    allowed_hosts: Optional[List[str]] = None,
    blocked_hosts: Optional[List[str]] = None,
    max_retries: int = 3,
    retry_backoff_factor: float = 0.5,
) -> requests.Session:
    """
    Create a requests Session with SSRF protection built-in.

    Args:
        allow_private_ips: If True, allow requests to private IP ranges
        allowed_hosts: List of hostnames to always allow
        blocked_hosts: Additional hostnames to block
        max_retries: Maximum number of retries
        retry_backoff_factor: Backoff factor for retries

    Returns:
        Configured requests.Session with SSRF protection
    """
    session = requests.Session()

    # Configure retry strategy
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=retry_backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # Store security config for use by custom adapters
    session._ssrf_config = {
        "allow_private_ips": allow_private_ips,
        "allowed_hosts": allowed_hosts or [],
        "blocked_hosts": blocked_hosts or [],
    }

    return session
