"""Atomic, local admission control for hosted Mem0 requests.

Charges are monotonic attempts. They are committed before transport and are
never refunded, so the configured ceilings remain hard even when a process
dies or the provider result is unavailable.
"""

from __future__ import annotations

import math
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_LIMITS = {
    "session_requests": 12,
    "daily_requests": 50,
    "session_auto_requests": 6,
    "daily_auto_requests": 20,
    "session_weight": 30,
    "daily_weight": 120,
}

ENV_LIMITS = {
    "session_requests": "MEM0_BUDGET_SESSION_REQUESTS",
    "daily_requests": "MEM0_BUDGET_DAILY_REQUESTS",
    "session_auto_requests": "MEM0_BUDGET_SESSION_AUTO_REQUESTS",
    "daily_auto_requests": "MEM0_BUDGET_DAILY_AUTO_REQUESTS",
    "session_weight": "MEM0_BUDGET_SESSION_WEIGHT",
    "daily_weight": "MEM0_BUDGET_DAILY_WEIGHT",
}

SEARCH_OPERATIONS = {"search", "list", "get", "search_memories", "get_memories", "get_memory", "list_entities"}
WRITE_OPERATIONS = {"add", "update", "import", "add_memory", "update_memory"}


@dataclass(frozen=True)
class AdmissionResult:
    admitted: bool
    reason: str | None
    charge_id: str
    weight: int
    idempotent: bool = False


def operation_weight(operation: str, payload_bytes: int = 0) -> int:
    normalized = operation.lower()
    if normalized in SEARCH_OPERATIONS:
        return 1
    if normalized in WRITE_OPERATIONS:
        return 2 + math.ceil(max(0, payload_bytes) / 4096)
    if normalized.startswith("delete") or normalized.endswith("entities"):
        return 1
    return 3


def _limits() -> dict[str, int] | None:
    values: dict[str, int] = {}
    for key, default in DEFAULT_LIMITS.items():
        raw = os.environ.get(ENV_LIMITS[key], str(default))
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None
        if value < 0 or str(value) != str(raw).strip():
            return None
        values[key] = value
    return values


def _database_path() -> Path:
    root = Path(os.environ.get("MEM0_STATE_DIR", "~/.mem0")).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root / "admission.sqlite3"


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_database_path(), timeout=0.5, isolation_level=None)
    connection.execute("PRAGMA busy_timeout = 500")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS charges (
            charge_id TEXT PRIMARY KEY,
            operation TEXT NOT NULL,
            ingress TEXT NOT NULL,
            automatic INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            day_bucket TEXT NOT NULL,
            weight INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at REAL NOT NULL,
            coalesce_key TEXT
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS charges_session_idx ON charges(session_id, created_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS charges_day_idx ON charges(day_bucket, created_at)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS charges_coalesce_idx ON charges(coalesce_key, created_at)"
    )
    return connection


def _totals(connection: sqlite3.Connection, where: str, params: tuple) -> tuple[int, int]:
    row = connection.execute(
        f"SELECT COUNT(*), COALESCE(SUM(weight), 0) FROM charges WHERE {where}", params
    ).fetchone()
    return int(row[0]), int(row[1])


def admit(
    operation: str,
    ingress: str,
    automatic: bool,
    session_id: str,
    *,
    payload_bytes: int = 0,
    charge_id: str | None = None,
    coalesce_key: str | None = None,
    now: float | None = None,
) -> AdmissionResult:
    """Atomically admit and charge one hosted-memory attempt."""
    identifier = charge_id or str(uuid.uuid4())
    weight = operation_weight(operation, payload_bytes)
    limits = _limits()
    if limits is None:
        return AdmissionResult(False, "remote-invalid-budget-config", identifier, weight)

    timestamp = time.time() if now is None else now
    day_bucket = datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()
    session = session_id or os.environ.get("MEM0_SESSION_ID", "default") or "default"

    connection = None
    try:
        connection = _connect()
        connection.execute("BEGIN IMMEDIATE")

        existing = connection.execute(
            "SELECT weight FROM charges WHERE charge_id = ?", (identifier,)
        ).fetchone()
        if existing:
            connection.execute("COMMIT")
            return AdmissionResult(True, None, identifier, int(existing[0]), idempotent=True)

        if automatic and coalesce_key:
            duplicate = connection.execute(
                "SELECT 1 FROM charges WHERE coalesce_key = ? AND created_at >= ? LIMIT 1",
                (coalesce_key, timestamp - 30),
            ).fetchone()
            if duplicate:
                connection.execute("COMMIT")
                return AdmissionResult(False, "remote-coalesced", identifier, weight)

        session_count, session_weight = _totals(connection, "session_id = ?", (session,))
        day_count, day_weight = _totals(connection, "day_bucket = ?", (day_bucket,))

        if session_count + 1 > limits["session_requests"]:
            reason = "remote-session-budget-exhausted"
        elif day_count + 1 > limits["daily_requests"]:
            reason = "remote-daily-budget-exhausted"
        elif session_weight + weight > limits["session_weight"]:
            reason = "remote-session-weight-exhausted"
        elif day_weight + weight > limits["daily_weight"]:
            reason = "remote-daily-weight-exhausted"
        elif automatic:
            session_auto, _ = _totals(
                connection, "session_id = ? AND automatic = 1", (session,)
            )
            day_auto, _ = _totals(
                connection, "day_bucket = ? AND automatic = 1", (day_bucket,)
            )
            reason = (
                "remote-automatic-budget-exhausted"
                if session_auto + 1 > limits["session_auto_requests"]
                or day_auto + 1 > limits["daily_auto_requests"]
                else None
            )
        else:
            reason = None

        if reason:
            connection.execute("ROLLBACK")
            return AdmissionResult(False, reason, identifier, weight)

        connection.execute(
            """
            INSERT INTO charges (
                charge_id, operation, ingress, automatic, session_id,
                day_bucket, weight, status, created_at, coalesce_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'charged', ?, ?)
            """,
            (
                identifier,
                operation,
                ingress,
                int(automatic),
                session,
                day_bucket,
                weight,
                timestamp,
                coalesce_key,
            ),
        )
        connection.execute("COMMIT")
        return AdmissionResult(True, None, identifier, weight)
    except (OSError, sqlite3.Error):
        if connection is not None:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
        return AdmissionResult(False, "remote-accounting-unavailable", identifier, weight)
    finally:
        if connection is not None:
            connection.close()
