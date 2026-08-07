from datetime import datetime, timedelta, timezone

import pytest

from mem0.memory.main import AsyncMemory, Memory


def _setup_factory_mocks(mocker):
    """Patch the provider factories so Memory/AsyncMemory can be constructed without real backends."""
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vector_store.return_value, mocker.MagicMock()],
    )

    mocker.patch("mem0.utils.factory.LlmFactory.create", mocker.MagicMock())
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())


def _record(id_, created_at=None, memory="m", **extra):
    record = {"id": id_, "memory": memory, "created_at": created_at}
    record.update(extra)
    return record


@pytest.fixture
def memory(mocker):
    _setup_factory_mocks(mocker)
    mocker.patch("mem0.memory.main.capture_event")
    mem = Memory()
    # cleanup is pure orchestration over get_all + delete, so stub those out.
    mem.get_all = mocker.MagicMock()
    mem.delete = mocker.MagicMock()
    return mem


class TestCleanupSync:
    def test_ttl_removes_old_keeps_recent(self, memory):
        now = datetime.now(timezone.utc)
        memory.get_all.return_value = {
            "results": [
                _record("old", (now - timedelta(hours=2)).isoformat()),
                _record("recent", (now - timedelta(minutes=1)).isoformat()),
            ]
        }

        report = memory.cleanup(policy="ttl", filters={"user_id": "u"}, older_than=timedelta(hours=1))

        assert report["policy"] == "ttl"
        assert report["scanned"] == 2
        assert report["removed_count"] == 1
        assert report["removed"][0]["id"] == "old"
        memory.delete.assert_called_once_with("old")
        memory.get_all.assert_called_once_with(filters={"user_id": "u"}, top_k=100)

    def test_ttl_accepts_seconds(self, memory):
        now = datetime.now(timezone.utc)
        memory.get_all.return_value = {"results": [_record("old", (now - timedelta(seconds=120)).isoformat())]}

        report = memory.cleanup(policy="ttl", filters={"user_id": "u"}, older_than=60)

        assert report["removed_count"] == 1
        memory.delete.assert_called_once_with("old")

    def test_dry_run_reports_without_deleting(self, memory):
        now = datetime.now(timezone.utc)
        memory.get_all.return_value = {"results": [_record("old", (now - timedelta(days=2)).isoformat())]}

        report = memory.cleanup(
            policy="ttl", filters={"user_id": "u"}, older_than=timedelta(days=1), dry_run=True
        )

        assert report["dry_run"] is True
        assert report["removed_count"] == 1
        memory.delete.assert_not_called()

    def test_custom_predicate(self, memory):
        memory.get_all.return_value = {
            "results": [
                _record("keep", memory="useful fact"),
                _record("drop", memory="please drop me"),
            ]
        }

        report = memory.cleanup(policy=lambda record: "drop" in record["memory"], filters={"user_id": "u"})

        assert report["policy"] == "custom"
        assert [r["id"] for r in report["removed"]] == ["drop"]
        memory.delete.assert_called_once_with("drop")

    def test_ttl_without_older_than_raises(self, memory):
        with pytest.raises(ValueError, match="older_than"):
            memory.cleanup(policy="ttl", filters={"user_id": "u"})
        memory.get_all.assert_not_called()

    def test_unknown_policy_raises(self, memory):
        with pytest.raises(ValueError, match="Unknown cleanup policy"):
            memory.cleanup(policy="nope", filters={"user_id": "u"})

    def test_lru_not_yet_supported(self, memory):
        with pytest.raises(ValueError, match="lru"):
            memory.cleanup(policy="lru", filters={"user_id": "u"})

    def test_record_without_created_at_is_skipped_by_ttl(self, memory):
        memory.get_all.return_value = {"results": [_record("no_ts", None)]}

        report = memory.cleanup(policy="ttl", filters={"user_id": "u"}, older_than=1)

        assert report["removed_count"] == 0
        memory.delete.assert_not_called()


@pytest.fixture
def async_memory(mocker):
    _setup_factory_mocks(mocker)
    mocker.patch("mem0.memory.main.capture_event")
    mem = AsyncMemory()
    mem.get_all = mocker.AsyncMock()
    mem.delete = mocker.AsyncMock()
    return mem


class TestCleanupAsync:
    @pytest.mark.asyncio
    async def test_async_ttl_removes_old(self, async_memory):
        now = datetime.now(timezone.utc)
        async_memory.get_all.return_value = {
            "results": [
                _record("old", (now - timedelta(hours=2)).isoformat()),
                _record("recent", (now - timedelta(minutes=1)).isoformat()),
            ]
        }

        report = await async_memory.cleanup(policy="ttl", filters={"user_id": "u"}, older_than=timedelta(hours=1))

        assert report["removed_count"] == 1
        assert report["removed"][0]["id"] == "old"
        async_memory.delete.assert_awaited_once_with("old")

    @pytest.mark.asyncio
    async def test_async_dry_run_reports_without_deleting(self, async_memory):
        now = datetime.now(timezone.utc)
        async_memory.get_all.return_value = {"results": [_record("old", (now - timedelta(days=2)).isoformat())]}

        report = await async_memory.cleanup(
            policy="ttl", filters={"user_id": "u"}, older_than=timedelta(days=1), dry_run=True
        )

        assert report["removed_count"] == 1
        async_memory.delete.assert_not_awaited()
