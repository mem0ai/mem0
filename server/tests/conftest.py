"""Shared pytest setup for the self-hosted server tests.

Importing ``main`` runs module-level initialization (auth check, DB engine,
Mem0 runtime). Set safe defaults here so the import works without a live
Postgres/provider; individual tests stub ``get_memory_instance`` as needed.
"""

import os
import tempfile

os.environ.setdefault("AUTH_DISABLED", "true")
os.environ.setdefault("MEM0_TELEMETRY", "false")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")
os.environ.setdefault(
    "HISTORY_DB_PATH", os.path.join(tempfile.gettempdir(), "mem0_server_test_history.db")
)
