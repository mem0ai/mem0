#!/usr/bin/env python3
"""Guided migration of core tables from SQLite to PostgreSQL.

Copies ``write_queue``, ``projects`` and ``write_audit_logs`` rows. Run while
the API is stopped. Idempotent on primary keys (skips existing rows).

Usage::

    DATABASE_URL=postgresql://... python scripts/migrate_sqlite_to_postgres.py ./api/openmemory.db
"""

from __future__ import annotations

import sys
from pathlib import Path


TABLES = ("write_queue", "projects", "write_audit_logs")


def migrate(sqlite_path: str, pg_url: str | None = None) -> None:
    import os

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    pg_url = pg_url or os.environ.get("DATABASE_URL")
    if not pg_url or not pg_url.startswith("postgresql"):
        raise SystemExit("DATABASE_URL must point to PostgreSQL")

    src = create_engine(f"sqlite:///{sqlite_path}", connect_args={"check_same_thread": False})
    dst = create_engine(pg_url)
    Src = sessionmaker(bind=src)
    Dst = sessionmaker(bind=dst)

    for table in TABLES:
        s = Src()
        d = Dst()
        try:
            rows = s.execute(text(f"SELECT * FROM {table}")).mappings().all()
            if not rows:
                print(f"{table}: nada a migrar")
                continue
            cols = list(rows[0].keys())
            placeholders = ", ".join(f":{c}" for c in cols)
            col_list = ", ".join(cols)
            inserted = 0
            for row in rows:
                try:
                    d.execute(
                        text(
                            f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
                            f"ON CONFLICT DO NOTHING"
                        ),
                        dict(row),
                    )
                    inserted += 1
                except Exception as exc:  # noqa: BLE001
                    print(f"  skip row in {table}: {exc}")
            d.commit()
            print(f"{table}: {inserted}/{len(rows)} linhas processadas")
        finally:
            s.close()
            d.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <sqlite.db>")
    db_file = Path(sys.argv[1])
    if not db_file.exists():
        raise SystemExit(f"arquivo não encontrado: {db_file}")
    migrate(str(db_file.resolve()))
