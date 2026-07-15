import asyncio
import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory
from mem0.memory.storage import SQLiteManager
from mem0.utils.lemmatization import lemmatize_for_bm25


class FakeVectorStore:
    """In-memory stand-in implementing just the slice export/import + get_all touch."""

    def __init__(self):
        self.data = {}

    def insert(self, vectors, ids, payloads):
        for vid, payload in zip(ids, payloads):
            self.data[vid] = SimpleNamespace(id=vid, payload=dict(payload), score=None)

    def list(self, filters=None, top_k=100):
        filters = filters or {}
        matched = [
            SimpleNamespace(id=item.id, payload=dict(item.payload), score=None)
            for item in self.data.values()
            if all(item.payload.get(k) == v for k, v in filters.items())
        ]
        return [matched]

    def get(self, vector_id):
        return self.data.get(vector_id)

    def delete(self, vector_id):
        self.data.pop(vector_id, None)


class FakeEmbedder:
    def embed(self, text, memory_action=None):
        return [float(len(text or "")), 0.0, 0.0]


SCOPE = {"user_id": "u1", "agent_id": "a1", "run_id": "sess-42"}
TS = "2026-07-10T00:00:00+00:00"


def _make_memory(mocker, cls=Memory):
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=MagicMock())
    mocker.patch("mem0.utils.factory.VectorStoreFactory.create", return_value=MagicMock())
    mocker.patch("mem0.utils.factory.LlmFactory.create", return_value=MagicMock())
    mocker.patch("mem0.memory.main.SQLiteManager", return_value=MagicMock())
    mocker.patch("mem0.memory.main.capture_event")
    mocker.patch("mem0.memory.main.display_first_run_notice")
    mocker.patch("mem0.memory.main.display_scale_threshold_notice")
    m = cls()
    m.vector_store = FakeVectorStore()
    m.embedding_model = FakeEmbedder()
    m.db = SQLiteManager(":memory:")
    m.api_version = "v1.1"
    return m


def _seed(mem, mem_id="m1", data="I love pizza", scope=SCOPE):
    payload = {"data": data, "hash": "h_" + mem_id, "created_at": TS, "updated_at": TS, **scope}
    mem.vector_store.insert(vectors=[[0.0, 0.0, 0.0]], ids=[mem_id], payloads=[payload])
    return payload


class TestSessionExportImport:
    def test_export_requires_entity_filter(self, mocker):
        m = _make_memory(mocker)
        with pytest.raises(ValueError):
            m.export_session(filters={})

    def test_round_trip_memories(self, mocker):
        src = _make_memory(mocker)
        _seed(src, "m1", "I love pizza")
        _seed(src, "m2", "I use Python")

        bundle = src.export_session(filters=SCOPE)
        assert bundle["mem0_export_version"] == "1"
        assert bundle["scope"] == SCOPE
        assert len(bundle["memories"]) == 2

        dst = _make_memory(mocker)
        summary = dst.import_session(bundle)
        assert summary["imported"]["memories"] == 2

        got = {r["id"]: r["memory"] for r in dst.get_all(filters=SCOPE)["results"]}
        assert got == {"m1": "I love pizza", "m2": "I use Python"}

    def test_import_recomputes_hash_and_text_lemmatized(self, mocker):
        src = _make_memory(mocker)
        _seed(src, "m1", "I love pizza")
        bundle = src.export_session(filters=SCOPE)
        # simulate a source backend that dropped text_lemmatized and carried a stale hash
        bundle["memories"][0]["payload"].pop("text_lemmatized", None)
        bundle["memories"][0]["payload"]["hash"] = "stale"

        dst = _make_memory(mocker)
        dst.import_session(bundle)
        stored = dst.vector_store.get("m1").payload
        assert stored["text_lemmatized"] == lemmatize_for_bm25("I love pizza")
        assert stored["hash"] == hashlib.md5("I love pizza".encode()).hexdigest()

    def test_empty_data_memory_is_dropped(self, mocker):
        src = _make_memory(mocker)
        _seed(src, "m1", "real memory")
        _seed(src, "m2", "")
        bundle = src.export_session(filters=SCOPE)
        assert len(bundle["memories"]) == 2  # export keeps both

        dst = _make_memory(mocker)
        summary = dst.import_session(bundle)
        assert summary["imported"]["memories"] == 1
        assert summary["dropped"]["memories"] == 1
        assert {r["id"] for r in dst.get_all(filters=SCOPE)["results"]} == {"m1"}

    def test_remap_scope_continues_as_new_session(self, mocker):
        src = _make_memory(mocker)
        _seed(src, "m1", "I love pizza")
        bundle = src.export_session(filters=SCOPE)

        dst = _make_memory(mocker)
        dst.import_session(bundle, remap_scope={"run_id": "sess-cont"})

        new_scope = {**SCOPE, "run_id": "sess-cont"}
        assert [r["memory"] for r in dst.get_all(filters=new_scope)["results"]] == ["I love pizza"]
        assert dst.get_all(filters=SCOPE)["results"] == []

    def test_remap_into_populated_same_instance_forks_source_intact(self, mocker):
        # Fork a session under a new run_id in the SAME store. remap must mint fresh ids so
        # nothing is silently skipped and the original session is left untouched.
        m = _make_memory(mocker)
        _seed(m, "m1", "I love pizza")
        _seed(m, "m2", "I use Python")
        bundle = m.export_session(filters=SCOPE)

        summary = m.import_session(bundle, remap_scope={"run_id": "sess-cont"})
        assert summary["imported"]["memories"] == 2  # forked, not skipped

        # Original session untouched.
        assert {r["id"] for r in m.get_all(filters=SCOPE)["results"]} == {"m1", "m2"}
        # Fork populated under the new scope, on fresh ids (not m1/m2).
        forked = m.get_all(filters={**SCOPE, "run_id": "sess-cont"})["results"]
        assert sorted(r["memory"] for r in forked) == ["I love pizza", "I use Python"]
        assert {r["id"] for r in forked}.isdisjoint({"m1", "m2"})

    def test_on_conflict_modes(self, mocker):
        src = _make_memory(mocker)
        _seed(src, "m1", "I love pizza")
        bundle = src.export_session(filters=SCOPE)

        dst = _make_memory(mocker)
        assert dst.import_session(bundle)["imported"]["memories"] == 1
        again = dst.import_session(bundle, on_conflict="skip")
        assert again["imported"]["memories"] == 0
        assert again["skipped"]["memories"] == 1
        assert dst.import_session(bundle, on_conflict="overwrite")["imported"]["memories"] == 1
        assert len(dst.vector_store.data) == 1
        assert dst.import_session(bundle, on_conflict="new_ids")["imported"]["memories"] == 1
        assert len(dst.vector_store.data) == 2

    def test_invalid_on_conflict_and_missing_bundle(self, mocker):
        m = _make_memory(mocker)
        with pytest.raises(ValueError):
            m.import_session({"memories": []}, on_conflict="nope")
        with pytest.raises(ValueError):
            m.import_session()

    def test_file_round_trip_gz(self, mocker, tmp_path):
        src = _make_memory(mocker)
        _seed(src, "m1", "I love pizza")
        out = src.export_session(filters=SCOPE, path=str(tmp_path / "sess.json"), compress=True)
        assert out.endswith(".gz")

        dst = _make_memory(mocker)
        assert dst.import_session(path=out)["imported"]["memories"] == 1

    def test_file_round_trip_plain_json(self, mocker, tmp_path):
        src = _make_memory(mocker)
        _seed(src, "m1", "I love pizza")
        out = src.export_session(filters=SCOPE, path=str(tmp_path / "sess.json"))
        assert out.endswith(".json") and not out.endswith(".gz")

        dst = _make_memory(mocker)
        assert dst.import_session(path=out)["imported"]["memories"] == 1

    def test_compress_does_not_double_gz_suffix(self, mocker, tmp_path):
        src = _make_memory(mocker)
        _seed(src, "m1", "x")
        out = src.export_session(filters=SCOPE, path=str(tmp_path / "s.json.gz"), compress=True)
        assert out.endswith(".json.gz") and not out.endswith(".gz.gz")

    def test_async_round_trip(self, mocker):
        src = _make_memory(mocker, cls=AsyncMemory)
        _seed(src, "m1", "I love pizza")

        async def run():
            bundle = await src.export_session(filters=SCOPE)
            dst = _make_memory(mocker, cls=AsyncMemory)
            summary = await dst.import_session(bundle)
            return dst, summary

        dst, summary = asyncio.run(run())
        assert summary["imported"]["memories"] == 1
        assert dst.vector_store.get("m1").payload["data"] == "I love pizza"
