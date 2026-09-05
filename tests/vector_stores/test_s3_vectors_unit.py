"""Unit tests for the AWS S3 Vectors backend (mem0/vector_stores/s3_vectors.py)."""

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


class TestS3Vectors:
    """Tests for the AWS S3 Vectors backend."""

    @pytest.fixture(autouse=True)
    def stub_boto3(self, monkeypatch):
        boto3_stub = MagicMock()
        botocore_mod = ModuleType("botocore")
        botocore_exc = ModuleType("botocore.exceptions")

        class ClientError(Exception):
            def __init__(self, error_response, operation_name=""):
                self.response = error_response
                super().__init__(str(error_response))

        botocore_exc.ClientError = ClientError
        botocore_mod.exceptions = botocore_exc

        monkeypatch.setitem(sys.modules, "boto3", boto3_stub)
        monkeypatch.setitem(sys.modules, "botocore", botocore_mod)
        monkeypatch.setitem(sys.modules, "botocore.exceptions", botocore_exc)
        monkeypatch.delitem(sys.modules, "mem0.vector_stores.s3_vectors", raising=False)

        self.ClientError = ClientError
        self.boto3_stub = boto3_stub
        yield

    def _make_store(self, mock_client=None):
        from mem0.vector_stores.s3_vectors import S3Vectors

        if mock_client is None:
            mock_client = MagicMock()
        mock_client.get_vector_bucket.return_value = {}
        mock_client.get_index.return_value = {}
        self.boto3_stub.client.return_value = mock_client

        store = S3Vectors(
            vector_bucket_name="test-bucket",
            collection_name="test-index",
            embedding_model_dims=3,
        )
        return store, mock_client

    # --- init ---

    def test_init_bucket_already_exists(self):
        store, mock_client = self._make_store()
        mock_client.get_vector_bucket.assert_called_once_with(vectorBucketName="test-bucket")
        mock_client.create_vector_bucket.assert_not_called()

    def test_init_creates_bucket_when_not_found(self):
        from mem0.vector_stores.s3_vectors import S3Vectors

        mock_client = MagicMock()
        mock_client.get_vector_bucket.side_effect = self.ClientError(
            {"Error": {"Code": "NotFoundException"}}
        )
        mock_client.get_index.return_value = {}
        self.boto3_stub.client.return_value = mock_client

        S3Vectors(vector_bucket_name="new-bucket", collection_name="test-index", embedding_model_dims=3)

        mock_client.create_vector_bucket.assert_called_once_with(vectorBucketName="new-bucket")

    def test_init_creates_index_when_not_found(self):
        from mem0.vector_stores.s3_vectors import S3Vectors

        mock_client = MagicMock()
        mock_client.get_vector_bucket.return_value = {}
        mock_client.get_index.side_effect = self.ClientError(
            {"Error": {"Code": "NotFoundException"}}
        )
        self.boto3_stub.client.return_value = mock_client

        S3Vectors(vector_bucket_name="test-bucket", collection_name="new-index", embedding_model_dims=3)

        mock_client.create_index.assert_called_once()
        kw = mock_client.create_index.call_args.kwargs
        assert kw["indexName"] == "new-index"
        assert kw["dimension"] == 3

    def test_init_reraises_unexpected_bucket_error(self):
        from mem0.vector_stores.s3_vectors import S3Vectors

        mock_client = MagicMock()
        mock_client.get_vector_bucket.side_effect = self.ClientError(
            {"Error": {"Code": "AccessDenied"}}
        )
        self.boto3_stub.client.return_value = mock_client

        with pytest.raises(self.ClientError):
            S3Vectors(vector_bucket_name="b", collection_name="idx", embedding_model_dims=3)

    # --- insert ---

    def test_insert_calls_put_vectors(self):
        store, mock_client = self._make_store()
        store.insert(
            vectors=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            payloads=[{"data": "mem1"}, {"data": "mem2"}],
            ids=["id1", "id2"],
        )
        mock_client.put_vectors.assert_called_once()
        kw = mock_client.put_vectors.call_args.kwargs
        assert kw["vectorBucketName"] == "test-bucket"
        assert kw["indexName"] == "test-index"
        vecs = kw["vectors"]
        assert len(vecs) == 2
        assert vecs[0]["key"] == "id1"
        assert vecs[0]["data"] == {"float32": [0.1, 0.2, 0.3]}
        assert vecs[0]["metadata"] == {"data": "mem1"}

    def test_insert_without_payloads(self):
        store, mock_client = self._make_store()
        store.insert(vectors=[[0.1, 0.2, 0.3]], ids=["id1"])
        kw = mock_client.put_vectors.call_args.kwargs
        assert kw["vectors"][0]["metadata"] == {}

    # --- search ---

    def test_search_returns_parsed_results(self):
        store, mock_client = self._make_store()
        mock_client.query_vectors.return_value = {
            "vectors": [
                {"key": "id1", "metadata": {"data": "mem1", "user_id": "u1"}, "distance": 0.2}
            ]
        }
        results = store.search(query="test", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert len(results) == 1
        assert results[0].id == "id1"
        assert abs(results[0].score - 0.8) < 1e-6
        assert results[0].payload["data"] == "mem1"

    def test_search_passes_filters(self):
        store, mock_client = self._make_store()
        mock_client.query_vectors.return_value = {"vectors": []}
        store.search(query="t", vectors=[0.1, 0.2, 0.3], top_k=5, filters={"user_id": "u1"})
        kw = mock_client.query_vectors.call_args.kwargs
        assert kw["filter"] == {"user_id": "u1"}

    def test_search_no_filters_omits_filter_param(self):
        store, mock_client = self._make_store()
        mock_client.query_vectors.return_value = {"vectors": []}
        store.search(query="t", vectors=[0.1, 0.2, 0.3], top_k=5)
        kw = mock_client.query_vectors.call_args.kwargs
        assert "filter" not in kw

    def test_search_parses_json_string_metadata(self):
        store, mock_client = self._make_store()
        mock_client.query_vectors.return_value = {
            "vectors": [{"key": "id1", "metadata": json.dumps({"data": "mem1"}), "distance": 0.0}]
        }
        results = store.search(query="t", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert results[0].payload["data"] == "mem1"

    def test_search_handles_none_distance(self):
        store, mock_client = self._make_store()
        mock_client.query_vectors.return_value = {
            "vectors": [{"key": "id1", "metadata": {}, "distance": None}]
        }
        results = store.search(query="t", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert results[0].score is None

    # --- delete ---

    def test_delete_calls_delete_vectors(self):
        store, mock_client = self._make_store()
        store.delete("id1")
        mock_client.delete_vectors.assert_called_once_with(
            vectorBucketName="test-bucket",
            indexName="test-index",
            keys=["id1"],
        )

    # --- get ---

    def test_get_returns_output_data(self):
        store, mock_client = self._make_store()
        mock_client.get_vectors.return_value = {
            "vectors": [{"key": "id1", "metadata": {"data": "mem1"}, "distance": None}]
        }
        result = store.get("id1")
        assert result is not None
        assert result.id == "id1"
        assert result.payload["data"] == "mem1"

    def test_get_returns_none_when_empty(self):
        store, mock_client = self._make_store()
        mock_client.get_vectors.return_value = {"vectors": []}
        assert store.get("missing") is None

    # --- update ---

    def test_update_with_vector_calls_insert(self):
        store, mock_client = self._make_store()
        store.update("id1", vector=[0.1, 0.2, 0.3], payload={"data": "updated"})
        mock_client.put_vectors.assert_called_once()

    def test_update_without_vector_fetches_existing_float32(self):
        store, mock_client = self._make_store()
        mock_client.get_vectors.side_effect = [
            {"vectors": [{"key": "id1", "metadata": {"data": "orig"}, "distance": None}]},
            {"vectors": [{"data": {"float32": [0.1, 0.2, 0.3]}, "metadata": {"data": "orig"}}]},
        ]
        store.update("id1", vector=None, payload={"data": "updated"})
        mock_client.put_vectors.assert_called_once()

    def test_update_without_vector_skips_when_not_found(self):
        store, mock_client = self._make_store()
        mock_client.get_vectors.return_value = {"vectors": []}
        store.update("id1", vector=None, payload={"data": "updated"})
        mock_client.put_vectors.assert_not_called()

    # --- list ---

    def test_list_filters_by_payload_field(self):
        store, mock_client = self._make_store()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "vectors": [
                    {"key": "id1", "metadata": {"data": "m1", "user_id": "u1"}, "distance": None},
                    {"key": "id2", "metadata": {"data": "m2", "user_id": "u2"}, "distance": None},
                ]
            }
        ]
        mock_client.get_paginator.return_value = paginator
        results = store.list(filters={"user_id": "u1"})
        assert isinstance(results, list) and isinstance(results[0], list)
        assert len(results[0]) == 1
        assert results[0][0].payload["user_id"] == "u1"

    def test_list_no_filter_returns_all(self):
        store, mock_client = self._make_store()
        paginator = MagicMock()
        paginator.paginate.return_value = [
            {
                "vectors": [
                    {"key": "id1", "metadata": {"data": "m1"}, "distance": None},
                    {"key": "id2", "metadata": {"data": "m2"}, "distance": None},
                ]
            }
        ]
        mock_client.get_paginator.return_value = paginator
        results = store.list()
        assert len(results[0]) == 2

    # --- col helpers ---

    def test_list_cols(self):
        store, mock_client = self._make_store()
        mock_client.list_indexes.return_value = {
            "indexes": [{"indexName": "idx1"}, {"indexName": "idx2"}]
        }
        assert store.list_cols() == ["idx1", "idx2"]

    def test_col_info(self):
        store, mock_client = self._make_store()
        mock_client.get_index.return_value = {"index": {"dimension": 3, "status": "ACTIVE"}}
        assert store.col_info() == {"dimension": 3, "status": "ACTIVE"}

    def test_reset_deletes_and_recreates_index(self):
        store, mock_client = self._make_store()
        mock_client.get_index.side_effect = self.ClientError(
            {"Error": {"Code": "NotFoundException"}}
        )
        store.reset()
        mock_client.delete_index.assert_called_once_with(
            vectorBucketName="test-bucket", indexName="test-index"
        )
        mock_client.create_index.assert_called_once()
