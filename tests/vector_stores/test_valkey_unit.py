"""Unit tests for the Valkey vector store backend (mem0/vector_stores/valkey.py)."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


class TestValkeyDB:
    """Tests for the Valkey vector store backend."""

    @pytest.fixture(autouse=True)
    def stub_valkey(self, monkeypatch):
        valkey_mod = ModuleType("valkey")
        valkey_exc = ModuleType("valkey.exceptions")
        valkey_cluster = ModuleType("valkey.cluster")

        class ResponseError(Exception):
            pass

        valkey_exc.ResponseError = ResponseError
        valkey_mod.exceptions = valkey_exc
        valkey_mod.ResponseError = ResponseError

        mock_client = MagicMock()
        valkey_mod.from_url = MagicMock(return_value=mock_client)

        numpy_mod = ModuleType("numpy")
        arr_mock = MagicMock()
        arr_mock.tobytes.return_value = b"\x00" * 12
        numpy_mod.array = MagicMock(return_value=arr_mock)
        numpy_mod.float32 = float

        pytz_mod = ModuleType("pytz")
        tz_mock = MagicMock()
        pytz_mod.timezone = MagicMock(return_value=tz_mock)
        pytz_mod.UTC = tz_mock

        for key, mod in [
            ("valkey", valkey_mod),
            ("valkey.exceptions", valkey_exc),
            ("valkey.cluster", valkey_cluster),
            ("numpy", numpy_mod),
            ("pytz", pytz_mod),
        ]:
            monkeypatch.setitem(sys.modules, key, mod)

        monkeypatch.delitem(sys.modules, "mem0.vector_stores.valkey", raising=False)

        self.ResponseError = ResponseError
        self.mock_client = mock_client
        yield

    def _make_store(self, index_type="hnsw"):
        mock_client = self.mock_client
        mock_client.execute_command = MagicMock(return_value=[])
        mock_ft = MagicMock()
        mock_ft.info.side_effect = self.ResponseError("index not found")
        mock_client.ft.return_value = mock_ft

        from mem0.vector_stores.valkey import ValkeyDB

        return ValkeyDB(
            valkey_url="valkey://localhost:6379",
            collection_name="test-idx",
            embedding_model_dims=3,
            index_type=index_type,
        )

    # --- init ---

    def test_init_creates_index_when_not_found(self):
        self._make_store()
        calls = [c.args[0] for c in self.mock_client.execute_command.call_args_list]
        assert "FT._LIST" in calls
        assert "FT.CREATE" in calls

    def test_init_skips_creation_when_index_exists(self):
        mock_client = self.mock_client
        mock_client.execute_command = MagicMock(return_value=[])
        mock_ft = MagicMock()
        mock_ft.info.return_value = {"num_docs": 0}
        mock_client.ft.return_value = mock_ft

        from mem0.vector_stores.valkey import ValkeyDB

        ValkeyDB(valkey_url="valkey://localhost", collection_name="idx", embedding_model_dims=3)
        calls = [c.args[0] for c in mock_client.execute_command.call_args_list]
        assert "FT.CREATE" not in calls

    def test_init_raises_for_invalid_index_type(self):
        mock_client = self.mock_client
        mock_client.execute_command = MagicMock(return_value=[])
        mock_client.ft.return_value = MagicMock(info=MagicMock(side_effect=self.ResponseError("not found")))

        from mem0.vector_stores.valkey import ValkeyDB

        with pytest.raises(ValueError, match="Invalid index_type"):
            ValkeyDB(valkey_url="valkey://localhost", collection_name="idx",
                     embedding_model_dims=3, index_type="bad")

    def test_init_raises_when_search_module_unavailable(self):
        mock_client = self.mock_client
        mock_client.execute_command.side_effect = self.ResponseError("unknown command `FT._LIST`")

        from mem0.vector_stores.valkey import ValkeyDB

        with pytest.raises(ValueError, match="search module"):
            ValkeyDB(valkey_url="valkey://localhost", collection_name="idx", embedding_model_dims=3)

    # --- _escape_tag_value (pure function) ---

    def test_escape_tag_value_plain(self):
        from mem0.vector_stores.valkey import ValkeyDB

        assert ValkeyDB._escape_tag_value("hello") == "hello"

    def test_escape_tag_value_email(self):
        from mem0.vector_stores.valkey import ValkeyDB

        escaped = ValkeyDB._escape_tag_value("user@example.com")
        assert r"\@" in escaped
        assert r"\." in escaped

    def test_escape_tag_value_space(self):
        from mem0.vector_stores.valkey import ValkeyDB

        escaped = ValkeyDB._escape_tag_value("foo bar")
        assert r"\ " in escaped

    def test_escape_tag_value_numeric(self):
        from mem0.vector_stores.valkey import ValkeyDB

        assert ValkeyDB._escape_tag_value(42) == "42"

    # --- _build_search_query (pure method) ---

    def test_build_search_query_no_filters(self):
        store = self._make_store()
        q = store._build_search_query("[KNN 5 @embedding $vec AS score]", filters=None)
        assert q == "*=>[KNN 5 @embedding $vec AS score]"

    def test_build_search_query_with_user_id(self):
        store = self._make_store()
        q = store._build_search_query("[KNN 5 @embedding $vec AS score]", filters={"user_id": "u1"})
        assert "@user_id:{u1}" in q
        assert "=>[KNN" in q

    def test_build_search_query_none_value_ignored(self):
        store = self._make_store()
        q = store._build_search_query("[KNN 5 @embedding $vec AS score]", filters={"user_id": None})
        assert q == "*=>[KNN 5 @embedding $vec AS score]"

    def test_build_search_query_multiple_filters(self):
        store = self._make_store()
        q = store._build_search_query(
            "[KNN 5 @embedding $vec AS score]",
            filters={"user_id": "u1", "agent_id": "a1"},
        )
        assert "@user_id:{u1}" in q
        assert "@agent_id:{a1}" in q

    # --- _build_index_schema (pure method) ---

    def test_build_index_schema_hnsw_contains_ef_construction(self):
        store = self._make_store(index_type="hnsw")
        cmd = store._build_index_schema("idx", 3, "COSINE", "mem0:idx")
        assert "HNSW" in cmd
        assert "EF_CONSTRUCTION" in cmd
        assert "EF_RUNTIME" in cmd

    def test_build_index_schema_flat_omits_ef_params(self):
        store = self._make_store(index_type="flat")
        cmd = store._build_index_schema("idx", 3, "COSINE", "mem0:idx")
        assert "FLAT" in cmd
        assert "EF_CONSTRUCTION" not in cmd

    def test_build_index_schema_flat_invalid_raises(self):
        store = self._make_store()
        store.index_type = "unknown"
        with pytest.raises(ValueError, match="Unsupported index_type"):
            store._build_index_schema("idx", 3, "COSINE", "mem0:idx")

    # --- simple client-call methods ---

    def test_delete(self):
        store = self._make_store()
        store.delete("id1")
        self.mock_client.delete.assert_called_with("mem0:test-idx:id1")

    def test_list_cols(self):
        store = self._make_store()
        self.mock_client.execute_command.return_value = ["idx1", "idx2"]
        cols = store.list_cols()
        assert "idx1" in cols or "idx2" in cols

    def test_delete_col_calls_ft_dropindex(self):
        store = self._make_store()
        self.mock_client.execute_command.reset_mock()
        self.mock_client.execute_command.return_value = "OK"
        store.delete_col()
        drop_calls = [
            c for c in self.mock_client.execute_command.call_args_list
            if c.args and c.args[0] == "FT.DROPINDEX"
        ]
        assert len(drop_calls) == 1

    def test_col_info(self):
        store = self._make_store()
        mock_ft = MagicMock()
        mock_ft.info.return_value = {"num_docs": 42}
        self.mock_client.ft.return_value = mock_ft
        assert store.col_info() == {"num_docs": 42}
