from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("turbopuffer", reason="turbopuffer not installed")

from turbopuffer.types import Row

from mem0.vector_stores.turbopuffer import OutputData, TurbopufferDB


def _make_row(id, dist=None, vector=None, **attributes):
    """Helper to create a turbopuffer Row with extra attributes."""
    data = {"id": id, "vector": vector}
    if dist is not None:
        data["$dist"] = dist
    data.update(attributes)
    return Row.model_validate(data)


@pytest.fixture
def mock_client():
    with patch("mem0.vector_stores.turbopuffer.TurbopufferClient") as MockClient:
        client_instance = MagicMock()
        namespace_instance = MagicMock()
        client_instance.namespace.return_value = namespace_instance
        MockClient.return_value = client_instance
        yield client_instance, namespace_instance


@pytest.fixture
def db(mock_client):
    _, _ = mock_client
    return TurbopufferDB(
        collection_name="test_ns",
        embedding_model_dims=4,
        api_key="tpuf_test_key",
        region="gcp-us-central1",
        distance_metric="cosine_distance",
        batch_size=2,
    )


# ── Initialization ──────────────────────────────────────────────────


class TestInit:
    def test_init_with_api_key(self, mock_client):
        client_instance, namespace_instance = mock_client
        db = TurbopufferDB(
            collection_name="my_ns",
            embedding_model_dims=128,
            api_key="tpuf_key",
            region="gcp-us-central1",
        )
        assert db.collection_name == "my_ns"
        assert db.embedding_model_dims == 128
        assert db.distance_metric == "cosine_distance"
        assert db.batch_size == 100
        client_instance.namespace.assert_called_with("my_ns")

    def test_init_with_env_var(self, mock_client):
        with patch.dict("os.environ", {"TURBOPUFFER_API_KEY": "tpuf_env_key"}):
            db = TurbopufferDB(
                collection_name="test",
                embedding_model_dims=4,
                region="gcp-us-central1",
            )
            assert db.collection_name == "test"

    def test_init_without_api_key_raises(self, mock_client):
        with patch.dict("os.environ", {}, clear=True):
            # Remove TURBOPUFFER_API_KEY if it exists
            import os
            os.environ.pop("TURBOPUFFER_API_KEY", None)
            with pytest.raises(ValueError, match="API key must be provided"):
                TurbopufferDB(
                    collection_name="test",
                    embedding_model_dims=4,
                    region="gcp-us-central1",
                )

    def test_init_with_extra_params(self, mock_client):
        client_instance, _ = mock_client
        with patch("mem0.vector_stores.turbopuffer.TurbopufferClient") as MockClient:
            MockClient.return_value = client_instance
            TurbopufferDB(
                collection_name="test",
                embedding_model_dims=4,
                api_key="key",
                region="aws-us-west-2",
                extra_params={"compression": True},
            )
            MockClient.assert_called_with(
                api_key="key",
                region="aws-us-west-2",
                compression=True,
            )

    def test_init_default_region(self, mock_client):
        client_instance, _ = mock_client
        with patch("mem0.vector_stores.turbopuffer.TurbopufferClient") as MockClient:
            MockClient.return_value = client_instance
            TurbopufferDB(
                collection_name="test",
                embedding_model_dims=4,
                api_key="key",
            )
            MockClient.assert_called_with(
                api_key="key",
                region="gcp-us-central1",
            )


# ── create_col ───────────────────────────────────────────────────────


class TestCreateCol:
    def test_create_col_is_noop(self, db):
        # Should not raise or call anything
        result = db.create_col()
        assert result is None

    def test_create_col_with_args_is_noop(self, db):
        result = db.create_col(name="x", vector_size=128, distance="cosine")
        assert result is None


# ── insert ───────────────────────────────────────────────────────────


class TestInsert:
    def test_insert_with_ids_and_payloads(self, db):
        vectors = [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]
        payloads = [{"data": "hello", "user_id": "u1"}, {"data": "world", "user_id": "u2"}]
        ids = ["id1", "id2"]

        db.insert(vectors, payloads, ids)

        db.namespace.write.assert_called_once()
        call_kwargs = db.namespace.write.call_args[1]
        rows = call_kwargs["upsert_rows"]
        assert len(rows) == 2
        assert rows[0]["id"] == "id1"
        assert rows[0]["vector"] == [0.1, 0.2, 0.3, 0.4]
        assert rows[0]["data"] == "hello"
        assert rows[0]["user_id"] == "u1"
        assert rows[1]["id"] == "id2"
        assert call_kwargs["distance_metric"] == "cosine_distance"

    def test_insert_without_ids_generates_ids(self, db):
        vectors = [[0.1, 0.2, 0.3, 0.4]]
        db.insert(vectors)

        db.namespace.write.assert_called_once()
        call_kwargs = db.namespace.write.call_args[1]
        assert call_kwargs["upsert_rows"][0]["id"] == "0"

    def test_insert_without_payloads(self, db):
        vectors = [[0.1, 0.2, 0.3, 0.4]]
        ids = ["id1"]
        db.insert(vectors, ids=ids)

        call_kwargs = db.namespace.write.call_args[1]
        row = call_kwargs["upsert_rows"][0]
        assert row["id"] == "id1"
        assert row["vector"] == [0.1, 0.2, 0.3, 0.4]
        assert len(row) == 2  # only id and vector

    def test_insert_payload_does_not_overwrite_id_or_vector(self, db):
        """Payload with 'id' or 'vector' keys must not overwrite the actual values."""
        vectors = [[0.1, 0.2, 0.3, 0.4]]
        payloads = [{"id": "fake_id", "vector": "fake_vector", "data": "hello"}]
        ids = ["real_id"]
        db.insert(vectors, payloads, ids)

        call_kwargs = db.namespace.write.call_args[1]
        row = call_kwargs["upsert_rows"][0]
        assert row["id"] == "real_id"
        assert row["vector"] == [0.1, 0.2, 0.3, 0.4]
        assert row["data"] == "hello"

    def test_insert_batching(self, db):
        """batch_size=2, so 3 vectors should produce 2 write calls."""
        vectors = [[0.1] * 4, [0.2] * 4, [0.3] * 4]
        ids = ["a", "b", "c"]
        db.insert(vectors, ids=ids)

        assert db.namespace.write.call_count == 2
        first_call = db.namespace.write.call_args_list[0][1]
        second_call = db.namespace.write.call_args_list[1][1]
        assert len(first_call["upsert_rows"]) == 2
        assert len(second_call["upsert_rows"]) == 1


# ── _parse_output ────────────────────────────────────────────────────


class TestParseOutput:
    def test_parse_rows_with_dist_and_attributes(self, db):
        rows = [
            _make_row("id1", dist=0.1, data="hello", user_id="u1"),
            _make_row("id2", dist=0.3, data="world", user_id="u2"),
        ]
        results = db._parse_output(rows)

        assert len(results) == 2
        assert results[0].id == "id1"
        assert results[0].score == pytest.approx(0.9)
        assert results[0].payload == {"data": "hello", "user_id": "u1"}
        assert results[1].id == "id2"
        assert results[1].score == pytest.approx(0.7)
        assert results[1].payload == {"data": "world", "user_id": "u2"}

    def test_parse_rows_without_dist(self, db):
        rows = [_make_row("id1", data="hello")]
        results = db._parse_output(rows)

        assert results[0].score is None
        assert results[0].payload == {"data": "hello"}

    def test_parse_rows_strips_vector_and_id(self, db):
        rows = [_make_row("id1", dist=0.0, vector=[1.0, 2.0, 3.0, 4.0], data="test")]
        results = db._parse_output(rows)

        assert "vector" not in results[0].payload
        assert "id" not in results[0].payload
        assert "$dist" not in results[0].payload
        assert results[0].id == "id1"

    def test_parse_empty_rows(self, db):
        assert db._parse_output([]) == []


# ── _convert_filters ─────────────────────────────────────────────────


class TestConvertFilters:
    def test_none_filters(self, db):
        assert db._convert_filters(None) is None

    def test_empty_filters(self, db):
        assert db._convert_filters({}) is None

    def test_single_eq_filter(self, db):
        result = db._convert_filters({"user_id": "u1"})
        assert result == ("user_id", "Eq", "u1")

    def test_multiple_eq_filters(self, db):
        result = db._convert_filters({"user_id": "u1", "agent_id": "a1"})
        assert result[0] == "And"
        conditions = result[1]
        assert ("user_id", "Eq", "u1") in conditions
        assert ("agent_id", "Eq", "a1") in conditions

    def test_range_filter_gte_lte(self, db):
        result = db._convert_filters({"score": {"gte": 0.5, "lte": 1.0}})
        assert result[0] == "And"
        conditions = result[1]
        assert ("score", "Gte", 0.5) in conditions
        assert ("score", "Lte", 1.0) in conditions

    def test_range_filter_gte_only(self, db):
        result = db._convert_filters({"score": {"gte": 0.5}})
        assert result == ("score", "Gte", 0.5)

    def test_range_filter_lte_only(self, db):
        result = db._convert_filters({"score": {"lte": 1.0}})
        assert result == ("score", "Lte", 1.0)

    def test_mixed_eq_and_range_filters(self, db):
        result = db._convert_filters({"user_id": "u1", "score": {"gte": 0.5}})
        assert result[0] == "And"
        conditions = result[1]
        assert ("user_id", "Eq", "u1") in conditions
        assert ("score", "Gte", 0.5) in conditions


# ── search ───────────────────────────────────────────────────────────


class TestSearch:
    def test_search_basic(self, db):
        mock_response = MagicMock()
        mock_response.rows = [
            _make_row("id1", dist=0.1, data="hello"),
            _make_row("id2", dist=0.2, data="world"),
        ]
        db.namespace.query.return_value = mock_response

        results = db.search("test query", [0.1, 0.2, 0.3, 0.4], top_k=2)

        db.namespace.query.assert_called_once_with(
            rank_by=("vector", "ANN", [0.1, 0.2, 0.3, 0.4]),
            top_k=2,
            include_attributes=True,
        )
        assert len(results) == 2
        assert results[0].id == "id1"
        assert results[0].score == pytest.approx(0.9)

    def test_search_with_filters(self, db):
        mock_response = MagicMock()
        mock_response.rows = [_make_row("id1", dist=0.1, data="hello")]
        db.namespace.query.return_value = mock_response

        results = db.search(
            "query", [0.1, 0.2, 0.3, 0.4], top_k=5, filters={"user_id": "u1"}
        )

        call_kwargs = db.namespace.query.call_args[1]
        assert call_kwargs["filters"] == ("user_id", "Eq", "u1")
        assert len(results) == 1

    def test_search_no_results(self, db):
        mock_response = MagicMock()
        mock_response.rows = None
        db.namespace.query.return_value = mock_response

        results = db.search("query", [0.1, 0.2, 0.3, 0.4])
        assert results == []

    def test_search_empty_rows(self, db):
        mock_response = MagicMock()
        mock_response.rows = []
        db.namespace.query.return_value = mock_response

        results = db.search("query", [0.1, 0.2, 0.3, 0.4])
        assert results == []


# ── delete ───────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_by_string_id(self, db):
        db.delete("id1")
        db.namespace.write.assert_called_once_with(deletes=["id1"])

    def test_delete_by_int_id(self, db):
        db.delete(123)
        db.namespace.write.assert_called_once_with(deletes=["123"])


# ── update ───────────────────────────────────────────────────────────


class TestUpdate:
    def test_update_with_vector_and_payload(self, db):
        db.update("id1", vector=[0.5, 0.6, 0.7, 0.8], payload={"data": "updated"})

        db.namespace.write.assert_called_once()
        call_kwargs = db.namespace.write.call_args[1]
        row = call_kwargs["upsert_rows"][0]
        assert row["id"] == "id1"
        assert row["vector"] == [0.5, 0.6, 0.7, 0.8]
        assert row["data"] == "updated"
        assert call_kwargs["distance_metric"] == "cosine_distance"

    def test_update_vector_only(self, db):
        db.update("id1", vector=[0.5, 0.6, 0.7, 0.8])

        call_kwargs = db.namespace.write.call_args[1]
        row = call_kwargs["upsert_rows"][0]
        assert row["id"] == "id1"
        assert row["vector"] == [0.5, 0.6, 0.7, 0.8]
        assert "data" not in row

    def test_update_payload_only_uses_patch(self, db):
        """Payload-only updates should use patch_rows, not upsert_rows."""
        db.update("id1", vector=None, payload={"data": "patched", "user_id": "u1"})

        call_kwargs = db.namespace.write.call_args[1]
        row = call_kwargs["patch_rows"][0]
        assert row["id"] == "id1"
        assert row["data"] == "patched"
        assert row["user_id"] == "u1"
        assert "upsert_rows" not in call_kwargs

    def test_update_payload_does_not_overwrite_id(self, db):
        """Payload with an 'id' key must not overwrite the actual vector ID."""
        db.update("real_id", vector=None, payload={"id": "fake_id", "data": "test"})
        call_kwargs = db.namespace.write.call_args[1]
        row = call_kwargs["patch_rows"][0]
        assert row["id"] == "real_id"

    def test_update_nothing(self, db):
        """Neither vector nor payload: should not call write."""
        db.update("id1")
        db.namespace.write.assert_not_called()


# ── get ──────────────────────────────────────────────────────────────


class TestGet:
    def test_get_found(self, db):
        mock_response = MagicMock()
        mock_response.rows = [_make_row("id1", dist=0.0, data="hello", user_id="u1")]
        db.namespace.query.return_value = mock_response

        result = db.get("id1")

        db.namespace.query.assert_called_once_with(
            top_k=1,
            rank_by=("vector", "ANN", [0.0, 0.0, 0.0, 0.0]),
            filters=("id", "Eq", "id1"),
            include_attributes=True,
        )
        assert result is not None
        assert result.id == "id1"
        assert result.payload["data"] == "hello"
        assert result.payload["user_id"] == "u1"

    def test_get_not_found(self, db):
        mock_response = MagicMock()
        mock_response.rows = []
        db.namespace.query.return_value = mock_response

        result = db.get("nonexistent")
        assert result is None

    def test_get_none_rows(self, db):
        mock_response = MagicMock()
        mock_response.rows = None
        db.namespace.query.return_value = mock_response

        result = db.get("id1")
        assert result is None

    def test_get_handles_exception(self, db):
        db.namespace.query.side_effect = Exception("API error")
        result = db.get("id1")
        assert result is None


# ── list_cols ────────────────────────────────────────────────────────


class TestListCols:
    def test_list_cols(self, db):
        ns1 = MagicMock()
        ns1.id = "ns1"
        ns2 = MagicMock()
        ns2.id = "ns2"
        db.client.namespaces.return_value = [ns1, ns2]

        result = db.list_cols()
        assert len(result) == 2
        db.client.namespaces.assert_called_once()


# ── delete_col ───────────────────────────────────────────────────────


class TestDeleteCol:
    def test_delete_col(self, db):
        db.delete_col()
        db.namespace.delete_all.assert_called_once()

    def test_delete_col_handles_error(self, db):
        db.namespace.delete_all.side_effect = Exception("API error")
        # Should not raise
        db.delete_col()


# ── col_info ─────────────────────────────────────────────────────────


class TestColInfo:
    def test_col_info(self, db):
        mock_metadata = MagicMock()
        mock_metadata.approx_row_count = 42
        mock_metadata.approx_logical_bytes = 1024
        mock_metadata.created_at = datetime(2025, 1, 1)
        mock_metadata.updated_at = datetime(2025, 6, 1)
        db.namespace.metadata.return_value = mock_metadata

        info = db.col_info()
        assert info["name"] == "test_ns"
        assert info["approx_row_count"] == 42
        assert info["approx_logical_bytes"] == 1024

    def test_col_info_handles_error(self, db):
        db.namespace.metadata.side_effect = Exception("not found")
        info = db.col_info()
        assert info == {"name": "test_ns"}


# ── list ─────────────────────────────────────────────────────────────


class TestList:
    def test_list_returns_wrapped_format(self, db):
        """list() must return [[results]] for compatibility with main.py."""
        mock_response = MagicMock()
        mock_response.rows = [
            _make_row("id1", dist=0.1, data="hello"),
            _make_row("id2", dist=0.2, data="world"),
        ]
        db.namespace.query.return_value = mock_response

        result = db.list()

        # Must be wrapped: result[0] is the actual list
        assert isinstance(result, list)
        assert isinstance(result[0], list)
        assert len(result[0]) == 2
        assert result[0][0].id == "id1"
        assert result[0][1].id == "id2"

    def test_list_with_filters(self, db):
        mock_response = MagicMock()
        mock_response.rows = [_make_row("id1", dist=0.1, data="hello")]
        db.namespace.query.return_value = mock_response

        db.list(filters={"user_id": "u1"}, top_k=50)

        call_kwargs = db.namespace.query.call_args[1]
        assert call_kwargs["filters"] == ("user_id", "Eq", "u1")
        assert call_kwargs["top_k"] == 50

    def test_list_empty(self, db):
        mock_response = MagicMock()
        mock_response.rows = None
        db.namespace.query.return_value = mock_response

        result = db.list()
        assert result == [[]]

    def test_list_uses_zero_vector(self, db):
        mock_response = MagicMock()
        mock_response.rows = []
        db.namespace.query.return_value = mock_response

        db.list()
        call_kwargs = db.namespace.query.call_args[1]
        assert call_kwargs["rank_by"] == ("vector", "ANN", [0.0, 0.0, 0.0, 0.0])

    def test_list_compatible_with_main_py_get_all(self, db):
        """Simulate how main.py _get_all_from_vector_store unwraps list()."""
        mock_response = MagicMock()
        mock_response.rows = [_make_row("id1", dist=0.1, data="hello")]
        db.namespace.query.return_value = mock_response

        memories_result = db.list(filters={"user_id": "u1"})

        # Reproduce main.py unwrapping logic
        first_element = memories_result[0]
        if isinstance(first_element, (list, tuple)):
            actual_memories = first_element
        else:
            actual_memories = memories_result

        assert isinstance(actual_memories, list)
        assert len(actual_memories) == 1
        assert actual_memories[0].id == "id1"
        assert actual_memories[0].payload["data"] == "hello"

    def test_list_compatible_with_main_py_delete_all(self, db):
        """Simulate how main.py delete_all uses list()[0]."""
        mock_response = MagicMock()
        mock_response.rows = [
            _make_row("id1", dist=0.1, data="hello"),
            _make_row("id2", dist=0.2, data="world"),
        ]
        db.namespace.query.return_value = mock_response

        result = db.list(filters={"user_id": "u1"})
        memories = result[0]

        assert isinstance(memories, list)
        for mem in memories:
            assert hasattr(mem, "id")
            assert hasattr(mem, "payload")


# ── count ────────────────────────────────────────────────────────────


class TestCount:
    def test_count(self, db):
        mock_metadata = MagicMock()
        mock_metadata.approx_row_count = 100
        db.namespace.metadata.return_value = mock_metadata

        assert db.count() == 100

    def test_count_handles_error(self, db):
        db.namespace.metadata.side_effect = Exception("error")
        assert db.count() == 0


# ── reset ────────────────────────────────────────────────────────────


class TestReset:
    def test_reset_calls_delete_all(self, db):
        db.reset()
        db.namespace.delete_all.assert_called_once()


# ── Config ───────────────────────────────────────────────────────────


class TestConfig:
    def test_config_valid(self):
        with patch.dict("os.environ", {"TURBOPUFFER_API_KEY": "key"}):
            from mem0.configs.vector_stores.turbopuffer import TurbopufferConfig

            config = TurbopufferConfig()
            assert config.collection_name == "mem0"
            assert config.embedding_model_dims == 1536
            assert config.distance_metric == "cosine_distance"
            assert config.batch_size == 100
            assert config.region == "gcp-us-central1"

    def test_config_custom_values(self):
        from mem0.configs.vector_stores.turbopuffer import TurbopufferConfig

        config = TurbopufferConfig(
            collection_name="custom",
            embedding_model_dims=768,
            api_key="tpuf_key",
            region="aws-us-west-2",
            distance_metric="euclidean_squared",
            batch_size=50,
        )
        assert config.collection_name == "custom"
        assert config.embedding_model_dims == 768
        assert config.api_key == "tpuf_key"
        assert config.region == "aws-us-west-2"
        assert config.distance_metric == "euclidean_squared"
        assert config.batch_size == 50

    def test_config_rejects_extra_fields(self):
        from mem0.configs.vector_stores.turbopuffer import TurbopufferConfig

        with pytest.raises(ValueError, match="Extra fields not allowed"):
            TurbopufferConfig(api_key="key", unknown_field="value")

    def test_config_requires_api_key(self):
        from mem0.configs.vector_stores.turbopuffer import TurbopufferConfig

        with patch.dict("os.environ", {}, clear=True):
            import os
            os.environ.pop("TURBOPUFFER_API_KEY", None)
            with pytest.raises(ValueError, match="api_key"):
                TurbopufferConfig()

    def test_config_accepts_env_var(self):
        from mem0.configs.vector_stores.turbopuffer import TurbopufferConfig

        with patch.dict("os.environ", {"TURBOPUFFER_API_KEY": "env_key"}):
            config = TurbopufferConfig()
            assert config.api_key is None  # not set explicitly, but env var is present


# ── Factory Registration ─────────────────────────────────────────────


class TestFactoryRegistration:
    def test_vector_store_factory_has_turbopuffer(self):
        from mem0.utils.factory import VectorStoreFactory

        assert "turbopuffer" in VectorStoreFactory.provider_to_class
        assert VectorStoreFactory.provider_to_class["turbopuffer"] == "mem0.vector_stores.turbopuffer.TurbopufferDB"

    def test_vector_store_config_has_turbopuffer(self):
        from mem0.vector_stores.configs import VectorStoreConfig

        config = VectorStoreConfig.__private_attributes__["_provider_configs"].default
        assert "turbopuffer" in config
        assert config["turbopuffer"] == "TurbopufferConfig"

    def test_config_validation_pipeline(self):
        """Test that VectorStoreConfig correctly resolves turbopuffer config."""
        from mem0.vector_stores.configs import VectorStoreConfig

        with patch.dict("os.environ", {"TURBOPUFFER_API_KEY": "key"}):
            config = VectorStoreConfig(
                provider="turbopuffer",
                config={"collection_name": "test", "region": "gcp-us-central1"},
            )
            assert config.config.collection_name == "test"
            assert config.config.region == "gcp-us-central1"
            assert config.config.embedding_model_dims == 1536


# ── OutputData ───────────────────────────────────────────────────────


class TestOutputData:
    def test_output_data_has_required_fields(self):
        od = OutputData(id="test", score=0.9, payload={"data": "hello"})
        assert od.id == "test"
        assert od.score == 0.9
        assert od.payload == {"data": "hello"}

    def test_output_data_nullable_fields(self):
        od = OutputData(id=None, score=None, payload=None)
        assert od.id is None
        assert od.score is None
        assert od.payload is None

    def test_output_data_payload_access_pattern(self):
        """Test the exact access pattern used by main.py."""
        od = OutputData(
            id="mem1",
            score=0.95,
            payload={
                "data": "User likes sci-fi movies",
                "hash": "abc123",
                "created_at": "2025-01-01",
                "updated_at": "2025-06-01",
                "user_id": "alice",
                "agent_id": "agent1",
            },
        )
        assert od.payload.get("data", "") == "User likes sci-fi movies"
        assert od.payload.get("hash") == "abc123"
        assert od.payload.get("created_at") == "2025-01-01"
        assert od.payload.get("user_id") == "alice"
        assert od.payload.get("run_id") is None  # not present, should return None
