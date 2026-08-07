import importlib.util
import sqlite3
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[2] / "examples" / "screenpipe-memory-source" / "sync_screenpipe.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sync_screenpipe", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_read_screenpipe_entries_maps_sqlite_rows(tmp_path):
    sync_screenpipe = load_module()
    db_path = tmp_path / "db.sqlite"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE frames (
                timestamp TEXT,
                accessibility_text TEXT,
                app_name TEXT,
                window_name TEXT,
                url TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE audio_transcriptions (
                created_at TEXT,
                transcription TEXT,
                device_name TEXT,
                speaker_id INTEGER
            )
            """
        )
        conn.execute(
            "INSERT INTO frames VALUES (?, ?, ?, ?, ?)",
            ("2026-06-16T09:00:00Z", "Reviewed the launch checklist", "Notes", "Launch Plan", None),
        )
        conn.execute(
            "INSERT INTO audio_transcriptions VALUES (?, ?, ?, ?)",
            ("2026-06-16T09:05:00Z", "We should follow up with Maya", "MacBook Microphone", 7),
        )

    entries = sync_screenpipe.read_screenpipe_entries(db_path, limit=10)

    assert [entry.source_type for entry in entries] == ["audio", "screen"]
    assert entries[0].text == "We should follow up with Maya"
    assert entries[0].to_metadata()["screenpipe_table"] == "audio_transcriptions"
    assert entries[1].app_name == "Notes"
    assert "Reviewed the launch checklist" in entries[1].to_memory_text()


def test_sync_entries_passes_source_metadata_to_memory_client():
    sync_screenpipe = load_module()

    class FakeMemoryClient:
        def __init__(self):
            self.calls = []

        def add(self, content, **kwargs):
            self.calls.append((content, kwargs))

    memory = FakeMemoryClient()
    entry = sync_screenpipe.ScreenpipeEntry(table="frames", row_id=42, text="Alice opened the roadmap")

    synced = sync_screenpipe.sync_entries(memory, [entry], user_id="alice")

    assert synced == 1
    content, kwargs = memory.calls[0]
    assert "Alice opened the roadmap" in content
    assert kwargs["filters"] == {"user_id": "alice"}
    assert kwargs["metadata"]["source"] == "screenpipe"
    assert kwargs["metadata"]["screenpipe_row_id"] == 42
