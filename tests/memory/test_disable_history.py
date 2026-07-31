"""Tests for MemoryConfig.disable_history (parity with TS disableHistory)."""

from unittest.mock import MagicMock, patch


from mem0.configs.base import MemoryConfig
from mem0.memory.storage import DummyHistoryManager, SQLiteManager


def test_dummy_history_manager_is_noop():
    db = DummyHistoryManager("/tmp/should-not-be-created-by-dummy.db")
    db.add_history("m1", None, "hello", "ADD")
    db.batch_add_history(
        [{"memory_id": "m1", "old_memory": None, "new_memory": "x", "event": "ADD"}]
    )
    assert db.get_history("m1") == []
    db.save_messages([{"role": "user", "content": "hi"}], "scope")
    assert db.get_last_messages("scope") == []
    db.reset()
    db.close()


def test_memory_config_disable_history_default_false():
    cfg = MemoryConfig()
    assert cfg.disable_history is False


@patch("mem0.memory.main.EmbedderFactory")
@patch("mem0.memory.main.VectorStoreFactory")
@patch("mem0.memory.main.LlmFactory")
@patch("mem0.memory.main.capture_event")
def test_memory_uses_dummy_when_disable_history(
    mock_event, mock_llm, mock_vs, mock_emb
):
    from mem0.memory.main import Memory

    mock_emb.create.return_value = MagicMock()
    mock_vs.create.return_value = MagicMock()
    mock_llm.create.return_value = MagicMock()

    cfg = MemoryConfig(disable_history=True, history_db_path=":memory:")
    mem = Memory(cfg)
    assert isinstance(mem.db, DummyHistoryManager)
    # history() path
    assert mem.history("any-id") == []
    mem.close()


@patch("mem0.memory.main.EmbedderFactory")
@patch("mem0.memory.main.VectorStoreFactory")
@patch("mem0.memory.main.LlmFactory")
@patch("mem0.memory.main.capture_event")
def test_memory_uses_sqlite_by_default(mock_event, mock_llm, mock_vs, mock_emb, tmp_path):
    from mem0.memory.main import Memory

    mock_emb.create.return_value = MagicMock()
    mock_vs.create.return_value = MagicMock()
    mock_llm.create.return_value = MagicMock()

    db_path = str(tmp_path / "history.db")
    cfg = MemoryConfig(history_db_path=db_path)
    mem = Memory(cfg)
    assert isinstance(mem.db, SQLiteManager)
    mem.db.add_history("m1", None, "fact", "ADD", created_at="2026-01-01T00:00:00+00:00")
    hist = mem.history("m1")
    assert len(hist) == 1
    assert hist[0]["new_memory"] == "fact"
    mem.close()


@patch("mem0.memory.main.EmbedderFactory")
@patch("mem0.memory.main.VectorStoreFactory")
@patch("mem0.memory.main.LlmFactory")
@patch("mem0.memory.main.capture_event")
def test_async_memory_uses_dummy_when_disable_history(
    mock_event, mock_llm, mock_vs, mock_emb
):
    from mem0.memory.main import AsyncMemory

    mock_emb.create.return_value = MagicMock()
    mock_vs.create.return_value = MagicMock()
    mock_llm.create.return_value = MagicMock()

    cfg = MemoryConfig(disable_history=True)
    mem = AsyncMemory(cfg)
    assert isinstance(mem.db, DummyHistoryManager)
    mem.close()


@patch("mem0.memory.main.EmbedderFactory")
@patch("mem0.memory.main.VectorStoreFactory")
@patch("mem0.memory.main.LlmFactory")
@patch("mem0.memory.main.capture_event")
def test_reset_preserves_disable_history(mock_event, mock_llm, mock_vs, mock_emb):
    from mem0.memory.main import Memory

    mock_emb.create.return_value = MagicMock()
    vs = MagicMock()
    mock_vs.create.return_value = vs
    mock_vs.reset.return_value = vs
    mock_llm.create.return_value = MagicMock()
    # enable reset path with hasattr reset
    vs.reset = MagicMock()

    cfg = MemoryConfig(disable_history=True)
    mem = Memory(cfg)
    assert isinstance(mem.db, DummyHistoryManager)
    mem.reset()
    assert isinstance(mem.db, DummyHistoryManager)
    mem.close()
