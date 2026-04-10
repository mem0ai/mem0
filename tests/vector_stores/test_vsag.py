import os
import tempfile
from unittest.mock import Mock, patch

import numpy as np
import pytest

from mem0.vector_stores.vsag import VSAG


@pytest.fixture
def mock_vsag_index():
    """Create a mock VSAG index."""
    index = Mock()
    index.get_num_elements = Mock(return_value=0)
    return index


@pytest.fixture
def vsag_instance(mock_vsag_index):
    """Create a VSAG instance with mocked index."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("mem0.vector_stores.vsag.pyvsag.Index", return_value=mock_vsag_index):
            vsag_store = VSAG(
                collection_name="test_collection",
                path=os.path.join(temp_dir, "test_vsag"),
                dim=128,
                index_type="hnsw",
                metric_type="l2",
            )
            vsag_store.index = mock_vsag_index
            yield vsag_store


def test_create_col(vsag_instance, mock_vsag_index):
    """Test creating a collection."""
    with patch("mem0.vector_stores.vsag.pyvsag.Index", return_value=mock_vsag_index):
        vsag_instance.create_col(name="new_collection", vector_size=256, distance="ip")

        assert vsag_instance.dim == 256
        assert vsag_instance.metric_type == "ip"


def test_insert(vsag_instance, mock_vsag_index):
    """Test inserting vectors."""
    # Prepare test data
    vectors = [[0.1] * 128, [0.2] * 128]  # 128-dim vectors
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]

    # Mock the add method
    mock_vsag_index.add = Mock(return_value=None)

    # Call insert
    vsag_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    # Verify docstore was updated
    assert vsag_instance.docstore["id1"] == {"name": "vector1"}
    assert vsag_instance.docstore["id2"] == {"name": "vector2"}

    # Verify id mappings
    assert vsag_instance.id_to_internal["id1"] == 0
    assert vsag_instance.id_to_internal["id2"] == 1

    # Verify index.add was called
    mock_vsag_index.add.assert_called_once()


def test_search(vsag_instance, mock_vsag_index):
    """Test searching for vectors."""
    # Setup the docstore and id mappings
    vsag_instance.docstore = {"id1": {"name": "vector1"}, "id2": {"name": "vector2"}}
    vsag_instance.id_to_internal = {"id1": 0, "id2": 1}
    vsag_instance.internal_to_id = {0: "id1", 1: "id2"}

    # Mock knn_search return values
    mock_result_ids = np.array([0, 1], dtype=np.int64)
    mock_result_dists = np.array([0.1, 0.2], dtype=np.float32)
    mock_vsag_index.knn_search = Mock(return_value=(mock_result_ids, mock_result_dists))

    # Call search
    query_vector = [0.1] * 128
    results = vsag_instance.search(query="test query", vectors=[query_vector], limit=2)

    # Verify results
    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == pytest.approx(0.1)
    assert results[0].payload == {"name": "vector1"}


def test_search_with_filters(vsag_instance, mock_vsag_index):
    """Test searching with filters."""
    # Setup the docstore and id mappings
    vsag_instance.docstore = {
        "id1": {"name": "vector1", "category": "A"},
        "id2": {"name": "vector2", "category": "B"},
    }
    vsag_instance.id_to_internal = {"id1": 0, "id2": 1}
    vsag_instance.internal_to_id = {0: "id1", 1: "id2"}

    # Mock knn_search return values
    mock_result_ids = np.array([0, 1], dtype=np.int64)
    mock_result_dists = np.array([0.1, 0.2], dtype=np.float32)
    mock_vsag_index.knn_search = Mock(return_value=(mock_result_ids, mock_result_dists))

    # Call search with filters
    query_vector = [0.1] * 128
    results = vsag_instance.search(
        query="test query",
        vectors=[query_vector],
        limit=2,
        filters={"category": "A"}
    )

    # Verify filtered results
    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].payload["category"] == "A"


def test_delete(vsag_instance, mock_vsag_index):
    """Test deleting a vector."""
    # Setup the docstore and id mappings
    vsag_instance.docstore = {"id1": {"name": "vector1"}, "id2": {"name": "vector2"}}
    vsag_instance.id_to_internal = {"id1": 0, "id2": 1}
    vsag_instance.internal_to_id = {0: "id1", 1: "id2"}

    # Mock remove method
    mock_vsag_index.remove = Mock(return_value=1)

    # Call delete
    vsag_instance.delete(vector_id="id1")

    # Verify the vector was removed from docstore
    assert "id1" not in vsag_instance.docstore
    assert "id2" in vsag_instance.docstore

    # Verify remove was called
    mock_vsag_index.remove.assert_called_once()


def test_update(vsag_instance, mock_vsag_index):
    """Test updating a vector."""
    # Setup the docstore and id mappings
    vsag_instance.docstore = {"id1": {"name": "vector1"}}
    vsag_instance.id_to_internal = {"id1": 0}
    vsag_instance.internal_to_id = {0: "id1"}

    # Test updating payload only
    vsag_instance.update(vector_id="id1", payload={"name": "updated_vector1"})
    assert vsag_instance.docstore["id1"] == {"name": "updated_vector1"}

    # Test updating vector (requires delete + insert)
    mock_vsag_index.remove = Mock(return_value=1)
    mock_vsag_index.add = Mock(return_value=None)

    new_vector = [0.5] * 128
    vsag_instance.update(vector_id="id1", vector=new_vector)


def test_get(vsag_instance):
    """Test getting a vector by ID."""
    # Setup the docstore
    vsag_instance.docstore = {"id1": {"name": "vector1"}, "id2": {"name": "vector2"}}

    # Test getting an existing vector
    result = vsag_instance.get(vector_id="id1")
    assert result.id == "id1"
    assert result.payload == {"name": "vector1"}
    assert result.score is None

    # Test getting a non-existent vector
    result = vsag_instance.get(vector_id="id3")
    assert result is None


def test_list(vsag_instance):
    """Test listing vectors."""
    # Setup the docstore
    vsag_instance.docstore = {
        "id1": {"name": "vector1", "category": "A"},
        "id2": {"name": "vector2", "category": "B"},
        "id3": {"name": "vector3", "category": "A"},
    }

    # Test listing all vectors
    results = vsag_instance.list()
    assert len(results[0]) == 3

    # Test listing with a limit
    results = vsag_instance.list(limit=2)
    assert len(results[0]) == 2

    # Test listing with filters
    results = vsag_instance.list(filters={"category": "A"})
    assert len(results[0]) == 2
    for result in results[0]:
        assert result.payload["category"] == "A"


def test_col_info(vsag_instance, mock_vsag_index):
    """Test getting collection info."""
    # Mock index attributes
    mock_vsag_index.get_num_elements = Mock(return_value=5)

    # Get collection info
    info = vsag_instance.col_info()

    # Verify the returned info
    assert info["name"] == "test_collection"
    assert info["count"] == 5
    assert info["dimension"] == 128
    assert info["metric"] == "l2"
    assert info["index_type"] == "hnsw"


def test_delete_col(vsag_instance):
    """Test deleting a collection."""
    # Mock os.path.exists and os.remove
    with patch("os.path.exists", return_value=True):
        with patch("os.remove") as mock_remove:
            vsag_instance.delete_col()

            # Verify os.remove was called twice (for index and meta files)
            assert mock_remove.call_count == 2

            # Verify the internal state was reset
            assert vsag_instance.index is None
            assert vsag_instance.docstore == {}
            assert vsag_instance.id_to_internal == {}
            assert vsag_instance.internal_to_id == {}


def test_reset(vsag_instance, mock_vsag_index):
    """Test resetting a collection."""
    # Setup some data
    vsag_instance.docstore = {"id1": {"name": "vector1"}}

    with patch.object(vsag_instance, "delete_col"):
        with patch.object(vsag_instance, "create_col"):
            vsag_instance.reset()

            # Verify delete_col and create_col were called
            vsag_instance.delete_col.assert_called_once()
            vsag_instance.create_col.assert_called_once()


def test_check_id_exist(vsag_instance, mock_vsag_index):
    """Test checking if an ID exists."""
    # Setup the docstore
    vsag_instance.docstore = {"id1": {"name": "vector1"}}

    # The get method returns OutputData or None
    result = vsag_instance.get("id1")
    assert result is not None
    assert result.id == "id1"

    result = vsag_instance.get("nonexistent")
    assert result is None


def test_get_default_index_params(vsag_instance):
    """Test default index parameters for different index types."""
    # Test HNSW defaults
    params = vsag_instance._get_default_index_params()
    assert "max_degree" in params
    assert "ef_construction" in params

    # Test HGRAPH defaults
    vsag_instance.index_type = "hgraph"
    params = vsag_instance._get_default_index_params()
    assert "base_quantization_type" in params
    assert "max_degree" in params


def test_build_index_params_json(vsag_instance):
    """Test building index parameters JSON."""
    json_params = vsag_instance._build_index_params_json()

    # Verify it's valid JSON
    import json
    params = json.loads(json_params)

    assert params["dtype"] == "float32"
    assert params["metric_type"] == "l2"
    assert params["dim"] == 128
    assert "hnsw" in params


def test_get_search_params_json(vsag_instance):
    """Test building search parameters JSON."""
    # Test with default params
    json_params = vsag_instance._get_search_params_json()

    import json
    params = json.loads(json_params)
    assert "hnsw" in params

    # Test with custom params
    json_params = vsag_instance._get_search_params_json({"ef_search": 200})
    params = json.loads(json_params)
    assert params["hnsw"]["ef_search"] == 200