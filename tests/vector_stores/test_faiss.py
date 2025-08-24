import os
import tempfile
from unittest.mock import Mock, patch

import faiss
import numpy as np
import pytest

from mem0.vector_stores.faiss import FAISS, OutputData


@pytest.fixture
def mock_faiss_index():
    index = Mock(spec=faiss.IndexFlatL2)
    index.d = 128  # Dimension of the vectors
    index.ntotal = 0  # Number of vectors in the index
    return index


@pytest.fixture
def faiss_instance(mock_faiss_index):
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock the faiss index creation
        with patch("faiss.IndexFlatL2", return_value=mock_faiss_index):
            # Mock the faiss.write_index function
            with patch("faiss.write_index"):
                # Create a FAISS instance with a temporary directory
                faiss_store = FAISS(
                    collection_name="test_collection",
                    path=os.path.join(temp_dir, "test_faiss"),
                    distance_strategy="euclidean",
                )
                # Set up the mock index
                faiss_store.index = mock_faiss_index
                yield faiss_store


def test_create_col(faiss_instance, mock_faiss_index):
    # Test creating a collection with euclidean distance
    with patch("faiss.IndexFlatL2", return_value=mock_faiss_index) as mock_index_flat_l2:
        with patch("faiss.write_index"):
            faiss_instance.create_col(name="new_collection")
            mock_index_flat_l2.assert_called_once_with(faiss_instance.embedding_model_dims)

    # Test creating a collection with inner product distance
    with patch("faiss.IndexFlatIP", return_value=mock_faiss_index) as mock_index_flat_ip:
        with patch("faiss.write_index"):
            faiss_instance.create_col(name="new_collection", distance="inner_product")
            mock_index_flat_ip.assert_called_once_with(faiss_instance.embedding_model_dims)


def test_insert(faiss_instance, mock_faiss_index):
    # Prepare test data
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]

    # Mock the numpy array conversion
    with patch("numpy.array", return_value=np.array(vectors, dtype=np.float32)) as mock_np_array:
        # Mock index.add
        mock_faiss_index.add.return_value = None

        # Call insert
        faiss_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

        # Verify numpy.array was called
        mock_np_array.assert_called_once_with(vectors, dtype=np.float32)

        # Verify index.add was called
        mock_faiss_index.add.assert_called_once()

        # Verify docstore and index_to_id were updated
        assert faiss_instance.docstore["id1"] == {"name": "vector1"}
        assert faiss_instance.docstore["id2"] == {"name": "vector2"}
        assert faiss_instance.index_to_id[0] == "id1"
        assert faiss_instance.index_to_id[1] == "id2"


def test_search(faiss_instance, mock_faiss_index):
    # Prepare test data
    query_vector = [0.1, 0.2, 0.3]

    # Setup the docstore and index_to_id mapping
    faiss_instance.docstore = {"id1": {"name": "vector1"}, "id2": {"name": "vector2"}}
    faiss_instance.index_to_id = {0: "id1", 1: "id2"}

    # First, create the mock for the search return values
    search_scores = np.array([[0.9, 0.8]])
    search_indices = np.array([[0, 1]])
    mock_faiss_index.search.return_value = (search_scores, search_indices)

    # Then patch numpy.array only for the query vector conversion
    with patch("numpy.array") as mock_np_array:
        mock_np_array.return_value = np.array(query_vector, dtype=np.float32)

        # Then patch _parse_output to return the expected results
        expected_results = [
            OutputData(id="id1", score=0.9, payload={"name": "vector1"}),
            OutputData(id="id2", score=0.8, payload={"name": "vector2"}),
        ]

        with patch.object(faiss_instance, "_parse_output", return_value=expected_results):
            # Call search
            results = faiss_instance.search(query="test query", vectors=query_vector, limit=2)

            # Verify numpy.array was called (but we don't check exact call arguments since it's complex)
            assert mock_np_array.called

            # Verify index.search was called
            mock_faiss_index.search.assert_called_once()

            # Verify results
            assert len(results) == 2
            assert results[0].id == "id1"
            assert results[0].score == 0.9
            assert results[0].payload == {"name": "vector1"}
            assert results[1].id == "id2"
            assert results[1].score == 0.8
            assert results[1].payload == {"name": "vector2"}


def test_search_with_filters(faiss_instance, mock_faiss_index):
    # Prepare test data
    query_vector = [0.1, 0.2, 0.3]

    # Setup the docstore and index_to_id mapping
    faiss_instance.docstore = {"id1": {"name": "vector1", "category": "A"}, "id2": {"name": "vector2", "category": "B"}}
    faiss_instance.index_to_id = {0: "id1", 1: "id2"}

    # First set up the search return values
    search_scores = np.array([[0.9, 0.8]])
    search_indices = np.array([[0, 1]])
    mock_faiss_index.search.return_value = (search_scores, search_indices)

    # Patch numpy.array for query vector conversion
    with patch("numpy.array") as mock_np_array:
        mock_np_array.return_value = np.array(query_vector, dtype=np.float32)

        # Directly mock the _parse_output method to return our expected values
        # We're simulating that _parse_output filters to just the first result
        all_results = [
            OutputData(id="id1", score=0.9, payload={"name": "vector1", "category": "A"}),
            OutputData(id="id2", score=0.8, payload={"name": "vector2", "category": "B"}),
        ]

        # Replace the _apply_filters method to handle our test case
        with patch.object(faiss_instance, "_parse_output", return_value=all_results):
            with patch.object(faiss_instance, "_apply_filters", side_effect=lambda p, f: p.get("category") == "A"):
                # Call search with filters
                results = faiss_instance.search(
                    query="test query", vectors=query_vector, limit=2, filters={"category": "A"}
                )

                # Verify numpy.array was called
                assert mock_np_array.called

                # Verify index.search was called
                mock_faiss_index.search.assert_called_once()

                # Verify filtered results - since we've mocked everything,
                # we should get just the result we want
                assert len(results) == 1
                assert results[0].id == "id1"
                assert results[0].score == 0.9
                assert results[0].payload == {"name": "vector1", "category": "A"}


def test_delete(faiss_instance):
    # Setup the docstore and index_to_id mapping
    faiss_instance.docstore = {"id1": {"name": "vector1"}, "id2": {"name": "vector2"}}
    faiss_instance.index_to_id = {0: "id1", 1: "id2"}

    # Call delete
    faiss_instance.delete(vector_id="id1")

    # Verify the vector was removed from docstore and index_to_id
    assert "id1" not in faiss_instance.docstore
    assert 0 not in faiss_instance.index_to_id
    assert "id2" in faiss_instance.docstore
    assert 1 in faiss_instance.index_to_id


def test_update(faiss_instance, mock_faiss_index):
    # Setup the docstore and index_to_id mapping
    faiss_instance.docstore = {"id1": {"name": "vector1"}, "id2": {"name": "vector2"}}
    faiss_instance.index_to_id = {0: "id1", 1: "id2"}

    # Test updating payload only
    faiss_instance.update(vector_id="id1", payload={"name": "updated_vector1"})
    assert faiss_instance.docstore["id1"] == {"name": "updated_vector1"}

    # Test updating vector
    # This requires mocking the delete and insert methods
    with patch.object(faiss_instance, "delete") as mock_delete:
        with patch.object(faiss_instance, "insert") as mock_insert:
            new_vector = [0.7, 0.8, 0.9]
            faiss_instance.update(vector_id="id2", vector=new_vector)

            # Verify delete and insert were called
            # Match the actual call signature (positional arg instead of keyword)
            mock_delete.assert_called_once_with("id2")
            mock_insert.assert_called_once()


def test_get(faiss_instance):
    # Setup the docstore
    faiss_instance.docstore = {"id1": {"name": "vector1"}, "id2": {"name": "vector2"}}

    # Test getting an existing vector
    result = faiss_instance.get(vector_id="id1")
    assert result.id == "id1"
    assert result.payload == {"name": "vector1"}
    assert result.score is None

    # Test getting a non-existent vector
    result = faiss_instance.get(vector_id="id3")
    assert result is None


def test_list(faiss_instance):
    # Setup the docstore
    faiss_instance.docstore = {
        "id1": {"name": "vector1", "category": "A"},
        "id2": {"name": "vector2", "category": "B"},
        "id3": {"name": "vector3", "category": "A"},
    }

    # Test listing all vectors
    results = faiss_instance.list()
    # Fix the expected result - the list method returns a list of lists
    assert len(results[0]) == 3

    # Test listing with a limit
    results = faiss_instance.list(limit=2)
    assert len(results[0]) == 2

    # Test listing with filters
    results = faiss_instance.list(filters={"category": "A"})
    assert len(results[0]) == 2
    for result in results[0]:
        assert result.payload["category"] == "A"


def test_col_info(faiss_instance, mock_faiss_index):
    # Mock index attributes
    mock_faiss_index.ntotal = 5
    mock_faiss_index.d = 128

    # Get collection info
    info = faiss_instance.col_info()

    # Verify the returned info
    assert info["name"] == "test_collection"
    assert info["count"] == 5
    assert info["dimension"] == 128
    assert info["distance"] == "euclidean"


def test_delete_col(faiss_instance):
    # Mock the os.remove function
    with patch("os.remove") as mock_remove:
        with patch("os.path.exists", return_value=True):
            # Call delete_col
            faiss_instance.delete_col()

            # Verify os.remove was called twice (for index and docstore files)
            assert mock_remove.call_count == 2

            # Verify the internal state was reset
            assert faiss_instance.index is None
            assert faiss_instance.docstore == {}
            assert faiss_instance.index_to_id == {}


def test_normalize_L2(faiss_instance, mock_faiss_index):
    # Setup a FAISS instance with normalize_L2=True
    faiss_instance.normalize_L2 = True

    # Prepare test data
    vectors = [[0.1, 0.2, 0.3]]

    # Mock numpy array conversion
    # Mock numpy array conversion
    with patch("numpy.array", return_value=np.array(vectors, dtype=np.float32)):
        # Mock faiss.normalize_L2
        with patch("faiss.normalize_L2") as mock_normalize:
            # Call insert
            faiss_instance.insert(vectors=vectors, ids=["id1"])

            # Verify faiss.normalize_L2 was called
            mock_normalize.assert_called_once()
