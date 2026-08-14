"""Copy SQLite history.db into a SQLAlchemy history store (sqlite or postgres)."""

import importlib.util
import sqlite3
from pathlib import Path

from mem0.memory.history_store.postgres import PostgresHistoryStore
from mem0.memory.storage import SQLiteManager


def _load_migrate():
    script = Path(__file__).resolve().parents[2] / "scripts" / "migrate_history_sqlite_to_postgres.py"
    spec = importlib.util.spec_from_file_location("migrate_history_sqlite_to_postgres", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.migrate


def test_migrate_sqlite_to_sqlalchemy(tmp_path):
    migrate = _load_migrate()
    src = tmp_path / "history.db"
    dst = tmp_path / "target.db"

    sqlite = SQLiteManager(str(src))
    sqlite.add_history("m1", None, "hello", "ADD", actor_id="u1", role="user")
    sqlite.save_messages([{"role": "user", "content": "hi", "name": None}], "scope-1")
    sqlite.close()

    migrate(str(src), f"sqlite:///{dst}")

    dest = PostgresHistoryStore(f"sqlite:///{dst}")
    try:
        rows = dest.get_history("m1")
        assert len(rows) == 1
        assert rows[0]["new_memory"] == "hello"
        assert rows[0]["actor_id"] == "u1"
        messages = dest.get_last_messages("scope-1")
        assert messages[0]["content"] == "hi"
    finally:
        dest.close()

    # Second run is idempotent (ON CONFLICT DO NOTHING).
    migrate(str(src), f"sqlite:///{dst}")
    conn = sqlite3.connect(dst)
    try:
        assert conn.execute("SELECT COUNT(*) FROM history").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1
    finally:
        conn.close()
