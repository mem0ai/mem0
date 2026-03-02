import pytest
from unittest.mock import Mock, patch

from mem0.vector_stores.tidb import TiDBVector, OutputData


@pytest.fixture
def mock_connection():
    """Create a mock TiDB connection."""
    connection = Mock()
    connection.cursor = Mock()
    connection.commit = Mock()
    connection.close = Mock()
    return connection


@pytest.fixture
def mock_cursor():
    """Create a mock TiDB cursor."""
    cursor = Mock()
    cursor.execute = Mock()
    cursor.executemany = Mock()
    cursor.fetchone = Mock()
    cursor.fetchall = Mock()
    return cursor


@pytest.fixture
def tidb_instance(mock_connection, mock_cursor):
    """Create a TiDBVector instance with mocked connection."""
    with patch('mem0.vector_stores.tidb.pymysql') as mock_pymysql:
        mock_pymysql.connect.return_value = mock_connection
        
        # Mock the cursor context manager
        mock_connection.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = Mock(return_value=None)
        
        instance = TiDBVector(
            host="localhost",
            port=4000,
            user="root",
            password="",
            database="test_db",
            collection_name="test_table",
            embedding_model_dims=128,
        )
        instance.connection = mock_connection
        return instance


def test_tidb_init(mock_connection, mock_cursor):
    """Test TiDBVector initialization."""
    with patch('mem0.vector_stores.tidb.pymysql') as mock_pymysql:
        mock_pymysql.connect.return_value = mock_connection
        
        # Mock the cursor context manager
        mock_connection.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = Mock(return_value=None)

        instance = TiDBVector(
            host="localhost",
            port=4000,
            user="root",
            password="",
            database="test_db",
            collection_name="test_table",
            embedding_model_dims=128,
        )

        assert instance.host == "localhost"
        assert instance.port == 4000
        assert instance.user == "root"
        assert instance.database == "test_db"
        assert instance.collection_name == "test_table"
        assert instance.embedding_model_dims == 128


def test_create_col(tidb_instance, mock_cursor):
    """Test table creation."""
    # Mock table doesn't exist
    mock_cursor.fetchone.return_value = None
    
    tidb_instance.create_col(name="new_table", vector_size=256)

    # Verify that execute was called
    assert mock_cursor.execute.called
    assert tidb_instance.connection.commit.called


def test_insert(tidb_instance, mock_cursor):
    """Test vector insertion."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"text": "test1"}, {"text": "test2"}]
    ids = ["id1", "id2"]

    tidb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    assert mock_cursor.executemany.called
    assert tidb_instance.connection.commit.called


def test_search(tidb_instance, mock_cursor):
    """Test vector search."""
    # Mock the search results
    mock_results = [
        {
            'id': 'id1',
            'vector': '[0.1, 0.2, 0.3]',
            'payload': '{"text": "test1"}',
            'similarity': 0.8
        },
        {
            'id': 'id2',
            'vector': '[0.4, 0.5, 0.6]',
            'payload': '{"text": "test2"}',
            'similarity': 0.7
        }
    ]
    mock_cursor.fetchall.return_value = mock_results

    query_vector = [0.2, 0.3, 0.4]
    results = tidb_instance.search(query="test", vectors=query_vector, limit=5)

    assert isinstance(results, list)
    assert len(results) <= 5
    assert mock_cursor.execute.called


def test_delete(tidb_instance, mock_cursor):
    """Test vector deletion."""
    tidb_instance.delete(vector_id="test_id")

    assert mock_cursor.execute.called
    assert tidb_instance.connection.commit.called


def test_update(tidb_instance, mock_cursor):
    """Test vector update."""
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"text": "updated"}

    # Mock existing vector
    mock_cursor.fetchone.return_value = {"id": "test_id"}

    tidb_instance.update(vector_id="test_id", vector=new_vector, payload=new_payload)

    assert mock_cursor.execute.called
    assert tidb_instance.connection.commit.called


def test_get(tidb_instance, mock_cursor):
    """Test retrieving a vector by ID."""
    # Mock the vector retrieval
    mock_vector = {
        'id': 'test_id',
        'vector': '[0.1, 0.2, 0.3]',
        'payload': '{"text": "test"}'
    }
    mock_cursor.fetchone.return_value = mock_vector

    result = tidb_instance.get(vector_id="test_id")

    assert result is not None
    assert isinstance(result, OutputData)
    assert result.id == "test_id"


def test_list_cols(tidb_instance, mock_cursor):
    """Test listing tables."""
    mock_cursor.fetchall.return_value = [
        {"Tables_in_test_db": "table1"},
        {"Tables_in_test_db": "table2"}
    ]

    tables = tidb_instance.list_cols()

    assert isinstance(tables, list)
    assert len(tables) == 2
    assert "table1" in tables


def test_delete_col(tidb_instance, mock_cursor):
    """Test table deletion."""
    tidb_instance.delete_col()

    assert mock_cursor.execute.called
    assert tidb_instance.connection.commit.called


def test_col_info(tidb_instance, mock_cursor):
    """Test getting table information."""
    # Mock table count
    mock_cursor.fetchone.return_value = {"count": 100}

    info = tidb_instance.col_info()

    assert isinstance(info, dict)
    assert 'name' in info
    assert 'count' in info


def test_list(tidb_instance, mock_cursor):
    """Test listing vectors."""
    # Mock the search results
    mock_results = [
        {
            'id': 'id1',
            'vector': '[0.1, 0.2, 0.3]',
            'payload': '{"text": "test1"}'
        }
    ]
    mock_cursor.fetchall.return_value = mock_results

    results = tidb_instance.list(limit=10)

    assert isinstance(results, list)
    assert len(results) > 0


def test_reset(tidb_instance, mock_cursor):
    """Test resetting the table."""
    tidb_instance.reset()

    assert mock_cursor.execute.called
    assert tidb_instance.connection.commit.called


def test_search_with_filters(tidb_instance, mock_cursor):
    """Test vector search with filters."""
    # Mock the search results
    mock_results = [
        {
            'id': 'id1',
            'vector': '[0.1, 0.2, 0.3]',
            'payload': '{"text": "test1", "category": "A"}',
            'similarity': 0.8
        }
    ]
    mock_cursor.fetchall.return_value = mock_results

    query_vector = [0.2, 0.3, 0.4]
    results = tidb_instance.search(
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


def test_insert_without_ids(tidb_instance, mock_cursor):
    """Test vector insertion without providing IDs."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"text": "test1"}, {"text": "test2"}]

    tidb_instance.insert(vectors=vectors, payloads=payloads)

    assert mock_cursor.executemany.called
    assert tidb_instance.connection.commit.called


def test_insert_without_payloads(tidb_instance, mock_cursor):
    """Test vector insertion without providing payloads."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    ids = ["id1", "id2"]

    tidb_instance.insert(vectors=vectors, ids=ids)

    assert mock_cursor.executemany.called
    assert tidb_instance.connection.commit.called


def test_get_nonexistent_vector(tidb_instance, mock_cursor):
    """Test getting a non-existent vector."""
    # Mock empty result
    mock_cursor.fetchone.return_value = None

    result = tidb_instance.get(vector_id="nonexistent")

    assert result is None


def test_update_nonexistent_vector(tidb_instance, mock_cursor):
    """Test updating a non-existent vector."""
    # Mock empty result
    mock_cursor.fetchone.return_value = None

    tidb_instance.update(vector_id="nonexistent", vector=[0.1, 0.2, 0.3])

    # Should not call update for non-existent vector
    assert not tidb_instance.connection.commit.called


def test_list_with_filters(tidb_instance, mock_cursor):
    """Test listing vectors with filters."""
    # Mock the search results
    mock_results = [
        {
            'id': 'id1',
            'vector': '[0.1, 0.2, 0.3]',
            'payload': '{"text": "test1", "category": "A"}'
        }
    ]
    mock_cursor.fetchall.return_value = mock_results

    results = tidb_instance.list(filters={"category": "A"}, limit=10)

    assert isinstance(results, list)
    assert len(results) > 0
    # Should only return filtered results
    for result in results[0]:
        assert result.payload.get("category") == "A"


def test_connection_cleanup(tidb_instance):
    """Test connection cleanup."""
    tidb_instance.__del__()
    
    assert tidb_instance.connection.close.called
