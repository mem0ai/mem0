import datetime

import pytest
from sqlalchemy import inspect

from mem0.memory.storage import SQLDatabaseManager


@pytest.fixture
def db_manager():
    # Create a fresh in-memory SQLite database for each test.
    manager = SQLDatabaseManager(db_type="sqlite", db_url="sqlite:///:memory:")
    yield manager
    manager.close()


def test_add_and_get_history(db_manager):
    memory_id = "mem1"
    now = datetime.datetime.now()
    record_id = db_manager.add_history(
        memory_id=memory_id,
        old_memory="old content",
        new_memory="new content",
        event="UPDATE",
        created_at=now,
        updated_at=now,
        is_deleted=0,
    )
    assert isinstance(record_id, str)
    history = db_manager.get_history(memory_id)
    assert len(history) == 1
    record = history[0]
    assert record["id"] == record_id
    assert record["memory_id"] == memory_id
    assert record["old_memory"] == "old content"
    assert record["new_memory"] == "new content"
    assert record["event"] == "UPDATE"
    assert record["created_at"] == now
    assert record["updated_at"] == now


def test_delete_history(db_manager):
    memory_id = "test_delete"
    # Add two history records.
    db_manager.add_history(memory_id, "a", "b", "ADD")
    db_manager.add_history(memory_id, "b", "c", "UPDATE")
    history = db_manager.get_history(memory_id)
    assert len(history) == 2

    # Soft-delete the records.
    count = db_manager.delete_history(memory_id)
    assert count >= 1

    # After deletion, get_history should return empty results.
    history_after = db_manager.get_history(memory_id)
    assert len(history_after) == 0


def test_reset_and_recreate(db_manager):
    memory_id = "mem_reset"
    # Add a record to the table.
    db_manager.add_history(memory_id, "x", "y", "ADD")
    history_before = db_manager.get_history(memory_id)
    assert len(history_before) == 1

    # Reset the database (drop and recreate the table).
    db_manager.reset()
    history_after = db_manager.get_history(memory_id)
    assert len(history_after) == 0

    # Ensure new records can be added after reset.
    new_record_id = db_manager.add_history(memory_id, "new_old", "new_new", "UPDATE")
    history_new = db_manager.get_history(memory_id)
    assert len(history_new) == 1
    assert history_new[0]["id"] == new_record_id


def test_ensure_datetime_valid(db_manager):
    dt_str = "2023-10-10T12:30:00"
    dt_obj = db_manager._ensure_datetime(dt_str)
    expected = datetime.datetime.fromisoformat(dt_str)
    assert dt_obj == expected

    now = datetime.datetime.now()
    assert db_manager._ensure_datetime(now) == now


def test_ensure_datetime_invalid(db_manager):
    with pytest.raises(TypeError):
        db_manager._ensure_datetime(123)
    with pytest.raises(TypeError):
        db_manager._ensure_datetime("invalid-datetime")


def test_multiple_history_records_order(db_manager):
    memory_id = "mem_order"
    base_time = datetime.datetime.now()
    # Add multiple records with increasing timestamps.
    for i in range(5):
        db_manager.add_history(
            memory_id,
            old_memory=f"old_{i}",
            new_memory=f"new_{i}",
            event="UPDATE",
            created_at=base_time + datetime.timedelta(seconds=i),
            updated_at=base_time + datetime.timedelta(seconds=i),
            is_deleted=0,
        )
    history = db_manager.get_history(memory_id)
    assert len(history) == 5

    # Verify that records are ordered by updated_at in ascending order.
    timestamps = [record["updated_at"] for record in history]
    assert timestamps == sorted(timestamps)


def test_table_schema_after_migration(db_manager):
    # Verify that after migration the history table contains the expected columns.
    inspector = inspect(db_manager._engine)
    tables = inspector.get_table_names()
    assert "history" in tables

    columns = {col["name"] for col in inspector.get_columns("history")}
    expected_columns = {
        "id",
        "memory_id",
        "old_memory",
        "new_memory",
        "new_value",
        "event",
        "created_at",
        "updated_at",
        "is_deleted",
    }
    assert expected_columns.issubset(columns)


def test_close_behavior(db_manager):
    # Close the database and check that the engine is disposed.
    db_manager.close()
    assert db_manager._engine is None
