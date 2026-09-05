from unittest.mock import Mock, patch

import pytest
from google.api_core import exceptions
from google.cloud.aiplatform.matching_engine.matching_engine_index_endpoint import (
    Namespace,
)

from mem0.configs.vector_stores.vertex_ai_vector_search import (
    GoogleMatchingEngineConfig,
)
from mem0.vector_stores.vertex_ai_vector_search import GoogleMatchingEngine


@pytest.fixture
def mock_vertex_ai():
    with (
        patch("google.cloud.aiplatform.MatchingEngineIndex") as mock_index,
        patch("google.cloud.aiplatform.MatchingEngineIndexEndpoint") as mock_endpoint,
        patch("google.cloud.aiplatform.init") as mock_init,
    ):
        mock_index_instance = Mock()
        mock_endpoint_instance = Mock()
        yield {
            "index": mock_index_instance,
            "endpoint": mock_endpoint_instance,
            "init": mock_init,
            "index_class": mock_index,
            "endpoint_class": mock_endpoint,
        }


@pytest.fixture
def config():
    return GoogleMatchingEngineConfig(
        project_id="test-project",
        project_number="123456789",
        region="us-central1",
        endpoint_id="test-endpoint",
        index_id="test-index",
        deployment_index_id="test-deployment",
        collection_name="test-collection",
        vector_search_api_endpoint="test.vertexai.goog",
    )


@pytest.fixture
def vector_store(config, mock_vertex_ai):
    mock_vertex_ai["index_class"].return_value = mock_vertex_ai["index"]
    mock_vertex_ai["endpoint_class"].return_value = mock_vertex_ai["endpoint"]
    return GoogleMatchingEngine(**config.model_dump())


def test_initialization(vector_store, mock_vertex_ai, config):
    """Test proper initialization of GoogleMatchingEngine"""
    mock_vertex_ai["init"].assert_called_once_with(project=config.project_id, location=config.region)

    expected_index_path = f"projects/{config.project_number}/locations/{config.region}/indexes/{config.index_id}"
    mock_vertex_ai["index_class"].assert_called_once_with(index_name=expected_index_path)


def test_insert_vectors(vector_store, mock_vertex_ai):
    """Test inserting vectors with payloads"""
    vectors = [[0.1, 0.2, 0.3]]
    payloads = [{"name": "test", "user_id": "user1"}]
    ids = ["test-id"]

    vector_store.insert(vectors=vectors, payloads=payloads, ids=ids)

    mock_vertex_ai["index"].upsert_datapoints.assert_called_once()
    call_args = mock_vertex_ai["index"].upsert_datapoints.call_args[1]
    assert len(call_args["datapoints"]) == 1
    datapoint_str = str(call_args["datapoints"][0])
    assert "test-id" in datapoint_str
    assert "0.1" in datapoint_str and "0.2" in datapoint_str and "0.3" in datapoint_str


def test_search_vectors(vector_store, mock_vertex_ai):
    """Test searching vectors with filters"""
    vectors = [[0.1, 0.2, 0.3]]
    filters = {"user_id": "test_user"}

    mock_datapoint = Mock()
    mock_datapoint.datapoint_id = "test-id"
    mock_datapoint.feature_vector = vectors

    mock_restrict = Mock()
    mock_restrict.namespace = "user_id"
    mock_restrict.allow_list = ["test_user"]
    mock_restrict.name = "user_id"
    mock_restrict.allow_tokens = ["test_user"]

    mock_datapoint.restricts = [mock_restrict]

    mock_neighbor = Mock()
    mock_neighbor.id = "test-id"
    mock_neighbor.distance = 0.1
    mock_neighbor.datapoint = mock_datapoint
    mock_neighbor.restricts = [mock_restrict]

    mock_vertex_ai["endpoint"].find_neighbors.return_value = [[mock_neighbor]]

    results = vector_store.search(query="", vectors=vectors, filters=filters, top_k=1)

    mock_vertex_ai["endpoint"].find_neighbors.assert_called_once_with(
        deployed_index_id=vector_store.deployment_index_id,
        queries=[vectors],
        num_neighbors=1,
        filter=[Namespace("user_id", ["test_user"], [])],
        return_full_datapoint=True,
    )

    assert len(results) == 1
    assert results[0].id == "test-id"
    assert results[0].score == 0.9
    assert results[0].payload == {"user_id": "test_user"}


def test_list_does_not_raise_type_error(vector_store, mock_vertex_ai):
    """list() must call search() with the required positional `vectors` arg."""
    mock_vertex_ai["endpoint"].find_neighbors.return_value = [[]]

    results = vector_store.list(filters={"user_id": "test_user"}, top_k=5)

    mock_vertex_ai["endpoint"].find_neighbors.assert_called_once()
    queries = mock_vertex_ai["endpoint"].find_neighbors.call_args[1]["queries"]
    assert queries == [[0.0] * 768]
    assert results == [[]]


def test_similarity_search_with_score_passes_embedding(vector_store, mock_vertex_ai):
    """similarity_search_with_score() must pass the embedding as `vectors`."""
    embedding = [0.1, 0.2, 0.3]
    vector_store.embedder = Mock()
    vector_store.embedder.embed_query.return_value = embedding
    mock_vertex_ai["endpoint"].find_neighbors.return_value = [[]]

    vector_store.similarity_search_with_score(query="hello", k=3)

    mock_vertex_ai["endpoint"].find_neighbors.assert_called_once()
    queries = mock_vertex_ai["endpoint"].find_neighbors.call_args[1]["queries"]
    assert queries == [embedding]


def test_delete(vector_store, mock_vertex_ai):
    """Test deleting vectors"""
    vector_id = "test-id"

    remove_mock = Mock()

    with patch.object(GoogleMatchingEngine, "delete", wraps=vector_store.delete) as delete_spy:
        with patch.object(vector_store.index, "remove_datapoints", remove_mock):
            vector_store.delete(ids=[vector_id])

            delete_spy.assert_called_once_with(ids=[vector_id])
            remove_mock.assert_called_once_with(datapoint_ids=[vector_id])


def test_error_handling(vector_store, mock_vertex_ai):
    """Test error handling during operations"""
    mock_vertex_ai["index"].upsert_datapoints.side_effect = exceptions.InvalidArgument("Invalid request")

    with pytest.raises(Exception) as exc_info:
        vector_store.insert(vectors=[[0.1, 0.2, 0.3]], payloads=[{"name": "test"}], ids=["test-id"])

    assert isinstance(exc_info.value, exceptions.InvalidArgument)
    assert "Invalid request" in str(exc_info.value)


class TestDistanceMetric:
    """Metric-aware distance-to-similarity conversion (issue #7232)."""

    def _config(self, **overrides):
        base = dict(
            project_id="test-project",
            project_number="123456789",
            region="us-central1",
            endpoint_id="test-endpoint",
            index_id="test-index",
            deployment_index_id="test-deployment",
            collection_name="test-collection",
            vector_search_api_endpoint="test.vertexai.goog",
        )
        base.update(overrides)
        return GoogleMatchingEngineConfig(**base)

    def _store(self, config, mock_vertex_ai):
        mock_vertex_ai["index_class"].return_value = mock_vertex_ai["index"]
        mock_vertex_ai["endpoint_class"].return_value = mock_vertex_ai["endpoint"]
        return GoogleMatchingEngine(**config.model_dump())

    def test_default_metric_is_cosine(self):
        assert self._config().distance_metric == "cosine"

    def test_metric_aliases_are_canonicalized(self):
        assert self._config(distance_metric="SQUARED_L2_DISTANCE").distance_metric == "squared_l2"
        assert self._config(distance_metric="dot_product_point").distance_metric == "dot_product"
        assert self._config(distance_metric="euclidean").distance_metric == "squared_l2"

    def test_invalid_metric_is_rejected(self):
        with pytest.raises(Exception):
            self._config(distance_metric="manhattan")

    def test_metric_reaches_the_store(self, mock_vertex_ai):
        store = self._store(self._config(distance_metric="squared_l2"), mock_vertex_ai)
        assert store.distance_metric == "squared_l2"

    def test_cosine_conversion_unchanged(self, mock_vertex_ai):
        store = self._store(self._config(), mock_vertex_ai)
        assert store._distance_to_similarity(0.2) == pytest.approx(0.8)
        assert store._distance_to_similarity(2.0) == 0.0
        assert store._distance_to_similarity(None) is None

    def test_squared_l2_conversion_is_bounded(self, mock_vertex_ai):
        store = self._store(self._config(distance_metric="squared_l2"), mock_vertex_ai)
        assert store._distance_to_similarity(2.0) == pytest.approx(1.0 / 3.0)
        assert 0.0 < store._distance_to_similarity(2.0) < 1.0

    def test_dot_product_passes_through(self, mock_vertex_ai):
        store = self._store(self._config(distance_metric="dot_product"), mock_vertex_ai)
        assert store._distance_to_similarity(2.0) == pytest.approx(2.0)

    def test_parse_output_respects_metric(self, mock_vertex_ai):
        """Regression: _parse_output must not hardcode the cosine conversion."""
        data = {"nearestNeighbors": {"neighbors": [{"datapoint": {"datapointId": "d1", "metadata": {}}, "distance": 2.0}]}}

        cosine_store = self._store(self._config(), mock_vertex_ai)
        assert cosine_store._parse_output(data)[0].score == 0.0

        l2_store = self._store(self._config(distance_metric="squared_l2"), mock_vertex_ai)
        assert l2_store._parse_output(data)[0].score == pytest.approx(1.0 / 3.0)
