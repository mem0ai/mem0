import os
from typing import Any, Dict, Generator, List, Tuple
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("topk_sdk", reason="topk-sdk not installed")

from mem0.vector_stores.topk import OutputData, TopK


@pytest.fixture
def mock_client() -> Generator[Tuple[MagicMock, MagicMock, MagicMock], None, None]:
    with patch("mem0.vector_stores.topk.Client") as MockClient:
        client_instance: MagicMock = MagicMock()
        col_instance: MagicMock = MagicMock()
        cols_instance: MagicMock = MagicMock()
        client_instance.collection.return_value = col_instance
        client_instance.collections.return_value = cols_instance
        # create_col calls collections().create() — silence CollectionAlreadyExistsError
        cols_instance.create.return_value = None
        col_instance.upsert.return_value = "lsn-upsert"
        col_instance.delete.return_value = "lsn-delete"
        MockClient.return_value = client_instance
        yield client_instance, col_instance, cols_instance


@pytest.fixture
def db(mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> TopK:
    return TopK(
        collection_name="test_col",
        embedding_model_dims=4,
        api_key="topk_test_key",
        region="aws-eu-central-1-sunflower",
        distance_metric="cosine",
        batch_size=2,
    )


# ── Initialization ───────────────────────────────────────────────────


class TestInit:
    def test_init_with_api_key_and_region(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        db = TopK(
            collection_name="my_col",
            embedding_model_dims=128,
            api_key="my_key",
            region="us-east-1",
        )
        assert db.collection_name == "my_col"
        assert db.embedding_model_dims == 128
        assert db.distance_metric == "cosine"
        assert db.batch_size == 100

    def test_init_with_env_vars(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        with patch.dict("os.environ", {"TOPK_API_KEY": "env_key", "TOPK_REGION": "env-region"}):
            db = TopK(collection_name="test", embedding_model_dims=4)
            assert db.collection_name == "test"

    def test_init_without_api_key_raises(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        env = {k: v for k, v in os.environ.items() if k not in ("TOPK_API_KEY", "TOPK_REGION")}
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(ValueError, match="TOPK_API_KEY"):
                TopK(collection_name="test", embedding_model_dims=4)

    def test_init_without_region_raises(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        env = {k: v for k, v in os.environ.items() if k != "TOPK_REGION"}
        env["TOPK_API_KEY"] = "key"
        with patch.dict("os.environ", env, clear=True):
            with pytest.raises(ValueError, match="TOPK_REGION"):
                TopK(collection_name="test", embedding_model_dims=4)

    def test_init_with_host_and_https(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        with patch("mem0.vector_stores.topk.Client") as MockClient:
            MockClient.return_value = mock_client[0]
            TopK(
                collection_name="test",
                embedding_model_dims=4,
                api_key="key",
                region="us-east-1",
                host="topk.dev",
                https=False,
            )
            call_kwargs: Dict[str, Any] = MockClient.call_args[1]
            assert call_kwargs["host"] == "topk.dev"
            assert call_kwargs["https"] is False

    def test_init_host_from_env(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        with patch("mem0.vector_stores.topk.Client") as MockClient:
            MockClient.return_value = mock_client[0]
            with patch.dict("os.environ", {"TOPK_HOST": "custom.host", "TOPK_HTTPS": "false"}):
                TopK(
                    collection_name="test",
                    embedding_model_dims=4,
                    api_key="key",
                    region="us-east-1",
                )
                call_kwargs: Dict[str, Any] = MockClient.call_args[1]
                assert call_kwargs["host"] == "custom.host"
                assert call_kwargs["https"] is False

    def test_init_https_defaults_to_true_when_no_env(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        with patch("mem0.vector_stores.topk.Client") as MockClient:
            MockClient.return_value = mock_client[0]
            env = {k: v for k, v in os.environ.items() if k != "TOPK_HTTPS"}
            with patch.dict("os.environ", env, clear=True):
                TopK(
                    collection_name="test",
                    embedding_model_dims=4,
                    api_key="key",
                    region="us-east-1",
                )
                call_kwargs: Dict[str, Any] = MockClient.call_args[1]
                assert call_kwargs["https"] is True

    def test_init_no_host_kwarg_when_not_set(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        with patch("mem0.vector_stores.topk.Client") as MockClient:
            MockClient.return_value = mock_client[0]
            env = {k: v for k, v in os.environ.items() if k != "TOPK_HOST"}
            with patch.dict("os.environ", env, clear=True):
                TopK(
                    collection_name="test",
                    embedding_model_dims=4,
                    api_key="key",
                    region="us-east-1",
                )
                call_kwargs: Dict[str, Any] = MockClient.call_args[1]
                assert "host" not in call_kwargs

    def test_init_calls_create_col(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, _, cols_instance = mock_client
        TopK(
            collection_name="mycol",
            embedding_model_dims=4,
            api_key="key",
            region="us-east-1",
        )
        cols_instance.create.assert_called_once()
        args, kwargs = cols_instance.create.call_args
        assert args[0] == "mycol"
        assert "vector" in kwargs["schema"]
        # BM25 index lives on the lemmatized text (Mem0 core sends lemmatized queries)
        assert "text_lemmatized" in kwargs["schema"]


# ── Metric mapping ───────────────────────────────────────────────────


class TestMetricMapping:
    def test_cosine_metric(self, db: TopK) -> None:
        assert db._topk_metric() == "cosine"

    def test_euclidean_metric(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        db = TopK(collection_name="c", embedding_model_dims=4, api_key="k", region="r", distance_metric="euclidean")
        assert db._topk_metric() == "euclidean"

    def test_dot_metric(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        db = TopK(collection_name="c", embedding_model_dims=4, api_key="k", region="r", distance_metric="dot")
        assert db._topk_metric() == "dot_product"

    def test_unknown_metric_defaults_to_cosine(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        db = TopK(collection_name="c", embedding_model_dims=4, api_key="k", region="r", distance_metric="unknown")
        assert db._topk_metric() == "cosine"


# ── Score conversion ─────────────────────────────────────────────────


class TestToSimilarity:
    def test_cosine_passthrough(self, db: TopK) -> None:
        # cosine: fn.vector_distance returns similarity directly (1=identical)
        assert db._to_similarity(1.0) == pytest.approx(1.0)
        assert db._to_similarity(0.7) == pytest.approx(0.7)
        assert db._to_similarity(0.0) == pytest.approx(0.0)

    def test_euclidean_conversion(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        db = TopK(collection_name="c", embedding_model_dims=4, api_key="k", region="r", distance_metric="euclidean")
        assert db._to_similarity(0.0) == pytest.approx(1.0)  # identical
        assert db._to_similarity(1.0) == pytest.approx(0.5)

    def test_dot_product_passthrough(self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        db = TopK(collection_name="c", embedding_model_dims=4, api_key="k", region="r", distance_metric="dot")
        assert db._to_similarity(0.8) == pytest.approx(0.8)
        assert db._to_similarity(1.5) == pytest.approx(1.5)


# ── Filter conversion ────────────────────────────────────────────────


class TestConvertFilters:
    def test_single_equality(self, db: TopK) -> None:
        result = db._convert_filters({"user_id": "alice"})
        assert result is not None

    def test_multiple_conditions_returns_all(self, db: TopK) -> None:
        result = db._convert_filters({"user_id": "alice", "category": "movies"})
        assert result is not None

    def test_range_conditions(self, db: TopK) -> None:
        result = db._convert_filters({"timestamp": {"gte": 1000, "lte": 2000}})
        assert result is not None

    def test_eq_operator(self, db: TopK) -> None:
        result = db._convert_filters({"status": {"eq": "active"}})
        assert result is not None

    def test_ne_operator(self, db: TopK) -> None:
        result = db._convert_filters({"status": {"ne": "inactive"}})
        assert result is not None

    def test_in_operator(self, db: TopK) -> None:
        result = db._convert_filters({"tag": {"in": ["a", "b", "c"]}})
        assert result is not None

    def test_nin_operator(self, db: TopK) -> None:
        result = db._convert_filters({"tag": {"nin": ["x", "y"]}})
        assert result is not None

    def test_contains_operator(self, db: TopK) -> None:
        result = db._convert_filters({"text": {"contains": "hello"}})
        assert result is not None

    def test_unknown_operator_raises(self, db: TopK) -> None:
        with pytest.raises(ValueError, match="Unsupported filter operator"):
            db._convert_filters({"field": {"regex": ".*"}})


# ── insert ───────────────────────────────────────────────────────────


class TestInsert:
    def test_insert_with_ids_and_payloads(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, _ = mock_client
        vectors: List[List[float]] = [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]
        payloads: List[Dict[str, Any]] = [{"data": "hello", "user_id": "u1"}, {"data": "world", "user_id": "u2"}]
        ids: List[str] = ["id1", "id2"]

        db.insert(vectors, payloads, ids)

        col_instance.upsert.assert_called_once()
        docs: List[Dict[str, Any]] = col_instance.upsert.call_args[0][0]
        assert len(docs) == 2
        assert docs[0]["_id"] == "id1"
        assert docs[0]["vector"] == [0.1, 0.2, 0.3, 0.4]
        assert docs[0]["data"] == "hello"

    def test_insert_without_ids_generates_ids(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, col_instance, _ = mock_client
        db.insert([[0.1, 0.2, 0.3, 0.4]])

        docs: List[Dict[str, Any]] = col_instance.upsert.call_args[0][0]
        assert docs[0]["_id"] == "0"

    def test_insert_batching(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        """batch_size=2, so 3 vectors → 2 upsert calls."""
        _, col_instance, _ = mock_client
        vectors: List[List[float]] = [[0.1] * 4, [0.2] * 4, [0.3] * 4]
        ids: List[str] = ["a", "b", "c"]
        db.insert(vectors, ids=ids)

        assert col_instance.upsert.call_count == 2
        assert db._last_write_lsn == "lsn-upsert"

    def test_insert_records_last_batch_lsn(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, col_instance, _ = mock_client
        col_instance.upsert.side_effect = ["lsn-batch-1", "lsn-batch-2"]
        vectors: List[List[float]] = [[0.1] * 4, [0.2] * 4, [0.3] * 4]
        db.insert(vectors, ids=["a", "b", "c"])

        assert db._last_write_lsn == "lsn-batch-2"


# ── write LSN propagation ────────────────────────────────────────────


class TestWriteLsn:
    def test_search_passes_lsn_after_insert(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, col_instance, _ = mock_client
        col_instance.query.return_value = []
        db.insert([[0.1, 0.2, 0.3, 0.4]], ids=["id1"])

        db.search(query="test", vectors=[0.1, 0.2, 0.3, 0.4])

        assert col_instance.query.call_args.kwargs.get("lsn") == "lsn-upsert"

    def test_get_passes_lsn_after_insert(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, col_instance, _ = mock_client
        col_instance.get.return_value = {}
        db.insert([[0.1, 0.2, 0.3, 0.4]], ids=["id1"])

        db.get("id1")

        assert col_instance.get.call_args.kwargs.get("lsn") == "lsn-upsert"

    def test_update_records_lsn(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, _ = mock_client
        db.update("id1", payload={"data": "updated"})

        assert db._last_write_lsn == "lsn-upsert"
        assert col_instance.upsert.call_count == 1

    def test_delete_records_lsn(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, _ = mock_client
        db.delete("id1")

        assert db._last_write_lsn == "lsn-delete"
        col_instance.delete.assert_called_once_with(["id1"])

    def test_delete_col_clears_lsn(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, cols_instance = mock_client
        db.insert([[0.1, 0.2, 0.3, 0.4]], ids=["id1"])
        cols_instance.delete.return_value = None

        db.delete_col()

        assert db._last_write_lsn is None


# ── search ───────────────────────────────────────────────────────────


class TestSearch:
    def test_search_returns_output_data(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, _ = mock_client
        col_instance.query.return_value = [
            {"_id": "id1", "score": 0.2, "data": "hello", "user_id": "u1", "category": "movies"},
            {"_id": "id2", "score": 0.5, "data": "world", "user_id": "u2"},
        ]

        results: List[OutputData] = db.search(
            query="test",
            vectors=[0.1, 0.2, 0.3, 0.4],
            top_k=2,
            filters={"category": {"eq": "movies"}},
        )

        assert len(results) == 2
        assert results[0].id == "id1"
        assert results[0].score == pytest.approx(0.2)  # cosine: raw similarity passed through
        assert results[0].payload is not None
        assert results[0].payload["data"] == "hello"
        # filter keys are added to the select, so filtered-on metadata is returned
        assert results[0].payload["category"] == "movies"
        assert "vector" not in results[0].payload
        assert "_id" not in results[0].payload
        assert "score" not in results[0].payload
        # single-RPC path — no get() hydration
        col_instance.get.assert_not_called()

    def test_search_empty_results(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, _ = mock_client
        col_instance.query.return_value = []
        results: List[OutputData] = db.search(query="test", vectors=[0.1, 0.2, 0.3, 0.4])
        assert results == []


# ── field selection ──────────────────────────────────────────────────


class TestSelectFields:
    def test_no_filters_returns_mem0_fields(self, db: TopK) -> None:
        from mem0.vector_stores.topk import _MEM0_FIELDS

        assert db._select_fields(None) == list(_MEM0_FIELDS)

    def test_filter_keys_are_appended(self, db: TopK) -> None:
        fields = db._select_fields({"category": {"eq": "movies"}, "user_id": "alice"})
        assert "category" in fields
        # core field used as a filter key is not duplicated
        assert fields.count("user_id") == 1

    def test_reserved_keys_are_excluded(self, db: TopK) -> None:
        fields = db._select_fields({"score": {"gt": 0.5}, "_id": "x", "vector": "y"})
        assert "score" not in fields
        assert "_id" not in fields
        assert "vector" not in fields


# ── keyword_search ───────────────────────────────────────────────────


class TestKeywordSearch:
    def test_keyword_search_returns_raw_bm25_scores(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, col_instance, _ = mock_client
        col_instance.query.return_value = [
            {"_id": "id1", "score": 3.5, "data": "sci-fi movie", "text_lemmatized": "sci-fi movie"},
        ]

        results: List[OutputData] = db.keyword_search(query="sci-fi", top_k=5)

        assert len(results) == 1
        assert results[0].id == "id1"
        assert results[0].score == pytest.approx(3.5)  # BM25 passes through as-is
        assert results[0].payload is not None
        assert results[0].payload["data"] == "sci-fi movie"

    def test_keyword_search_bm25_not_inverted_for_euclidean(
        self, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """BM25 scores must NOT go through the euclidean distance→similarity inversion."""
        _, col_instance, _ = mock_client
        db = TopK(collection_name="c", embedding_model_dims=4, api_key="k", region="r", distance_metric="euclidean")
        col_instance.query.return_value = [{"_id": "id1", "score": 8.0, "data": "best match"}]

        results: List[OutputData] = db.keyword_search(query="best match")

        assert results[0].score == pytest.approx(8.0)

    def test_keyword_search_empty_results(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, _ = mock_client
        col_instance.query.return_value = []
        results: List[OutputData] = db.keyword_search(query="nothing")
        assert results == []


# ── delete ───────────────────────────────────────────────────────────


class TestDelete:
    def test_delete_calls_collection_delete(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, col_instance, _ = mock_client
        db.delete("vec_id")
        col_instance.delete.assert_called_once_with(["vec_id"])

    def test_delete_converts_int_id_to_str(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, _ = mock_client
        db.delete(42)
        col_instance.delete.assert_called_once_with(["42"])


# ── update ───────────────────────────────────────────────────────────


class TestUpdate:
    def test_update_with_vector_and_payload(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, col_instance, _ = mock_client
        db.update("id1", vector=[0.1, 0.2, 0.3, 0.4], payload={"data": "updated"})

        col_instance.upsert.assert_called_once()
        docs: List[Dict[str, Any]] = col_instance.upsert.call_args[0][0]
        assert docs[0]["_id"] == "id1"
        assert docs[0]["vector"] == [0.1, 0.2, 0.3, 0.4]
        assert docs[0]["data"] == "updated"

    def test_update_payload_only(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, _ = mock_client
        db.update("id1", payload={"data": "new"})

        docs: List[Dict[str, Any]] = col_instance.upsert.call_args[0][0]
        assert "vector" not in docs[0]
        assert docs[0]["data"] == "new"


# ── get ──────────────────────────────────────────────────────────────


class TestGet:
    def test_get_existing_document(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, _ = mock_client
        col_instance.get.return_value = {"id1": {"_id": "id1", "data": "hello", "user_id": "u1"}}

        result = db.get("id1")

        assert result is not None
        assert result.id == "id1"
        assert result.score is None
        assert result.payload is not None
        assert result.payload["data"] == "hello"
        assert "_id" not in result.payload
        assert "vector" not in result.payload

    def test_get_missing_document_returns_none(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, col_instance, _ = mock_client
        col_instance.get.return_value = {}

        result = db.get("missing_id")
        assert result is None

    def test_get_empty_results_returns_none(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, col_instance, _ = mock_client
        col_instance.get.return_value = None

        result = db.get("id1")
        assert result is None


# ── list ─────────────────────────────────────────────────────────────


class TestList:
    def test_list_returns_nested_list(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, _ = mock_client
        col_instance.query.return_value = [
            {"_id": "id1", "data": "hello"},
            {"_id": "id2", "data": "world"},
        ]

        results: List[List[OutputData]] = db.list()

        assert isinstance(results, list)
        assert isinstance(results[0], list)
        assert len(results[0]) == 2
        assert results[0][0].id == "id1"
        assert results[0][0].score is None
        assert results[0][0].payload is not None
        assert results[0][0].payload["data"] == "hello"

    def test_list_propagates_errors(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        """Backend failures must propagate, not masquerade as 'no memories' (matches qdrant/pinecone)."""
        _, col_instance, _ = mock_client
        col_instance.query.side_effect = RuntimeError("connection error")

        with pytest.raises(RuntimeError, match="connection error"):
            db.list()


# ── col_info ─────────────────────────────────────────────────────────


class TestColInfo:
    def test_col_info_success(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, col_instance, cols_instance = mock_client
        col_obj = MagicMock()
        col_obj.name = "test_col"
        col_obj.region = "aws-us-east-1-elastica"
        cols_instance.get.return_value = col_obj
        col_instance.count.return_value = 42

        info: Dict[str, Any] = db.col_info()

        assert info["name"] == "test_col"
        assert info["count"] == 42
        assert info["region"] == "aws-us-east-1-elastica"

    def test_col_info_exception_returns_name_only(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, col_instance, cols_instance = mock_client
        cols_instance.get.side_effect = Exception("error")

        info: Dict[str, Any] = db.col_info()
        assert info == {"name": "test_col"}


# ── delete_col / list_cols / reset ───────────────────────────────────


class TestCollectionOps:
    def test_delete_col_calls_collections_delete(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, _, cols_instance = mock_client
        db.delete_col()
        cols_instance.delete.assert_called_once_with("test_col")

    def test_list_cols(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, _, cols_instance = mock_client
        c1, c2 = MagicMock(), MagicMock()
        c1.name = "col1"
        c2.name = "col2"
        cols_instance.list.return_value = [c1, c2]

        result: List[str] = db.list_cols()
        assert result == ["col1", "col2"]

    def test_reset_deletes_and_recreates(self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]) -> None:
        _, _, cols_instance = mock_client
        cols_instance.create.reset_mock()
        db.reset()

        cols_instance.delete.assert_called_once_with("test_col")
        cols_instance.create.assert_called_once()


# ── get_user_id / set_user_id ────────────────────────────────────────


class TestUserId:
    def test_get_user_id_returns_cached_value(self, db: TopK) -> None:
        db._cached_user_id = "cached-user"
        assert db.get_user_id() == "cached-user"

    def test_get_user_id_reads_persisted_record(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        client_instance, col_instance, _ = mock_client
        migrations_col = MagicMock()
        migrations_col.get.return_value = {"user_id_record": {"user_id": "stored-user"}}
        client_instance.collection.side_effect = lambda name, partition=None: (
            migrations_col if name == "memory_migrations" else col_instance
        )

        assert db.get_user_id() == "stored-user"
        migrations_col.get.assert_called_once_with(["user_id_record"])
        migrations_col.upsert.assert_not_called()

    def test_get_user_id_creates_record_when_missing(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        client_instance, col_instance, _ = mock_client
        migrations_col = MagicMock()
        migrations_col.get.return_value = {}
        migrations_col.upsert.return_value = "lsn-mig"
        client_instance.collection.side_effect = lambda name, partition=None: (
            migrations_col if name == "memory_migrations" else col_instance
        )

        user_id = db.get_user_id()

        assert isinstance(user_id, str)
        assert len(user_id) > 0
        migrations_col.upsert.assert_called_once()
        assert migrations_col.upsert.call_args[0][0][0]["user_id"] == user_id
        assert db._last_write_lsn is None

    def test_set_user_id_persists_without_lsn(
        self, db: TopK, mock_client: Tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        client_instance, col_instance, _ = mock_client
        migrations_col = MagicMock()
        migrations_col.upsert.return_value = "lsn-mig"
        client_instance.collection.side_effect = lambda name, partition=None: (
            migrations_col if name == "memory_migrations" else col_instance
        )

        db.set_user_id("custom-user")

        migrations_col.upsert.assert_called_once_with(
            [{"_id": "user_id_record", "user_id": "custom-user"}]
        )
        assert db._cached_user_id == "custom-user"
        assert db._last_write_lsn is None
