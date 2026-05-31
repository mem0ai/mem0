import json
import os
import pickle
import tempfile
from unittest.mock import Mock, patch

import faiss
import numpy as np
import pytest

from mem0.vector_stores.faiss import (
    FAISS,
    OutputData,
    SafeUnpickler,
    _safe_pickle_load,
    _validate_docstore_structure,
)


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
            results = faiss_instance.search(query="test query", vectors=query_vector, top_k=2)

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
                    query="test query", vectors=query_vector, top_k=2, filters={"category": "A"}
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


def test_delete(faiss_instance, mock_faiss_index):
    # Setup the docstore and index_to_id mapping
    faiss_instance.docstore = {"id1": {"name": "vector1"}, "id2": {"name": "vector2"}}
    faiss_instance.index_to_id = {0: "id1", 1: "id2"}

    # Mock reconstruct to return vectors for remaining entries
    mock_faiss_index.reconstruct.side_effect = lambda idx: np.array(
        [0.1, 0.2, 0.3] if idx == 0 else [0.4, 0.5, 0.6], dtype=np.float32
    )

    # Call delete
    faiss_instance.delete(vector_id="id1")

    # Verify the vector was removed from docstore
    assert "id1" not in faiss_instance.docstore
    assert "id2" in faiss_instance.docstore

    # Verify the FAISS index was rebuilt
    mock_faiss_index.reset.assert_called_once()
    mock_faiss_index.add.assert_called_once()

    # Verify index_to_id was remapped contiguously
    assert faiss_instance.index_to_id == {0: "id2"}


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
    results = faiss_instance.list(top_k=2)
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

            # Verify os.remove was called for index, json docstore, and legacy pkl files
            assert mock_remove.call_count == 3

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


# =============================================================================
# Security Tests for Pickle Deserialization Vulnerability Fix
# =============================================================================


class TestSafeUnpickler:
    """Tests for the SafeUnpickler class that prevents arbitrary code execution."""

    def test_safe_unpickler_allows_basic_types(self):
        """SafeUnpickler should allow basic Python types."""
        # Create a legitimate pickle with basic types
        data = (
            {"key1": "value1", "key2": {"nested": "dict"}},
            {0: "id1", 1: "id2"},
        )
        pickled = pickle.dumps(data)

        # Should load successfully
        import io

        result = SafeUnpickler(io.BytesIO(pickled)).load()
        assert result == data

    def test_safe_unpickler_blocks_os_system(self):
        """SafeUnpickler should block os.system execution attempts."""
        # Generate the malicious payload dynamically to ensure correct format
        import io

        class Evil:
            def __reduce__(self):
                return (os.system, ("echo pwned",))

        malicious_payload = pickle.dumps(Evil())

        with pytest.raises(pickle.UnpicklingError) as exc_info:
            SafeUnpickler(io.BytesIO(malicious_payload)).load()

        assert "Unsafe pickle" in str(exc_info.value)
        assert "posix.system" in str(exc_info.value)

    def test_safe_unpickler_blocks_subprocess(self):
        """SafeUnpickler should block subprocess execution attempts."""
        import subprocess

        # Create a malicious pickle that tries to use subprocess
        class MaliciousSubprocess:
            def __reduce__(self):
                return (subprocess.call, (["echo", "pwned"],))

        malicious_payload = pickle.dumps(MaliciousSubprocess())

        import io

        with pytest.raises(pickle.UnpicklingError) as exc_info:
            SafeUnpickler(io.BytesIO(malicious_payload)).load()

        assert "Unsafe pickle" in str(exc_info.value)

    def test_safe_unpickler_blocks_eval(self):
        """SafeUnpickler should block eval/exec attempts."""

        # Create a malicious pickle that tries to use eval
        class MaliciousEval:
            def __reduce__(self):
                return (eval, ("__import__('os').system('touch pwned')",))

        malicious_payload = pickle.dumps(MaliciousEval())

        import io

        with pytest.raises(pickle.UnpicklingError) as exc_info:
            SafeUnpickler(io.BytesIO(malicious_payload)).load()

        assert "Unsafe pickle" in str(exc_info.value)

    def test_safe_unpickler_blocks_arbitrary_modules(self):
        """SafeUnpickler should block imports from arbitrary modules."""

        # Create a pickle that tries to load a class from a non-builtins module
        class ArbitraryClass:
            def __reduce__(self):
                return (type, ("Evil", (), {}))

        malicious_payload = pickle.dumps(ArbitraryClass())

        import io

        # This should either work (type is a builtin) or fail safely
        # The key is it shouldn't execute arbitrary code
        try:
            result = SafeUnpickler(io.BytesIO(malicious_payload)).load()
            # If it loads, verify it's just a benign type object
            assert isinstance(result, type)
        except pickle.UnpicklingError:
            # This is also acceptable - blocking unknown patterns
            pass


class TestSafePickleLoad:
    """Tests for the _safe_pickle_load function."""

    def test_safe_pickle_load_with_valid_file(self):
        """_safe_pickle_load should load valid pickle files."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pkl", delete=False) as f:
            data = ({"id1": {"data": "test"}}, {0: "id1"})
            pickle.dump(data, f)
            temp_path = f.name

        try:
            result = _safe_pickle_load(temp_path)
            assert result == data
        finally:
            os.unlink(temp_path)

    def test_safe_pickle_load_blocks_malicious_file(self):
        """_safe_pickle_load should block malicious pickle files."""

        # Generate the malicious payload dynamically
        class Evil:
            def __reduce__(self):
                return (os.system, ("echo pwned",))

        malicious_payload = pickle.dumps(Evil())

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pkl", delete=False) as f:
            f.write(malicious_payload)
            temp_path = f.name

        try:
            with pytest.raises(pickle.UnpicklingError) as exc_info:
                _safe_pickle_load(temp_path)
            assert "Unsafe pickle" in str(exc_info.value)
        finally:
            os.unlink(temp_path)


class TestValidateDocstoreStructure:
    """Tests for the _validate_docstore_structure function."""

    def test_valid_structure(self):
        """Should accept valid docstore structure."""
        data = ({"id1": {"data": "test"}}, {0: "id1"})
        docstore, index_to_id = _validate_docstore_structure(data)
        assert docstore == {"id1": {"data": "test"}}
        assert index_to_id == {0: "id1"}

    def test_invalid_tuple_length(self):
        """Should reject tuples with wrong length."""
        with pytest.raises(ValueError, match="expected tuple"):
            _validate_docstore_structure(({}, {}, {}))

    def test_invalid_docstore_type(self):
        """Should reject non-dict docstore."""
        with pytest.raises(ValueError, match="docstore must be a dict"):
            _validate_docstore_structure(("not a dict", {}))

    def test_invalid_index_to_id_type(self):
        """Should reject non-dict index_to_id."""
        with pytest.raises(ValueError, match="index_to_id must be a dict"):
            _validate_docstore_structure(({}, "not a dict"))

    def test_invalid_docstore_key_type(self):
        """Should reject non-string docstore keys."""
        with pytest.raises(ValueError, match="Invalid docstore key type"):
            _validate_docstore_structure(({123: {"data": "test"}}, {0: "id1"}))

    def test_invalid_index_to_id_key_type(self):
        """Should reject non-int index_to_id keys."""
        with pytest.raises(ValueError, match="Invalid index_to_id key type"):
            _validate_docstore_structure(({"id1": {"data": "test"}}, {"0": "id1"}))


class TestFAISSSecurityIntegration:
    """Integration tests for FAISS security fixes."""

    def test_faiss_saves_as_json(self):
        """FAISS should save docstore as JSON, not pickle."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_index = Mock()
            mock_index.d = 128
            mock_index.ntotal = 0

            with patch("mem0.vector_stores.faiss.faiss.IndexFlatL2", return_value=mock_index):
                with patch("mem0.vector_stores.faiss.faiss.write_index"):
                    faiss_store = FAISS(
                        collection_name="test_security",
                        path=os.path.join(temp_dir, "test_faiss"),
                        distance_strategy="euclidean",
                    )
                    faiss_store.index = mock_index

                    # Insert some data
                    faiss_store.docstore = {"id1": {"data": "test"}}
                    faiss_store.index_to_id = {0: "id1"}
                    faiss_store._save()

                    # Verify JSON file was created
                    json_path = os.path.join(temp_dir, "test_faiss", "test_security.json")
                    pkl_path = os.path.join(temp_dir, "test_faiss", "test_security.pkl")

                    assert os.path.exists(json_path), "JSON docstore file should be created"
                    assert not os.path.exists(pkl_path), "Pickle file should NOT be created"

                    # Verify JSON content
                    with open(json_path, "r") as f:
                        data = json.load(f)
                    assert data["docstore"] == {"id1": {"data": "test"}}
                    assert data["index_to_id"] == {"0": "id1"}

    def test_faiss_loads_json_preferentially(self):
        """FAISS should prefer JSON over pickle when both exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            faiss_path = os.path.join(temp_dir, "test_faiss")
            os.makedirs(faiss_path)

            # Create both JSON and pickle files with different data
            json_data = {"docstore": {"id1": {"source": "json"}}, "index_to_id": {"0": "id1"}}
            pkl_data = ({"id1": {"source": "pickle"}}, {0: "id1"})

            with open(os.path.join(faiss_path, "test_pref.json"), "w") as f:
                json.dump(json_data, f)

            with open(os.path.join(faiss_path, "test_pref.pkl"), "wb") as f:
                pickle.dump(pkl_data, f)

            mock_index = Mock()
            mock_index.d = 128
            mock_index.ntotal = 1

            with patch("mem0.vector_stores.faiss.faiss.read_index", return_value=mock_index):
                with patch("mem0.vector_stores.faiss.faiss.write_index"):
                    faiss_store = FAISS.__new__(FAISS)
                    faiss_store.collection_name = "test_pref"
                    faiss_store.path = faiss_path
                    faiss_store.index = None
                    faiss_store.docstore = {}
                    faiss_store.index_to_id = {}

                    faiss_store._load(
                        os.path.join(faiss_path, "test_pref.faiss"),
                        os.path.join(faiss_path, "test_pref.pkl"),
                    )

                    # Should have loaded from JSON, not pickle
                    assert faiss_store.docstore == {"id1": {"source": "json"}}

    def test_faiss_blocks_malicious_pickle_on_load(self):
        """FAISS should block loading of malicious pickle files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            faiss_path = os.path.join(temp_dir, "test_faiss")
            os.makedirs(faiss_path)

            # Create a malicious pickle file (RCE payload)
            class Evil:
                def __reduce__(self):
                    return (os.system, (f"touch {temp_dir}/pwned",))

            malicious_payload = pickle.dumps(Evil())

            with open(os.path.join(faiss_path, "malicious.pkl"), "wb") as f:
                f.write(malicious_payload)

            mock_index = Mock()
            mock_index.ntotal = 1

            with patch("mem0.vector_stores.faiss.faiss.read_index", return_value=mock_index):
                faiss_store = FAISS.__new__(FAISS)
                faiss_store.collection_name = "malicious"
                faiss_store.path = faiss_path
                faiss_store.index = None
                faiss_store.docstore = {}
                faiss_store.index_to_id = {}

                # Should raise an error, not execute the malicious payload
                with pytest.raises(ValueError) as exc_info:
                    faiss_store._load(
                        os.path.join(faiss_path, "malicious.faiss"),
                        os.path.join(faiss_path, "malicious.pkl"),
                    )

                assert "malicious pickle" in str(exc_info.value).lower() or "unsafe" in str(exc_info.value).lower()

                # Verify the malicious command was NOT executed
                pwned_file = os.path.join(temp_dir, "pwned")
                assert not os.path.exists(pwned_file), "Malicious payload should NOT have been executed!"

    def test_faiss_migrates_legacy_pickle_to_json(self):
        """FAISS should auto-migrate valid pickle files to JSON format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            faiss_path = os.path.join(temp_dir, "test_faiss")
            os.makedirs(faiss_path)

            # Create a legitimate legacy pickle file
            pkl_data = ({"id1": {"data": "legacy"}}, {0: "id1"})
            with open(os.path.join(faiss_path, "legacy.pkl"), "wb") as f:
                pickle.dump(pkl_data, f)

            mock_index = Mock()
            mock_index.d = 128
            mock_index.ntotal = 1

            with patch("mem0.vector_stores.faiss.faiss.read_index", return_value=mock_index):
                with patch("mem0.vector_stores.faiss.faiss.write_index"):
                    faiss_store = FAISS.__new__(FAISS)
                    faiss_store.collection_name = "legacy"
                    faiss_store.path = faiss_path
                    faiss_store.index = None
                    faiss_store.docstore = {}
                    faiss_store.index_to_id = {}

                    faiss_store._load(
                        os.path.join(faiss_path, "legacy.faiss"),
                        os.path.join(faiss_path, "legacy.pkl"),
                    )

                    # Data should be loaded correctly
                    assert faiss_store.docstore == {"id1": {"data": "legacy"}}
                    assert faiss_store.index_to_id == {0: "id1"}

                    # JSON file should now exist (auto-migrated)
                    json_path = os.path.join(faiss_path, "legacy.json")
                    assert os.path.exists(json_path), "JSON file should be created during migration"

    def test_delete_col_removes_json_and_pkl(self):
        """delete_col should remove both JSON and legacy pickle files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            faiss_path = os.path.join(temp_dir, "test_faiss")
            os.makedirs(faiss_path)

            # Create both file types
            json_path = os.path.join(faiss_path, "test_del.json")
            pkl_path = os.path.join(faiss_path, "test_del.pkl")
            faiss_index_path = os.path.join(faiss_path, "test_del.faiss")

            with open(json_path, "w") as f:
                json.dump({"docstore": {}, "index_to_id": {}}, f)
            with open(pkl_path, "wb") as f:
                pickle.dump(({}, {}), f)
            with open(faiss_index_path, "w") as f:
                f.write("dummy")

            with patch("faiss.IndexFlatL2"):
                faiss_store = FAISS.__new__(FAISS)
                faiss_store.collection_name = "test_del"
                faiss_store.path = faiss_path
                faiss_store.index = Mock()
                faiss_store.docstore = {}
                faiss_store.index_to_id = {}

                faiss_store.delete_col()

                # Both files should be deleted
                assert not os.path.exists(json_path), "JSON file should be deleted"
                assert not os.path.exists(pkl_path), "PKL file should be deleted"
                assert not os.path.exists(faiss_index_path), "FAISS index should be deleted"
