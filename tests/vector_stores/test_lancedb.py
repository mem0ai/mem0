import pytest
from unittest.mock import Mock, patch

from mem0.vector_stores.lancedb import LanceDB, OutputData


@pytest.fixture
def mock_table():
    """Create a mock LanceDB table."""
    table = Mock()
    table.add = Mock()
    table.search = Mock(return_value=Mock())
    table.delete = Mock()
    table.to_pandas = Mock(return_value=Mock())
    return table


@pytest.fixture
def mock_db(mock_table):
    """Create a mock LanceDB database."""
    db = Mock()
    db.table_names = Mock(return_value=["existing_table"])
    db.create_table = Mock(return_value=mock_table)
    db.open_table = Mock(return_value=mock_table)
    db.drop_table = Mock()
    return db


@pytest.fixture
def lancedb_instance(mock_db, mock_table):
    """Create a LanceDB instance with mocked database."""
    with patch('mem0.vector_stores.lancedb.lancedb') as mock_lancedb:
        mock_lancedb.connect.return_value = mock_db
        
        instance = LanceDB(
            uri="./test_lancedb",
            collection_name="test_collection",
            embedding_model_dims=128,
        )
        instance.db = mock_db
        instance.table = mock_table
        return instance


def test_lancedb_init(mock_db, mock_table):
    """Test LanceDB initialization."""
    with patch('mem0.vector_stores.lancedb.lancedb') as mock_lancedb:
        mock_lancedb.connect.return_value = mock_db

        instance = LanceDB(
            uri="./test_lancedb",
            collection_name="test_collection",
            embedding_model_dims=128,
        )

        assert instance.uri == "./test_lancedb"
        assert instance.collection_name == "test_collection"
        assert instance.embedding_model_dims == 128
        assert instance.table_name == "test_collection"


def test_create_col(lancedb_instance):
    """Test collection creation."""
    lancedb_instance.create_col(name="new_collection", vector_size=256)

    # Verify that create_table was called
    assert lancedb_instance.db.create_table.called


def test_insert(lancedb_instance):
    """Test vector insertion."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"text": "test1"}, {"text": "test2"}]
    ids = ["id1", "id2"]

    lancedb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    assert lancedb_instance.table.add.called


def test_search(lancedb_instance):
    """Test vector search."""
    # Mock the search results
    mock_results = Mock()
    mock_results.to_pandas.return_value = Mock()
    mock_results.to_pandas.return_value.iterrows.return_value = [
        (0, {"id": "id1", "vector": [0.1, 0.2, 0.3], "payload": '{"text": "test1"}', "_distance": 0.8}),
        (1, {"id": "id2", "vector": [0.4, 0.5, 0.6], "payload": '{"text": "test2"}', "_distance": 0.7})
    ]
    
    lancedb_instance.table.search.return_value.limit.return_value = mock_results

    query_vector = [0.2, 0.3, 0.4]
    results = lancedb_instance.search(query="test", vectors=query_vector, limit=5)

    assert isinstance(results, list)
    assert len(results) <= 5
    assert lancedb_instance.table.search.called


def test_delete(lancedb_instance):
    """Test vector deletion."""
    lancedb_instance.delete(vector_id="test_id")

    assert lancedb_instance.table.delete.called


def test_update(lancedb_instance):
    """Test vector update."""
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"text": "updated"}

    # Mock existing record
    mock_existing = Mock()
    mock_existing.empty = False
    lancedb_instance.table.search.return_value.where.return_value.to_pandas.return_value = mock_existing

    lancedb_instance.update(vector_id="test_id", vector=new_vector, payload=new_payload)

    assert lancedb_instance.table.delete.called
    assert lancedb_instance.table.add.called


def test_get(lancedb_instance):
    """Test retrieving a vector by ID."""
    # Mock the search results
    mock_results = Mock()
    mock_results.empty = False
    mock_results.iloc = [{"id": "test_id", "vector": [0.1, 0.2, 0.3], "payload": '{"text": "test"}'}]
    lancedb_instance.table.search.return_value.where.return_value.to_pandas.return_value = mock_results

    result = lancedb_instance.get(vector_id="test_id")

    assert result is not None
    assert isinstance(result, OutputData)
    assert result.id == "test_id"


def test_list_cols(lancedb_instance):
    """Test listing collections."""
    lancedb_instance.db.table_names.return_value = ["collection1", "collection2"]

    collections = lancedb_instance.list_cols()

    assert isinstance(collections, list)
    assert len(collections) == 2
    assert "collection1" in collections


def test_delete_col(lancedb_instance):
    """Test collection deletion."""
    lancedb_instance.delete_col()

    assert lancedb_instance.db.drop_table.called


def test_col_info(lancedb_instance):
    """Test getting collection information."""
    # Mock table length
    lancedb_instance.table.to_pandas.return_value.__len__ = Mock(return_value=100)

    info = lancedb_instance.col_info()

    assert isinstance(info, dict)
    assert 'name' in info
    assert 'count' in info


def test_list(lancedb_instance):
    """Test listing vectors."""
    # Mock the search results
    mock_results = Mock()
    mock_results.iterrows.return_value = [
        (0, {"id": "id1", "vector": [0.1, 0.2, 0.3], "payload": '{"text": "test1"}'})
    ]
    lancedb_instance.table.search.return_value.limit.return_value.to_pandas.return_value = mock_results

    results = lancedb_instance.list(limit=10)

    assert isinstance(results, list)
    assert len(results) > 0


def test_reset(lancedb_instance):
    """Test resetting the collection."""
    lancedb_instance.reset()

    assert lancedb_instance.db.drop_table.called


def test_search_with_filters(lancedb_instance):
    """Test vector search with filters."""
    # Mock the search results
    mock_results = Mock()
    mock_results.to_pandas.return_value.iterrows.return_value = [
        (0, {"id": "id1", "vector": [0.1, 0.2, 0.3], "payload": '{"text": "test1", "category": "A"}', "_distance": 0.8})
    ]
    
    lancedb_instance.table.search.return_value.where.return_value.limit.return_value = mock_results

    query_vector = [0.2, 0.3, 0.4]
    results = lancedb_instance.search(
        query="test",
        vectors=query_vector,
        limit=5,
        filters={"category": "A"}
    )

    assert isinstance(results, list)
    # Should only return filtered results
    for result in results:
        assert result.payload.get("category") == "A"


def test_output_data_model():
    """Test OutputData model."""
    data = OutputData(
        id="test_id",
        score=0.95,
        payload={"text": "test"}
    )

    assert data.id == "test_id"
    assert data.score == 0.95
    assert data.payload == {"text": "test"}


def test_insert_without_ids(lancedb_instance):
    """Test vector insertion without providing IDs."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"text": "test1"}, {"text": "test2"}]

    lancedb_instance.insert(vectors=vectors, payloads=payloads)

    assert lancedb_instance.table.add.called


def test_insert_without_payloads(lancedb_instance):
    """Test vector insertion without providing payloads."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    ids = ["id1", "id2"]

    lancedb_instance.insert(vectors=vectors, ids=ids)

    assert lancedb_instance.table.add.called


def test_build_filter_expression(lancedb_instance):
    """Test filter expression building."""
    filters = {"category": "A", "type": "test"}
    expr = lancedb_instance._build_filter_expression(filters)
    
    assert "category" in expr
    assert "type" in expr
    assert "AND" in expr


def test_get_nonexistent_vector(lancedb_instance):
    """Test getting a non-existent vector."""
    # Mock empty results
    mock_results = Mock()
    mock_results.empty = True
    lancedb_instance.table.search.return_value.where.return_value.to_pandas.return_value = mock_results

    result = lancedb_instance.get(vector_id="nonexistent")

    assert result is None


def test_update_nonexistent_vector(lancedb_instance):
    """Test updating a non-existent vector."""
    # Mock empty results
    mock_results = Mock()
    mock_results.empty = True
    lancedb_instance.table.search.return_value.where.return_value.to_pandas.return_value = mock_results

    lancedb_instance.update(vector_id="nonexistent", vector=[0.1, 0.2, 0.3])

    # Should not call add or delete for non-existent vector
    assert not lancedb_instance.table.add.called
    assert not lancedb_instance.table.delete.called
