"""Unit tests for the Google Vertex AI Matching Engine backend (mem0/vector_stores/vertex_ai_vector_search.py)."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest


class TestGoogleMatchingEngine:
    """Tests for the Google Vertex AI Matching Engine backend."""

    @pytest.fixture(autouse=True)
    def stub_google(self, monkeypatch):
        class GoogleAPIError(Exception):
            pass

        class NotFound(GoogleAPIError):
            pass

        class PermissionDenied(GoogleAPIError):
            pass

        class InvalidArgument(GoogleAPIError):
            pass

        google_mod = ModuleType("google")
        google_cloud_mod = ModuleType("google.cloud")
        aiplatform_mod = ModuleType("google.cloud.aiplatform")
        aiplatform_v1_mod = ModuleType("google.cloud.aiplatform_v1")
        google_api_core_mod = ModuleType("google.api_core")
        google_api_core_exc_mod = ModuleType("google.api_core.exceptions")
        google_oauth2_mod = ModuleType("google.oauth2")
        service_account_mod = ModuleType("google.oauth2.service_account")

        google_api_core_exc_mod.GoogleAPIError = GoogleAPIError
        google_api_core_exc_mod.NotFound = NotFound
        google_api_core_exc_mod.PermissionDenied = PermissionDenied
        google_api_core_exc_mod.InvalidArgument = InvalidArgument
        google_api_core_mod.exceptions = google_api_core_exc_mod

        aiplatform_v1_types_mod = ModuleType("google.cloud.aiplatform_v1.types")
        aiplatform_v1_types_index_mod = ModuleType("google.cloud.aiplatform_v1.types.index")
        mock_datapoint_cls = MagicMock()
        aiplatform_v1_types_index_mod.IndexDatapoint = mock_datapoint_cls
        aiplatform_v1_types_mod.index = aiplatform_v1_types_index_mod
        aiplatform_v1_mod.types = aiplatform_v1_types_mod
        aiplatform_v1_mod.MatchServiceClient = MagicMock()
        aiplatform_v1_mod.IndexDatapoint = mock_datapoint_cls
        aiplatform_v1_mod.FindNeighborsRequest = MagicMock()

        me_mod = ModuleType("google.cloud.aiplatform.matching_engine")
        me_ep_mod = ModuleType(
            "google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint"
        )

        class Namespace:
            def __init__(self, name, allow_list, deny_list):
                self.name = name
                self.allow_list = allow_list
                self.deny_list = deny_list

        me_ep_mod.Namespace = Namespace
        me_mod.matching_engine_index_endpoint = me_ep_mod

        langchain_core_mod = ModuleType("langchain_core")
        langchain_docs_mod = ModuleType("langchain_core.documents")

        class Document:
            def __init__(self, page_content="", metadata=None):
                self.page_content = page_content
                self.metadata = metadata or {}

        langchain_docs_mod.Document = Document
        langchain_core_mod.documents = langchain_docs_mod

        mock_index = MagicMock()
        mock_endpoint = MagicMock()
        aiplatform_mod.init = MagicMock()
        aiplatform_mod.MatchingEngineIndex = MagicMock(return_value=mock_index)
        aiplatform_mod.MatchingEngineIndexEndpoint = MagicMock(return_value=mock_endpoint)

        # Wire parent attributes explicitly — Python only sets these during a
        # fresh import, not when stubs are pre-placed in sys.modules.
        google_mod.api_core = google_api_core_mod
        google_mod.cloud = google_cloud_mod
        google_api_core_mod.exceptions = google_api_core_exc_mod
        google_cloud_mod.aiplatform = aiplatform_mod
        google_cloud_mod.aiplatform_v1 = aiplatform_v1_mod
        aiplatform_v1_mod.types = aiplatform_v1_types_mod
        aiplatform_v1_types_mod.index = aiplatform_v1_types_index_mod
        google_oauth2_mod.service_account = service_account_mod
        langchain_core_mod.documents = langchain_docs_mod

        for key, mod in [
            ("google", google_mod),
            ("google.cloud", google_cloud_mod),
            ("google.cloud.aiplatform", aiplatform_mod),
            ("google.cloud.aiplatform_v1", aiplatform_v1_mod),
            ("google.cloud.aiplatform_v1.types", aiplatform_v1_types_mod),
            ("google.cloud.aiplatform_v1.types.index", aiplatform_v1_types_index_mod),
            ("google.cloud.aiplatform.matching_engine", me_mod),
            (
                "google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint",
                me_ep_mod,
            ),
            ("google.api_core", google_api_core_mod),
            ("google.api_core.exceptions", google_api_core_exc_mod),
            ("google.oauth2", google_oauth2_mod),
            ("google.oauth2.service_account", service_account_mod),
            ("langchain_core", langchain_core_mod),
            ("langchain_core.documents", langchain_docs_mod),
        ]:
            monkeypatch.setitem(sys.modules, key, mod)

        monkeypatch.delitem(sys.modules, "mem0.vector_stores.vertex_ai_vector_search", raising=False)
        monkeypatch.delitem(
            sys.modules, "mem0.configs.vector_stores.vertex_ai_vector_search", raising=False
        )

        self.mock_index = mock_index
        self.mock_endpoint = mock_endpoint
        self.GoogleAPIError = GoogleAPIError
        self.NotFound = NotFound
        self.PermissionDenied = PermissionDenied
        self.InvalidArgument = InvalidArgument
        yield

    def _make_store(self):
        config_mod = ModuleType("mem0.configs.vector_stores.vertex_ai_vector_search")

        class GoogleMatchingEngineConfig:
            def __init__(self, **kwargs):
                self.project_id = kwargs.get("project_id", "proj")
                self.project_number = kwargs.get("project_number", "123")
                self.region = kwargs.get("region", "us-central1")
                self.endpoint_id = kwargs.get("endpoint_id", "ep-123")
                self.index_id = kwargs.get("index_id", "idx-123")
                self.deployment_index_id = kwargs.get(
                    "deployment_index_id", kwargs.get("collection_name", "dep-idx")
                )
                self.collection_name = kwargs.get("collection_name", "dep-idx")
                self.vector_search_api_endpoint = kwargs.get(
                    "vector_search_api_endpoint", "api.endpoint"
                )

            def model_dump(self):
                return {}

        config_mod.GoogleMatchingEngineConfig = GoogleMatchingEngineConfig
        sys.modules["mem0.configs.vector_stores.vertex_ai_vector_search"] = config_mod
        sys.modules.pop("mem0.vector_stores.vertex_ai_vector_search", None)

        from mem0.vector_stores.vertex_ai_vector_search import GoogleMatchingEngine

        return GoogleMatchingEngine(
            project_id="proj",
            project_number="123",
            region="us-central1",
            endpoint_id="ep-123",
            index_id="idx-123",
            collection_name="dep-idx",
            vector_search_api_endpoint="api.endpoint",
        )

    # --- init ---

    def test_init_sets_attributes(self):
        store = self._make_store()
        assert store.project_id == "proj"
        assert store.collection_name == "dep-idx"
        assert store.index_id == "idx-123"

    def test_init_calls_aiplatform_init(self):
        import google.cloud.aiplatform as aip

        self._make_store()
        aip.init.assert_called_once()

    # --- insert ---

    def test_insert_calls_upsert_datapoints(self):
        store = self._make_store()
        store.insert(
            vectors=[[0.1, 0.2, 0.3]],
            payloads=[{"data": "mem1", "user_id": "u1"}],
            ids=["id1"],
        )
        self.mock_index.upsert_datapoints.assert_called_once()

    def test_insert_empty_raises(self):
        store = self._make_store()
        with pytest.raises(ValueError, match="No vectors"):
            store.insert(vectors=[], payloads=[], ids=[])

    def test_insert_mismatched_payloads_raises(self):
        store = self._make_store()
        with pytest.raises(ValueError, match="payloads"):
            store.insert(
                vectors=[[0.1], [0.2]],
                payloads=[{"data": "m1"}],
                ids=["id1", "id2"],
            )

    def test_insert_mismatched_ids_raises(self):
        store = self._make_store()
        with pytest.raises(ValueError, match="ids"):
            store.insert(
                vectors=[[0.1], [0.2]],
                payloads=[{"data": "m1"}, {"data": "m2"}],
                ids=["id1"],
            )

    # --- delete ---

    def test_delete_single_id_returns_true(self):
        store = self._make_store()
        assert store.delete("id1") is True
        self.mock_index.remove_datapoints.assert_called_once_with(datapoint_ids=["id1"])

    def test_delete_list_of_ids(self):
        store = self._make_store()
        assert store.delete(ids=["id1", "id2"]) is True
        self.mock_index.remove_datapoints.assert_called_once_with(datapoint_ids=["id1", "id2"])

    def test_delete_no_id_provided_returns_false(self):
        store = self._make_store()
        assert store.delete() is False

    def test_delete_already_gone_returns_true(self):
        store = self._make_store()
        self.mock_index.remove_datapoints.side_effect = self.NotFound()
        assert store.delete("id1") is True

    def test_delete_permission_denied_returns_false(self):
        store = self._make_store()
        self.mock_index.remove_datapoints.side_effect = self.PermissionDenied()
        assert store.delete("id1") is False

    def test_delete_invalid_argument_returns_false(self):
        store = self._make_store()
        self.mock_index.remove_datapoints.side_effect = self.InvalidArgument()
        assert store.delete("id1") is False

    # --- update ---

    def test_update_calls_upsert_when_found(self):
        store = self._make_store()
        store.get = MagicMock(return_value=MagicMock(id="id1"))
        result = store.update("id1", vector=[0.1, 0.2, 0.3], payload={"data": "up"})
        assert result is True
        self.mock_index.upsert_datapoints.assert_called_once()

    def test_update_returns_false_when_not_found(self):
        store = self._make_store()
        store.get = MagicMock(return_value=None)
        assert store.update("missing", vector=[0.1], payload={"data": "x"}) is False

    def test_update_raises_without_vector_or_payload(self):
        store = self._make_store()
        with pytest.raises(ValueError, match="Either vector or payload"):
            store.update("id1", vector=None, payload=None)

    # --- keyword_search ---

    def test_keyword_search_returns_none(self):
        store = self._make_store()
        assert store.keyword_search("query") is None

    # --- col helpers ---

    def test_col_info_returns_config_fields(self):
        store = self._make_store()
        info = store.col_info()
        assert info["project_id"] == "proj"
        assert info["index_id"] == "idx-123"
        assert info["endpoint_id"] == "ep-123"

    def test_list_cols_returns_deployment_id(self):
        store = self._make_store()
        assert store.list_cols() == ["dep-idx"]

    def test_delete_col_is_noop(self):
        store = self._make_store()
        store.delete_col()
        self.mock_index.remove_datapoints.assert_not_called()

    def test_reset_is_noop(self):
        store = self._make_store()
        store.reset()
        self.mock_index.remove_datapoints.assert_not_called()

    def test_create_col_is_noop(self):
        store = self._make_store()
        store.create_col(name="x", vector_size=3, distance="cosine")
        self.mock_index.upsert_datapoints.assert_not_called()

    # --- search / _parse_output ---

    def test_search_returns_empty_when_no_neighbors(self):
        store = self._make_store()
        self.mock_endpoint.find_neighbors.return_value = []
        results = store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert results == []

    def test_search_parses_neighbors(self):
        store = self._make_store()
        neighbor = MagicMock()
        neighbor.id = "id1"
        neighbor.distance = 0.3
        restrict = MagicMock()
        restrict.name = "user_id"
        restrict.allow_tokens = ["u1"]
        neighbor.restricts = [restrict]
        self.mock_endpoint.find_neighbors.return_value = [[neighbor]]
        results = store.search(query="q", vectors=[0.1, 0.2, 0.3], top_k=5)
        assert len(results) == 1
        assert results[0].id == "id1"
        assert abs(results[0].score - 0.7) < 1e-6
        assert results[0].payload.get("user_id") == "u1"
