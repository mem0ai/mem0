import json
import pytest
from unittest.mock import Mock, patch

from mem0.vector_stores.azure_mysql import AzureMySQL, OutputData


@pytest.fixture
def mock_connection_pool():
    """Create a mock connection pool."""
    pool = Mock()
    conn = Mock()
    cursor = Mock()

    # Setup cursor mock
    cursor.fetchall = Mock(return_value=[])
    cursor.fetchone = Mock(return_value=None)
    cursor.execute = Mock()
    cursor.executemany = Mock()
    cursor.close = Mock()

    # Setup connection mock
    conn.cursor = Mock(return_value=cursor)
    conn.commit = Mock()
    conn.rollback = Mock()
    conn.close = Mock()

    # Setup pool mock
    pool.connection = Mock(return_value=conn)
    pool.close = Mock()

    return pool


@pytest.fixture
def azure_mysql_instance(mock_connection_pool):
    """Create an AzureMySQL instance with mocked connection pool."""
    with patch('mem0.vector_stores.azure_mysql.PooledDB') as mock_pooled_db:
        mock_pooled_db.return_value = mock_connection_pool

        instance = AzureMySQL(
            host="test-server.mysql.database.azure.com",
            port=3306,
            user="testuser",
            password="testpass",
            database="testdb",
            collection_name="test_collection",
            embedding_model_dims=128,
            use_azure_credential=False,
            ssl_disabled=True,
        )
        instance.connection_pool = mock_connection_pool
        return instance


def test_azure_mysql_init(mock_connection_pool):
    """Test AzureMySQL initialization."""
    with patch('mem0.vector_stores.azure_mysql.PooledDB') as mock_pooled_db:
        mock_pooled_db.return_value = mock_connection_pool

        instance = AzureMySQL(
            host="test-server.mysql.database.azure.com",
            port=3306,
            user="testuser",
            password="testpass",
            database="testdb",
            collection_name="test_collection",
            embedding_model_dims=128,
        )

        assert instance.host == "test-server.mysql.database.azure.com"
        assert instance.port == 3306
        assert instance.user == "testuser"
        assert instance.database == "testdb"
        assert instance.collection_name == "test_collection"
        assert instance.embedding_model_dims == 128


def test_create_col(azure_mysql_instance):
    """Test collection creation."""
    azure_mysql_instance.create_col(name="new_collection", vector_size=256)

    # Verify that execute was called (table creation)
    conn = azure_mysql_instance.connection_pool.connection()
    cursor = conn.cursor()
    assert cursor.execute.called


def test_insert(azure_mysql_instance):
    """Test vector insertion."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"text": "test1"}, {"text": "test2"}]
    ids = ["id1", "id2"]

    azure_mysql_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    conn = azure_mysql_instance.connection_pool.connection()
    cursor = conn.cursor()
    assert cursor.executemany.called


def test_search(azure_mysql_instance):
    """Test vector search."""
    # Mock the database response
    conn = azure_mysql_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchall = Mock(return_value=[
        {
            'id': 'id1',
            'vector': json.dumps([0.1, 0.2, 0.3]),
            'payload': json.dumps({"text": "test1"})
        },
        {
            'id': 'id2',
            'vector': json.dumps([0.4, 0.5, 0.6]),
            'payload': json.dumps({"text": "test2"})
        }
    ])

    query_vector = [0.2, 0.3, 0.4]
    results = azure_mysql_instance.search(query="test", vectors=query_vector, limit=5)

    assert isinstance(results, list)
    assert cursor.execute.called


def test_delete(azure_mysql_instance):
    """Test vector deletion."""
    azure_mysql_instance.delete(vector_id="test_id")

    conn = azure_mysql_instance.connection_pool.connection()
    cursor = conn.cursor()
    assert cursor.execute.called


def test_update(azure_mysql_instance):
    """Test vector update."""
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"text": "updated"}

    azure_mysql_instance.update(vector_id="test_id", vector=new_vector, payload=new_payload)

    conn = azure_mysql_instance.connection_pool.connection()
    cursor = conn.cursor()
    assert cursor.execute.called


def test_get(azure_mysql_instance):
    """Test retrieving a vector by ID."""
    # Mock the database response
    conn = azure_mysql_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchone = Mock(return_value={
        'id': 'test_id',
        'vector': json.dumps([0.1, 0.2, 0.3]),
        'payload': json.dumps({"text": "test"})
    })

    result = azure_mysql_instance.get(vector_id="test_id")

    assert result is not None
    assert isinstance(result, OutputData)
    assert result.id == "test_id"


def test_list_cols(azure_mysql_instance):
    """Test listing collections."""
    # Mock the database response
    conn = azure_mysql_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchall = Mock(return_value=[
        {"Tables_in_testdb": "collection1"},
        {"Tables_in_testdb": "collection2"}
    ])

    collections = azure_mysql_instance.list_cols()

    assert isinstance(collections, list)
    assert len(collections) == 2


def test_delete_col(azure_mysql_instance):
    """Test collection deletion."""
    azure_mysql_instance.delete_col()

    conn = azure_mysql_instance.connection_pool.connection()
    cursor = conn.cursor()
    assert cursor.execute.called


def test_col_info(azure_mysql_instance):
    """Test getting collection information."""
    # Mock the database response
    conn = azure_mysql_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchone = Mock(return_value={
        'name': 'test_collection',
        'count': 100,
        'size_mb': 1.5
    })

    info = azure_mysql_instance.col_info()

    assert isinstance(info, dict)
    assert cursor.execute.called


def test_list(azure_mysql_instance):
    """Test listing vectors."""
    # Mock the database response
    conn = azure_mysql_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchall = Mock(return_value=[
        {
            'id': 'id1',
            'vector': json.dumps([0.1, 0.2, 0.3]),
            'payload': json.dumps({"text": "test1"})
        }
    ])

    results = azure_mysql_instance.list(limit=10)

    assert isinstance(results, list)
    assert len(results) > 0


def test_reset(azure_mysql_instance):
    """Test resetting the collection."""
    azure_mysql_instance.reset()

    conn = azure_mysql_instance.connection_pool.connection()
    cursor = conn.cursor()
    # Should call execute at least twice (drop and create)
    assert cursor.execute.call_count >= 2


@pytest.mark.skipif(True, reason="Requires Azure credentials")
def test_azure_credential_authentication():
    """Test Azure DefaultAzureCredential authentication."""
    with patch('mem0.vector_stores.azure_mysql.DefaultAzureCredential') as mock_cred:
        mock_token = Mock()
        mock_token.token = "test_token"
        mock_cred.return_value.get_token.return_value = mock_token

        instance = AzureMySQL(
            host="test-server.mysql.database.azure.com",
            port=3306,
            user="testuser",
            password=None,
            database="testdb",
            collection_name="test_collection",
            embedding_model_dims=128,
            use_azure_credential=True,
        )

        assert instance.password == "test_token"


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
