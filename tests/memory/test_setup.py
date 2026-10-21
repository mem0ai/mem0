import importlib
import os

import pytest


def test_import_survives_unwritable_mem0_dir(monkeypatch, tmp_path):
    """import mem0 must not require creating ~/.mem0 (read-only HOME / Lambda)."""
    blocked = tmp_path / "nope"
    blocked.write_text("not-a-directory")
    monkeypatch.setenv("MEM0_DIR", str(blocked))

    import mem0.memory.setup as setup

    importlib.reload(setup)

    assert setup.mem0_dir == str(blocked)
    assert setup.get_user_id() == "anonymous_user"
    setup._write_config({"user_id": "x"})  # best-effort, must not raise
