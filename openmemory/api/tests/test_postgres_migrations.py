"""PostgreSQL migration integration tests (task_01).

Skipped unless POSTGRES_TEST_URL is set, e.g.::

    POSTGRES_TEST_URL=postgresql://mem0:mem0@localhost:6432/openmemory pytest tests/test_postgres_migrations.py -v
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("POSTGRES_TEST_URL"),
    reason="POSTGRES_TEST_URL not set",
)


@pytest.fixture
def pg_url():
    return os.environ["POSTGRES_TEST_URL"]


def test_alembic_upgrade_head(pg_url, monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from alembic import command
    from alembic.config import Config

    ini = tmp_path / "alembic.ini"
    ini.write_text(
        """
[alembic]
script_location = alembic
sqlalchemy.url = driver://user:pass@localhost/dbname
""".strip()
    )
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    command.upgrade(cfg, "head")

    from sqlalchemy import create_engine, inspect

    eng = create_engine(pg_url)
    tables = set(inspect(eng).get_table_names())
    eng.dispose()
    for name in ("write_queue", "projects", "write_audit_logs"):
        assert name in tables


def test_write_queue_index_exists(pg_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", pg_url)
    from sqlalchemy import create_engine, inspect

    eng = create_engine(pg_url)
    indexes = {idx["name"] for idx in inspect(eng).get_indexes("write_queue")}
    eng.dispose()
    assert "idx_write_queue_status_created" in indexes
