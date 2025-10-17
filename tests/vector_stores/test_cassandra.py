import json
import pytest
from unittest.mock import Mock, patch

from mem0.vector_stores.cassandra import CassandraDB, OutputData


@pytest.fixture
def mock_session():
    """Create a mock Cassandra session."""
    session = Mock()
    session.execute = Mock(return_value=Mock())
    session.prepare = Mock(return_value=Mock())
    session.set_keyspace = Mock()
    return session


@pytest.fixture
def mock_cluster(mock_session):
    """Create a mock Cassandra cluster."""
    cluster = Mock()
    cluster.connect = Mock(return_value=mock_session)
    cluster.shutdown = Mock()
    return cluster


@pytest.fixture
def cassandra_instance(mock_cluster, mock_session):
    """Create a CassandraDB instance with mocked cluster."""
    with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
        mock_cluster_class.return_value = mock_cluster
        
        instance = CassandraDB(
            contact_points=['127.0.0.1'],
            port=9042,
            username='testuser',
            password='testpass',
            keyspace='test_keyspace',
            collection_name='test_collection',
            embedding_model_dims=128,
        )
        instance.session = mock_session
        return instance


def test_cassandra_init(mock_cluster, mock_session):
    """Test CassandraDB initialization."""
    with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
        mock_cluster_class.return_value = mock_cluster

        instance = CassandraDB(
            contact_points=['127.0.0.1'],
            port=9042,
            username='testuser',
            password='testpass',
            keyspace='test_keyspace',
            collection_name='test_collection',
            embedding_model_dims=128,
        )

        assert instance.contact_points == ['127.0.0.1']
        assert instance.port == 9042
        assert instance.username == 'testuser'
        assert instance.keyspace == 'test_keyspace'
        assert instance.collection_name == 'test_collection'
        assert instance.embedding_model_dims == 128


def test_create_col(cassandra_instance):
    """Test collection creation."""
    cassandra_instance.create_col(name="new_collection", vector_size=256)

    # Verify that execute was called (table creation)
    assert cassandra_instance.session.execute.called


def test_insert(cassandra_instance):
    """Test vector insertion."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"text": "test1"}, {"text": "test2"}]
    ids = ["id1", "id2"]

    # Mock prepared statement
    mock_prepared = Mock()
    cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

    cassandra_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    assert cassandra_instance.session.prepare.called
    assert cassandra_instance.session.execute.called


def test_search(cassandra_instance):
    """Test vector search."""
    # Mock the database response
    mock_row1 = Mock()
    mock_row1.id = 'id1'
    mock_row1.vector = [0.1, 0.2, 0.3]
    mock_row1.payload = json.dumps({"text": "test1"})

    mock_row2 = Mock()
    mock_row2.id = 'id2'
    mock_row2.vector = [0.4, 0.5, 0.6]
    mock_row2.payload = json.dumps({"text": "test2"})

    cassandra_instance.session.execute = Mock(return_value=[mock_row1, mock_row2])

    query_vector = [0.2, 0.3, 0.4]
    results = cassandra_instance.search(query="test", vectors=query_vector, limit=5)

    assert isinstance(results, list)
    assert len(results) <= 5
    assert cassandra_instance.session.execute.called


def test_delete(cassandra_instance):
    """Test vector deletion."""
    mock_prepared = Mock()
    cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

    cassandra_instance.delete(vector_id="test_id")

    assert cassandra_instance.session.prepare.called
    assert cassandra_instance.session.execute.called


def test_update(cassandra_instance):
    """Test vector update."""
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"text": "updated"}

    mock_prepared = Mock()
    cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

    cassandra_instance.update(vector_id="test_id", vector=new_vector, payload=new_payload)

    assert cassandra_instance.session.prepare.called
    assert cassandra_instance.session.execute.called


def test_get(cassandra_instance):
    """Test retrieving a vector by ID."""
    # Mock the database response
    mock_row = Mock()
    mock_row.id = 'test_id'
    mock_row.vector = [0.1, 0.2, 0.3]
    mock_row.payload = json.dumps({"text": "test"})

    mock_result = Mock()
    mock_result.one = Mock(return_value=mock_row)

    mock_prepared = Mock()
    cassandra_instance.session.prepare = Mock(return_value=mock_prepared)
    cassandra_instance.session.execute = Mock(return_value=mock_result)

    result = cassandra_instance.get(vector_id="test_id")

    assert result is not None
    assert isinstance(result, OutputData)
    assert result.id == "test_id"


def test_list_cols(cassandra_instance):
    """Test listing collections."""
    # Mock the database response
    mock_row1 = Mock()
    mock_row1.table_name = "collection1"

    mock_row2 = Mock()
    mock_row2.table_name = "collection2"

    cassandra_instance.session.execute = Mock(return_value=[mock_row1, mock_row2])

    collections = cassandra_instance.list_cols()

    assert isinstance(collections, list)
    assert len(collections) == 2
    assert "collection1" in collections


def test_delete_col(cassandra_instance):
    """Test collection deletion."""
    cassandra_instance.delete_col()

    assert cassandra_instance.session.execute.called


def test_col_info(cassandra_instance):
    """Test getting collection information."""
    # Mock the database response
    mock_row = Mock()
    mock_row.count = 100

    mock_result = Mock()
    mock_result.one = Mock(return_value=mock_row)

    cassandra_instance.session.execute = Mock(return_value=mock_result)

    info = cassandra_instance.col_info()

    assert isinstance(info, dict)
    assert 'name' in info
    assert 'keyspace' in info


def test_list(cassandra_instance):
    """Test listing vectors."""
    # Mock the database response
    mock_row = Mock()
    mock_row.id = 'id1'
    mock_row.vector = [0.1, 0.2, 0.3]
    mock_row.payload = json.dumps({"text": "test1"})

    cassandra_instance.session.execute = Mock(return_value=[mock_row])

    results = cassandra_instance.list(limit=10)

    assert isinstance(results, list)
    assert len(results) > 0


def test_reset(cassandra_instance):
    """Test resetting the collection."""
    cassandra_instance.reset()

    assert cassandra_instance.session.execute.called


def test_astra_db_connection(mock_cluster, mock_session):
    """Test connection with DataStax Astra DB secure connect bundle."""
    with patch('mem0.vector_stores.cassandra.Cluster') as mock_cluster_class:
        mock_cluster_class.return_value = mock_cluster

        instance = CassandraDB(
            contact_points=['127.0.0.1'],
            port=9042,
            username='testuser',
            password='testpass',
            keyspace='test_keyspace',
            collection_name='test_collection',
            embedding_model_dims=128,
            secure_connect_bundle='/path/to/bundle.zip'
        )

        assert instance.secure_connect_bundle == '/path/to/bundle.zip'


def test_search_with_filters(cassandra_instance):
    """Test vector search with filters."""
    # Mock the database response
    mock_row1 = Mock()
    mock_row1.id = 'id1'
    mock_row1.vector = [0.1, 0.2, 0.3]
    mock_row1.payload = json.dumps({"text": "test1", "category": "A"})

    mock_row2 = Mock()
    mock_row2.id = 'id2'
    mock_row2.vector = [0.4, 0.5, 0.6]
    mock_row2.payload = json.dumps({"text": "test2", "category": "B"})

    cassandra_instance.session.execute = Mock(return_value=[mock_row1, mock_row2])

    query_vector = [0.2, 0.3, 0.4]
    results = cassandra_instance.search(
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


def test_insert_without_ids(cassandra_instance):
    """Test vector insertion without providing IDs."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"text": "test1"}, {"text": "test2"}]

    mock_prepared = Mock()
    cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

    cassandra_instance.insert(vectors=vectors, payloads=payloads)

    assert cassandra_instance.session.prepare.called
    assert cassandra_instance.session.execute.called


def test_insert_without_payloads(cassandra_instance):
    """Test vector insertion without providing payloads."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    ids = ["id1", "id2"]

    mock_prepared = Mock()
    cassandra_instance.session.prepare = Mock(return_value=mock_prepared)

    cassandra_instance.insert(vectors=vectors, ids=ids)

    assert cassandra_instance.session.prepare.called
    assert cassandra_instance.session.execute.called

