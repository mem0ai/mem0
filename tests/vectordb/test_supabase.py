import pytest
from unittest.mock import patch

try:
    import vecs
    from vecs.collections import Collection, CollectionNotFound

except ImportError:
    raise ImportError(
        "Supabase requires extra dependencies. Install with `pip install --upgrade embedchain[vecs]`"
    ) from None


from embedchain.config.vectordb.supabase import SupabaseDBConfig
from embedchain.vectordb.supabase import SupabaseVectorDB


class MockVecsClient:
    def __init__(self):
        self.collections = {}

    def create_client(self, *args, **kwargs):
        return self

    def get_collection(self, name):
        if name in self.collections:
            return self.collections[name]
        else:
            raise CollectionNotFound(f"Collection {name} not found")

    def create_collection(self, name, dimension):
        collection = Collection(name=name, dimension=dimension)
        self.collections[name] = collection
        return collection


@pytest.fixture
def mock_vecs_client():
    return MockVecsClient()


@pytest.fixture
def supabase_config():
    return SupabaseDBConfig(
        postgres_connection_string="mock_connection_string",
        collection_name="test_collection",
        dimension=128,
        index_measure="cosine_distance",
        index_method="hnsw",
    )


def test_init_without_config():
    with patch.object(vecs, "create_client") as mock_create_client:
        db = SupabaseVectorDB("mock_connection_string", "test_collection", 128)
        assert db._client is mock_create_client.return_value
        assert db.config.postgres_connection_string == "mock_connection_string"
        assert db.config.collection_name == "test_collection"
        assert db._index_measure == "cosine_distance"
        assert db._index_method == "hnsw"


def test_init_with_config(supabase_config, mock_vecs_client):
    with patch.object(vecs, "create_client") as mock_create_client:
        mock_create_client.return_value = mock_vecs_client
        db = SupabaseVectorDB(config=supabase_config)
        assert db._client is mock_vecs_client
        assert db.config == supabase_config


def test_init_collection_exists(mock_vecs_client):
    mock_collection = Collection(name="test_collection", dimension=128)
    mock_vecs_client.collections["test_collection"] = mock_collection
    with patch.object(vecs, "create_client") as mock_create_client:
        mock_create_client.return_value = mock_vecs_client
        db = SupabaseVectorDB("mock_connection_string", "test_collection", 128, config=None)
        assert db._collection == mock_collection


def test_init_collection_not_found(mock_vecs_client):
    with patch.object(vecs, "create_client") as mock_create_client:
        mock_create_client.return_value = mock_vecs_client
        with pytest.raises(CollectionNotFound):
            SupabaseVectorDB("mock_connection_string", "non-existent_collection", 128, config=None)


def test_get(mock_vecs_client):
    mock_collection = Collection(name="test_collection", dimension=128)
    mock_collection.data = [{"id": 1, "vector": [1, 2, 3], "metadata": {"key": "value"}}]
    mock_vecs_client.collections["test_collection"] = mock_collection
    with patch.object(vecs, "create_client") as mock_create_client:
        mock_create_client.return_value = mock_vecs_client
        db = SupabaseVectorDB("mock_connection_string", "test_collection", 128, config=None)
        embeddings = db.get([1])
        assert embeddings == [{"id": 1, "vector": [1, 2, 3], "metadata": {"key": "value"}}]


def test_query(mock_vecs_client):
    mock_collection = Collection(name="test_collection", dimension=128)
    mock_collection.data = [
        {"id": 1, "vector": [1, 2, 3], "metadata": {"category": "A"}},
        {"id": 2, "vector": [4, 5, 6], "metadata": {"category": "B"}},
        {"id": 3, "vector": [7, 8, 9], "metadata": {"category": "A"}},
    ]
    mock_vecs_client.collections["test_collection"] = mock_collection
    with patch.object(vecs, "create_client") as mock_create_client:
        mock_create_client.return_value = mock_vecs_client
        db = SupabaseVectorDB("mock_connection_string", "test_collection", 128, config=None)

        # Example query with filter on metadata
        query = {"metadata": {"category": "A"}}
        results = db.query(query)

        # Assert that results contain items with matching metadata
        assert all(result["metadata"]["category"] == "A" for result in results)
        assert len(results) == 2  # Two items match the filter


def test_add(mock_vecs_client):
    mock_collection = Collection(name="test_collection", dimension=128)
    mock_vecs_client.collections["test_collection"] = mock_collection
    data = [{"id": 2, "vector": [4, 5, 6], "metadata": {"key2": "value2"}}]
    with patch.object(vecs, "create_client") as mock_create_client:
        mock_create_client.return_value = mock_vecs_client
        db = SupabaseVectorDB("mock_connection_string", "test_collection", 128, config=None)
        db.add(data)
        assert mock_vecs_client.collections["test_collection"].data == [
            {"id": 1, "vector": [1, 2, 3], "metadata": {"key": "value"}},
            {"id": 2, "vector": [4, 5, 6], "metadata": {"key2": "value2"}},
        ]


def test_delete(mock_vecs_client):
    mock_collection = Collection(name="test_collection", dimension=128)
    mock_collection.data = [
        {"id": 1, "vector": [1, 2, 3]},
        {"id": 2, "vector": [4, 5, 6]},
        {"id": 3, "vector": [7, 8, 9]},
    ]
    mock_vecs_client.collections["test_collection"] = mock_collection
    with patch.object(vecs, "create_client") as mock_create_client:
        mock_create_client.return_value = mock_vecs_client
        db = SupabaseVectorDB("mock_connection_string", "test_collection", 128, config=None)
        db.delete([1, 2])
        assert mock_vecs_client.collections["test_collection"].data == [
            {"id": 3, "vector": [7, 8, 9]},
        ]
        db.delete([3])
        assert mock_vecs_client.collections["test_collection"].data == []
