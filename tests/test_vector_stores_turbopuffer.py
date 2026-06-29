"""Unit tests for the Turbopuffer backend (mem0/vector_stores/turbopuffer.py)."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


class TestTurbopufferDB:
    """Tests for the Turbopuffer backend."""

    @pytest.fixture(autouse=True)
    def stub_turbopuffer(self, monkeypatch):
        tpuf_mod = ModuleType("turbopuffer")
        mock_client = MagicMock()
        mock_namespace = MagicMock()
        mock_client.namespace.return_value = mock_namespace
        MockTurbopuffer = MagicMock(return_value=mock_client)
        tpuf_mod.Turbopuffer = MockTurbopuffer

        monkeypatch.setitem(sys.modules, "turbopuffer", tpuf_mod)
        monkeypatch.delitem(sys.modules, "mem0.vector_stores.turbopuffer", raising=False)

        self.mock_client = mock_client
        self.mock_namespace = mock_namespace
        self.MockTurbopuffer = MockTurbopuffer
        yield

    def _make_store(self, **kwargs):
        from mem0.vector_stores.turbopuffer import TurbopufferDB

        return TurbopufferDB(
            collection_name="test-ns",
            embedding_model_dims=3,
            api_key="test-key",
            **kwargs,
        )

    # --- init ---

    def test_init_creates_client_and_namespace(self):
        store = self._make_store()
        self.MockTurbopuffer.assert_called_once()
        self.mock_client.namespace.assert_called_once_with("test-ns")

    def test_init_raises_without_api_key(self, monkeypatch):
        monkeypatch.delenv("TURBOPUFFER_API_KEY", raising=False)
        from mem0.vector_stores.turbopuffer import TurbopufferDB

        with pytest.raises(ValueError, match="API key"):
            TurbopufferDB(collection_name="ns", embedding_model_dims=3)

    # --- insert ---

    def test_insert_sends_correct_rows(self):
        store = self._make_store()
        store.insert(
            vectors=[[0.1, 0.2, 0.3]],
            payloads=[{"data": "mem1", "user_id": "u1"}],
            ids=["id1"],
        )
        self.mock_namespace.write.assert_called_once()
        kw = self.mock_namespace.write.call_args.kwargs
        rows = kw["upsert_rows"]
        assert rows[0]["id"] == "id1"
        assert rows[0]["vector"] == [0.1, 0.2, 0.3]
        assert rows[0]["data"] == "mem1"

    def test_insert_auto_generates_ids(self):
        store = self._make_store()
        store.insert(vectors=[[0.1, 0.2, 0.3]], payloads=[{"data": "m"}])
        kw = self.mock_namespace.write.call_args.kwargs
        assert kw["upsert_rows"][0]["id"] == "0"

    def test_insert_respects_batch_size(self):
        from mem0.vector_stores.turbopuffer import TurbopufferDB

        store = TurbopufferDB(
            collection_name="ns", embedding_model_dims=3, api_key="k", batch_size=2
        )
        store.insert(
            vectors=[[0.1, 0.2, 0.3]] * 5,
            payloads=[{"data": f"m{i}"} for i in range(5)],
            ids=[f"id{i}" for i in range(5)],
        )
        assert self.mock_namespace.write.call_count == 3  # ceil(5/2)

    # --- search ---

    def test_search_returns_parsed_results(self):
        store = self._make_store()
        row = MagicMock()
        row.model_dump.return_value = {"id": "id1", "data": "mem1", "$dist": 0.3, "vector": None}
        self.mock_namespace.query.return_value = MagicMock(rows=[row])

        results = store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert len(results) == 1
        assert results[0].id == "id1"
        assert abs(results[0].score - 0.7) < 1e-6
        assert results[0].payload["data"] == "mem1"

    def test_search_passes_eq_filter(self):
        store = self._make_store()
        self.mock_namespace.query.return_value = MagicMock(rows=[])
        store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u1"})
        kw = self.mock_namespace.query.call_args.kwargs
        assert kw["filters"] == ("user_id", "Eq", "u1")

    def test_search_no_filter_omits_filters_param(self):
        store = self._make_store()
        self.mock_namespace.query.return_value = MagicMock(rows=[])
        store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5)
        kw = self.mock_namespace.query.call_args.kwargs
        assert "filters" not in kw

    # --- delete / update ---

    def test_delete(self):
        store = self._make_store()
        store.delete("id1")
        self.mock_namespace.write.assert_called_once_with(deletes=["id1"])

    def test_update_with_vector_uses_upsert(self):
        store = self._make_store()
        store.update("id1", vector=[0.1, 0.2, 0.3], payload={"data": "updated"})
        kw = self.mock_namespace.write.call_args.kwargs
        assert "upsert_rows" in kw
        assert kw["upsert_rows"][0]["id"] == "id1"
        assert kw["upsert_rows"][0]["vector"] == [0.1, 0.2, 0.3]

    def test_update_payload_only_uses_patch(self):
        store = self._make_store()
        store.update("id1", vector=None, payload={"data": "updated"})
        kw = self.mock_namespace.write.call_args.kwargs
        assert "patch_rows" in kw
        assert kw["patch_rows"][0]["id"] == "id1"

    # --- get ---

    def test_get_found(self):
        store = self._make_store()
        row = MagicMock()
        row.model_dump.return_value = {"id": "id1", "data": "mem1", "$dist": 0.0, "vector": None}
        self.mock_namespace.query.return_value = MagicMock(rows=[row])
        result = store.get("id1")
        assert result is not None
        assert result.id == "id1"

    def test_get_not_found_returns_none(self):
        store = self._make_store()
        self.mock_namespace.query.return_value = MagicMock(rows=[])
        result = store.get("missing")
        assert result is None

    # --- list ---

    def test_list_wraps_results_in_outer_list(self):
        store = self._make_store()
        row = MagicMock()
        row.model_dump.return_value = {"id": "id1", "data": "m", "$dist": 0.1, "vector": None}
        self.mock_namespace.query.return_value = MagicMock(rows=[row])
        results = store.list(top_k=10)
        assert isinstance(results, list) and isinstance(results[0], list)
        assert len(results[0]) == 1

    def test_list_returns_empty_on_error(self):
        store = self._make_store()
        self.mock_namespace.query.side_effect = Exception("network error")
        results = store.list()
        assert results == [[]]

    # --- _convert_filters ---

    def test_convert_filters_none_returns_none(self):
        store = self._make_store()
        assert store._convert_filters(None) is None

    def test_convert_filters_empty_returns_none(self):
        store = self._make_store()
        assert store._convert_filters({}) is None

    def test_convert_filters_single_eq(self):
        store = self._make_store()
        assert store._convert_filters({"user_id": "u1"}) == ("user_id", "Eq", "u1")

    def test_convert_filters_multiple_uses_and(self):
        store = self._make_store()
        result = store._convert_filters({"user_id": "u1", "agent_id": "a1"})
        assert result[0] == "And"
        assert len(result[1]) == 2

    def test_convert_filters_gte_lte(self):
        store = self._make_store()
        result = store._convert_filters({"score": {"gte": 0.5, "lte": 0.9}})
        assert result[0] == "And"
        assert ("score", "Gte", 0.5) in result[1]
        assert ("score", "Lte", 0.9) in result[1]

    # --- col helpers ---

    def test_col_info(self):
        store = self._make_store()
        meta = MagicMock()
        meta.approx_row_count = 42
        meta.approx_logical_bytes = 1024
        meta.created_at = "2025-01-01"
        meta.updated_at = "2025-06-01"
        self.mock_namespace.metadata.return_value = meta
        info = store.col_info()
        assert info["name"] == "test-ns"
        assert info["approx_row_count"] == 42

    def test_col_info_on_error_returns_name_only(self):
        store = self._make_store()
        self.mock_namespace.metadata.side_effect = Exception("unavailable")
        info = store.col_info()
        assert info == {"name": "test-ns"}

    def test_reset_calls_delete_all(self):
        store = self._make_store()
        store.reset()
        self.mock_namespace.delete_all.assert_called_once()

    def test_create_col_is_noop(self):
        store = self._make_store()
        store.create_col(name="new", vector_size=3, distance="cosine")
        self.mock_namespace.write.assert_not_called()

    def test_count(self):
        store = self._make_store()
        meta = MagicMock()
        meta.approx_row_count = 7
        self.mock_namespace.metadata.return_value = meta
        assert store.count() == 7

    def test_count_returns_zero_on_error(self):
        store = self._make_store()
        self.mock_namespace.metadata.side_effect = Exception("err")
        assert store.count() == 0
