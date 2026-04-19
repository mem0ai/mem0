from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


class MigrationTests(unittest.TestCase):
    def test_alembic_upgrade_creates_core_tables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "alembic_runtime.db"
            database_url = f"sqlite:///{db_path}"

            config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
            config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "migrations"))
            config.set_main_option("sqlalchemy.url", database_url)

            old_cwd = os.getcwd()
            try:
                os.chdir(Path(__file__).resolve().parents[2])
                command.upgrade(config, "head")
            finally:
                os.chdir(old_cwd)

            engine = create_engine(database_url)
            inspector = inspect(engine)
            table_names = set(inspector.get_table_names())
            self.assertTrue(
                {"agents", "episodes", "memory_events", "memory_spaces", "namespaces"}.issubset(table_names)
            )
            self.assertIn("alembic_version", table_names)
