"""Unit tests for the Upstash Vector backend (mem0/vector_stores/upstash_vector.py)."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


class TestUpstashVector:
    """Tests for the Upstash Vector backend."""

    @pytest.fixture(autouse=True)
    def stub_upstash(self, monkeypatch):
        upstash_mod = ModuleType("upstash_vector")
        MockIndex = MagicMock()
        upstash_mod.Index = MockIndex
        monkeypatch.setitem(sys.modules, "upstash_vector", upstash_mod)
        monkeypatch.delitem(sys.modules, "mem0.vector_stores.upstash_vector", raising=False)
        self.MockIndex = MockIndex
        yield

    def _make_store(self, enable_embeddings=False):
        from mem0.vector_stores.upstash_vector import UpstashVector

        mock_client = MagicMock()
        store = UpstashVector(
            collection_name="test-ns",
            client=mock_client,
            enable_embeddings=enable_embeddings,
        )
        return store, mock_client

    # --- init ---

    def test_init_with_url_and_token(self):
        from mem0.vector_stores.upstash_vector import UpstashVector

        mock_idx = MagicMock()
        self.MockIndex.return_value = mock_idx
        store = UpstashVector(collection_name="ns", url="https://x.upstash.io", token="tok")
        self.MockIndex.assert_called_once_with("https://x.upstash.io", "tok")
        assert store.client == mock_idx

    def test_init_raises_without_credentials(self):
        from mem0.vector_stores.upstash_vector import UpstashVector

        with pytest.raises(ValueError, match="client or URL and token"):
            UpstashVector(collection_name="ns")

    # --- insert ---

    def test_insert_vector_mode(self):
        store, mock_client = self._make_store(enable_embeddings=False)
        store.insert(
            vectors=[[0.1, 0.2, 0.3]],
            payloads=[{"data": "mem1"}],
            ids=["id1"],
        )
        mock_client.upsert.assert_called_once()
        kw = mock_client.upsert.call_args.kwargs
        assert kw["namespace"] == "test-ns"
        v = kw["vectors"][0]
        assert v["id"] == "id1"
        assert v["vector"] == [0.1, 0.2, 0.3]
        assert v["metadata"] == {"data": "mem1"}

    def test_insert_embedding_mode_uses_data_field(self):
        store, mock_client = self._make_store(enable_embeddings=True)
        store.insert(
            vectors=[[0.1, 0.2, 0.3]],
            payloads=[{"data": "mem1"}],
            ids=["id1"],
        )
        kw = mock_client.upsert.call_args.kwargs
        assert kw["vectors"][0]["data"] == "mem1"
        assert "vector" not in kw["vectors"][0]

    def test_insert_embedding_mode_raises_without_data(self):
        store, _ = self._make_store(enable_embeddings=True)
        with pytest.raises(ValueError, match="data"):
            store.insert(
                vectors=[[0.1, 0.2, 0.3]],
                payloads=[{"no_data_field": "x"}],
                ids=["id1"],
            )

    # --- search ---

    def test_search_vector_mode(self):
        store, mock_client = self._make_store(enable_embeddings=False)
        res = MagicMock()
        res.id, res.score, res.metadata = "id1", 0.9, {"data": "mem1"}
        mock_client.query_many.return_value = [[res]]
        results = store.search(query="q", vectors=[[0.1, 0.2, 0.3]], top_k=5)
        assert len(results) == 1
        assert results[0].id == "id1"
        assert results[0].score == 0.9

    def test_search_embedding_mode(self):
        store, mock_client = self._make_store(enable_embeddings=True)
        res = MagicMock()
        res.id, res.score, res.metadata = "id1", 0.8, {"data": "mem1"}
        mock_client.query.return_value = [res]
        results = store.search(query="mem1", vectors=[[0.1, 0.2, 0.3]], top_k=5)
        mock_client.query.assert_called_once()
        assert results[0].score == 0.8

    def test_search_applies_filter_string(self):
        store, mock_client = self._make_store(enable_embeddings=False)
        mock_client.query_many.return_value = [[]]
        store.search(query="q", vectors=[[0.1]], top_k=5, filters={"user_id": "u1"})
        kw = mock_client.query_many.call_args.kwargs
        assert kw["queries"][0]["filter"] == 'user_id = "u1"'

    # --- keyword_search ---

    def test_keyword_search_returns_results(self):
        store, mock_client = self._make_store()
        res = MagicMock()
        res.id, res.score, res.metadata = "id1", 0.8, {"data": "mem1"}
        mock_client.query.return_value = [res]
        results = store.keyword_search(query="mem1", top_k=5)
        assert results[0].id == "id1"

    def test_keyword_search_returns_none_on_error(self):
        store, mock_client = self._make_store()
        mock_client.query.side_effect = Exception("BM25 not available")
        assert store.keyword_search("q") is None

    # --- delete / update / get ---

    def test_delete(self):
        store, mock_client = self._make_store()
        store.delete("id1")
        mock_client.delete.assert_called_once_with(ids=["id1"], namespace="test-ns")

    def test_update(self):
        store, mock_client = self._make_store()
        store.update("id1", vector=[0.1, 0.2, 0.3], payload={"data": "updated"})
        mock_client.update.assert_called_once_with(
            id="id1",
            vector=[0.1, 0.2, 0.3],
            data="updated",
            metadata={"data": "updated"},
            namespace="test-ns",
        )

    def test_get_found(self):
        store, mock_client = self._make_store()
        vec = MagicMock()
        vec.id, vec.metadata = "id1", {"data": "mem1"}
        mock_client.fetch.return_value = [vec]
        result = store.get("id1")
        assert result.id == "id1"
        assert result.payload == {"data": "mem1"}
        assert result.score is None

    def test_get_empty_response_returns_none(self):
        store, mock_client = self._make_store()
        mock_client.fetch.return_value = []
        assert store.get("missing") is None

    def test_get_null_vector_returns_none(self):
        store, mock_client = self._make_store()
        mock_client.fetch.return_value = [None]
        assert store.get("id1") is None

    # --- list ---

    def test_list_returns_empty_for_zero_vectors(self):
        store, mock_client = self._make_store()
        info = MagicMock()
        info.namespaces = {}
        mock_client.info.return_value = info
        assert store.list() == [[]]

    def test_list_namespace_empty_vector_count(self):
        store, mock_client = self._make_store()
        ns_info = MagicMock()
        ns_info.vector_count = 0
        info = MagicMock()
        info.namespaces = {"test-ns": ns_info}
        mock_client.info.return_value = info
        assert store.list() == [[]]

    # --- _stringify ---

    def test_stringify_wraps_strings_in_quotes(self):
        store, _ = self._make_store()
        assert store._stringify("hello") == '"hello"'

    def test_stringify_passes_numbers_through(self):
        store, _ = self._make_store()
        assert store._stringify(42) == 42

    # --- col helpers ---

    def test_list_cols(self):
        store, mock_client = self._make_store()
        mock_client.list_namespaces.return_value = ["ns1", "ns2"]
        assert store.list_cols() == ["ns1", "ns2"]

    def test_delete_col_resets_namespace(self):
        store, mock_client = self._make_store()
        store.delete_col()
        mock_client.reset.assert_called_once_with(namespace="test-ns")

    def test_col_info_returns_client_info(self):
        store, mock_client = self._make_store()
        sentinel = object()
        mock_client.info.return_value = sentinel
        assert store.col_info() is sentinel

    def test_create_col_is_noop(self):
        store, mock_client = self._make_store()
        store.create_col("ns", 3, "cosine")
        mock_client.upsert.assert_not_called()
