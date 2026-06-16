"""Lightweight identity helpers (task_04 / ADR-003).

The MCP route is ``/mcp/{client_name}/sse/{user_id}``. Per ADR-003 the
``user_id`` segment carries the **machine hostname** and is used purely for
*attribution/audit* on the write path — it is NOT an access gate. Reads
(``search_memory``/``list_memories``) deliberately ignore identity and filter by
``project`` only, so two machines on the local network share everything.

This module centralizes how a raw ``user_id`` value is turned into a usable
hostname, including the decision for the PRD's open question of what to do when
the hostname is missing/blank: we fall back to a single, explicit sentinel
(:data:`DEFAULT_HOSTNAME`) instead of raising — a write must never fail just
because the caller omitted its hostname; attribution simply records the
sentinel.
"""

# Sentinel attribution used when the MCP caller provides no (or a blank)
# hostname in the ``user_id`` slot. Kept as a single well-known value so audit
# logs and the project catalog's ``first_seen_hostname`` stay queryable.
DEFAULT_HOSTNAME = "unknown-host"


def resolve_hostname(raw: str | None) -> str:
    """Normalize the raw ``user_id`` segment into a hostname for attribution.

    Args:
        raw: The value captured from the MCP route's ``user_id`` slot (or the
            ``user_id_var`` context var). May be ``None`` or blank.

    Returns:
        The trimmed hostname, or :data:`DEFAULT_HOSTNAME` when ``raw`` is
        ``None``/empty/whitespace. Never raises — attribution is best-effort and
        must not block a write.
    """
    if raw is None:
        return DEFAULT_HOSTNAME
    hostname = raw.strip()
    return hostname if hostname else DEFAULT_HOSTNAME
