#!/usr/bin/env python3
"""Copy SQLite history.db (history + messages) into Postgres.

Use this once when moving a replicas=1 SQLite install onto the shared
Postgres history store, before raising replica count.

Example:

    python scripts/migrate_history_sqlite_to_postgres.py \\
      --sqlite /app/history/history.db \\
      --url postgresql+psycopg://postgres:postgres@postgres:5432/mem0_app
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from typing import Sequence

from sqlalchemy import create_engine, text

_UPSERT_HISTORY = """
INSERT INTO history (
    id, memory_id, old_memory, new_memory, event,
    created_at, updated_at, is_deleted, actor_id, role
)
VALUES (
    :id, :memory_id, :old_memory, :new_memory, :event,
    :created_at, :updated_at, :is_deleted, :actor_id, :role
)
ON CONFLICT (id) DO NOTHING
"""

_UPSERT_MESSAGE = """
INSERT INTO messages (id, session_scope, role, content, name, created_at)
VALUES (:id, :session_scope, :role, :content, :name, :created_at)
ON CONFLICT (id) DO NOTHING
"""

_CREATE_HISTORY = """
CREATE TABLE IF NOT EXISTS history (
    id           TEXT PRIMARY KEY,
    memory_id    TEXT,
    old_memory   TEXT,
    new_memory   TEXT,
    event        TEXT,
    created_at   TEXT,
    updated_at   TEXT,
    is_deleted   INTEGER,
    actor_id     TEXT,
    role         TEXT
)
"""

_CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id            TEXT PRIMARY KEY,
    session_scope TEXT,
    role          TEXT,
    content       TEXT,
    name          TEXT,
    created_at    TEXT
)
"""

_CREATE_HISTORY_INDEX = "CREATE INDEX IF NOT EXISTS ix_history_memory_id_created_at ON history (memory_id, created_at)"
_CREATE_MESSAGES_INDEX = (
    "CREATE INDEX IF NOT EXISTS ix_messages_session_scope_created_at ON messages (session_scope, created_at)"
)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def _copy_table(sqlite_conn: sqlite3.Connection, engine, table: str, columns: Sequence[str], sql: str) -> int:
    if not _table_exists(sqlite_conn, table):
        print(f"skip {table}: not present in sqlite", file=sys.stderr)
        return 0
    cols = ", ".join(columns)
    rows = sqlite_conn.execute(f"SELECT {cols} FROM {table}").fetchall()
    payload = [dict(zip(columns, row)) for row in rows]
    if not payload:
        print(f"copied 0 {table} rows")
        return 0
    with engine.begin() as conn:
        conn.execute(text(sql), payload)
    print(f"copied {len(payload)} {table} rows")
    return len(payload)


def migrate(sqlite_path: str, url: str) -> None:
    sqlite_conn = sqlite3.connect(sqlite_path)
    engine = create_engine(url, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(text(_CREATE_HISTORY))
        conn.execute(text(_CREATE_MESSAGES))
        conn.execute(text(_CREATE_HISTORY_INDEX))
        conn.execute(text(_CREATE_MESSAGES_INDEX))

    history_cols = (
        "id",
        "memory_id",
        "old_memory",
        "new_memory",
        "event",
        "created_at",
        "updated_at",
        "is_deleted",
        "actor_id",
        "role",
    )
    message_cols = ("id", "session_scope", "role", "content", "name", "created_at")
    try:
        _copy_table(sqlite_conn, engine, "history", history_cols, _UPSERT_HISTORY)
        _copy_table(sqlite_conn, engine, "messages", message_cols, _UPSERT_MESSAGE)
    finally:
        sqlite_conn.close()
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", required=True, help="Path to existing history.db")
    parser.add_argument("--url", required=True, help="SQLAlchemy URL for mem0_app")
    args = parser.parse_args()
    migrate(args.sqlite, args.url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
