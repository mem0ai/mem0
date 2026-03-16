import json
import numpy as np
import pytest
from unittest.mock import Mock, patch

from mem0.configs.vector_stores.polardb import SUPPORTED_INDEX_TYPES
from mem0.vector_stores.polardb import PolarDB, OutputData, METRIC_MAP


@pytest.fixture
def mock_connection_pool():
    """Create a mock connection pool."""
    pool = Mock()
    conn = Mock()
    cursor = Mock()

    cursor.fetchall = Mock(return_value=[])
    cursor.fetchone = Mock(return_value=None)
    cursor.execute = Mock()
    cursor.executemany = Mock()
    cursor.close = Mock()

    conn.cursor = Mock(return_value=cursor)
    conn.commit = Mock()
    conn.rollback = Mock()
    conn.close = Mock()

    pool.connection = Mock(return_value=conn)
    pool.close = Mock()

    return pool


@pytest.fixture
def polardb_instance(mock_connection_pool):
    """Create a PolarDB instance with mocked connection pool."""
    with patch("mem0.vector_stores.polardb.PooledDB") as mock_pooled_db:
        mock_pooled_db.return_value = mock_connection_pool

        instance = PolarDB(
            host="test-polardb.mysql.polardb.rds.aliyuncs.com",
            port=3306,
            user="testuser",
            password="testpass",
            database="testdb",
            collection_name="test_collection",
            embedding_model_dims=128,
            metric="cosine",
            hnsw_m=16,
            hnsw_ef_construction=200,
            ssl_disabled=True,
        )
        instance.connection_pool = mock_connection_pool
        return instance


def test_polardb_init(mock_connection_pool):
    """Test PolarDB initialization."""
    with patch("mem0.vector_stores.polardb.PooledDB") as mock_pooled_db:
        mock_pooled_db.return_value = mock_connection_pool

        instance = PolarDB(
            host="test-polardb.mysql.polardb.rds.aliyuncs.com",
            port=3306,
            user="testuser",
            password="testpass",
            database="testdb",
            collection_name="test_collection",
            embedding_model_dims=128,
        )

        assert instance.host == "test-polardb.mysql.polardb.rds.aliyuncs.com"
        assert instance.port == 3306
        assert instance.user == "testuser"
        assert instance.database == "testdb"
        assert instance.collection_name == "test_collection"
        assert instance.embedding_model_dims == 128
        assert instance.metric == "cosine"
        assert instance.polardb_metric == "COSINE"


def test_polardb_init_invalid_metric(mock_connection_pool):
    """Test PolarDB initialization with invalid metric."""
    with patch("mem0.vector_stores.polardb.PooledDB") as mock_pooled_db:
        mock_pooled_db.return_value = mock_connection_pool

        with pytest.raises(ValueError, match="Unsupported metric"):
            PolarDB(
                host="test-host",
                port=3306,
                user="testuser",
                password="testpass",
                database="testdb",
                collection_name="test_collection",
                embedding_model_dims=128,
                metric="invalid_metric",
                ssl_disabled=True,
            )


def test_vector_to_bytes():
    """Test vector to binary conversion."""
    v = [1.0, 2.0, 3.0, 4.0]
    result = PolarDB._vector_to_bytes(v)

    assert isinstance(result, bytes)
    assert len(result) == 4 * 4  # 4 floats * 4 bytes each
    # Verify round-trip
    restored = PolarDB._bytes_to_vector(result)
    np.testing.assert_array_almost_equal(restored, v)


def test_bytes_to_vector():
    """Test binary to vector conversion."""
    original = [1.5, 2.5, 3.5]
    binary = np.array(original, dtype="float32").tobytes()
    result = PolarDB._bytes_to_vector(binary)

    assert isinstance(result, list)
    np.testing.assert_array_almost_equal(result, original)


def test_build_vector_index_comment(polardb_instance):
    """Test FAISS_HNSW_FLAT index comment generation."""
    comment = polardb_instance._build_vector_index_comment()
    assert "imci_vector_index=FAISS_HNSW_FLAT(" in comment
    assert "metric=cosine" in comment
    assert "max_degree=16" in comment
    assert "ef_construction=200" in comment


def test_create_col(polardb_instance):
    """Test collection creation with VECTOR type and HNSW index."""
    polardb_instance.create_col(name="new_collection", vector_size=256)

    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    assert cursor.execute.called

    call_args = cursor.execute.call_args[0][0]
    assert "CREATE TABLE" in call_args
    assert "VECTOR(256)" in call_args
    assert "imci_vector_index=FAISS_HNSW_FLAT" in call_args
    assert "COLUMNAR=1" in call_args


def test_insert(polardb_instance):
    """Test vector insertion with binary encoding."""
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"text": "test1"}, {"text": "test2"}]
    ids = ["id1", "id2"]

    polardb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    assert cursor.executemany.called

    call_args = cursor.executemany.call_args
    sql = call_args[0][0]
    data = call_args[0][1]
    assert "_binary" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert len(data) == 2
    # Verify binary encoding
    assert isinstance(data[0][1], bytes)


def test_search(polardb_instance):
    """Test vector search using server-side DISTANCE function."""
    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchall = Mock(
        return_value=[
            {"id": "id1", "score": 0.1, "payload": json.dumps({"text": "test1"})},
            {"id": "id2", "score": 0.2, "payload": json.dumps({"text": "test2"})},
        ]
    )

    query_vector = [0.2, 0.3, 0.4]
    results = polardb_instance.search(query="test", vectors=query_vector, limit=5)

    assert isinstance(results, list)
    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.1
    assert results[0].payload == {"text": "test1"}

    call_args = cursor.execute.call_args[0]
    sql = call_args[0]
    assert "DISTANCE" in sql
    assert "COSINE" in sql
    assert "ORDER BY score ASC" in sql
    assert "_binary" in sql


def test_search_with_filters(polardb_instance):
    """Test vector search with payload filters."""
    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchall = Mock(
        return_value=[
            {"id": "id1", "score": 0.1, "payload": json.dumps({"user_id": "user1", "text": "test"})},
        ]
    )

    results = polardb_instance.search(
        query="test",
        vectors=[0.1, 0.2, 0.3],
        limit=5,
        filters={"user_id": "user1"},
    )

    assert len(results) == 1
    call_args = cursor.execute.call_args[0]
    sql = call_args[0]
    assert "JSON_EXTRACT" in sql
    assert "WHERE" in sql


def test_delete(polardb_instance):
    """Test vector deletion."""
    polardb_instance.delete(vector_id="test_id")

    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    assert cursor.execute.called
    call_args = cursor.execute.call_args[0]
    assert "DELETE" in call_args[0]


def test_update_vector(polardb_instance):
    """Test updating a vector with binary encoding."""
    new_vector = [0.7, 0.8, 0.9]
    polardb_instance.update(vector_id="test_id", vector=new_vector)

    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    assert cursor.execute.called
    call_args = cursor.execute.call_args[0]
    assert "UPDATE" in call_args[0]
    assert "_binary" in call_args[0]
    assert isinstance(call_args[1][0], bytes)


def test_update_payload(polardb_instance):
    """Test updating payload."""
    new_payload = {"text": "updated"}
    polardb_instance.update(vector_id="test_id", payload=new_payload)

    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    assert cursor.execute.called


def test_get(polardb_instance):
    """Test retrieving a vector by ID."""
    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchone = Mock(
        return_value={
            "id": "test_id",
            "payload": json.dumps({"text": "test"}),
        }
    )

    result = polardb_instance.get(vector_id="test_id")

    assert result is not None
    assert isinstance(result, OutputData)
    assert result.id == "test_id"
    assert result.payload == {"text": "test"}


def test_get_not_found(polardb_instance):
    """Test retrieving a non-existent vector."""
    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchone = Mock(return_value=None)

    result = polardb_instance.get(vector_id="nonexistent")
    assert result is None


def test_list_cols(polardb_instance):
    """Test listing collections."""
    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchall = Mock(
        return_value=[
            {"Tables_in_testdb": "collection1"},
            {"Tables_in_testdb": "collection2"},
        ]
    )

    collections = polardb_instance.list_cols()

    assert isinstance(collections, list)
    assert len(collections) == 2
    assert "collection1" in collections


def test_delete_col(polardb_instance):
    """Test collection deletion."""
    polardb_instance.delete_col()

    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    assert cursor.execute.called
    call_args = cursor.execute.call_args[0][0]
    assert "DROP TABLE" in call_args


def test_col_info(polardb_instance):
    """Test getting collection information."""
    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchone = Mock(
        return_value={
            "name": "test_collection",
            "count": 100,
            "size_mb": 1.5,
        }
    )

    info = polardb_instance.col_info()

    assert isinstance(info, dict)
    assert info["name"] == "test_collection"
    assert info["count"] == 100
    assert info["size"] == "1.5 MB"


def test_col_info_empty(polardb_instance):
    """Test col_info when collection doesn't exist."""
    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchone = Mock(return_value=None)

    info = polardb_instance.col_info()
    assert info == {}


def test_list(polardb_instance):
    """Test listing vectors."""
    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchall = Mock(
        return_value=[
            {"id": "id1", "payload": json.dumps({"text": "test1"})},
            {"id": "id2", "payload": json.dumps({"text": "test2"})},
        ]
    )

    results = polardb_instance.list(limit=10)

    assert isinstance(results, list)
    assert len(results) == 1  # Wrapped in outer list
    assert len(results[0]) == 2


def test_list_with_filters(polardb_instance):
    """Test listing vectors with filters."""
    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    cursor.fetchall = Mock(
        return_value=[
            {"id": "id1", "payload": json.dumps({"user_id": "user1"})},
        ]
    )

    results = polardb_instance.list(filters={"user_id": "user1"}, limit=10)

    assert len(results[0]) == 1
    call_args = cursor.execute.call_args[0]
    assert "JSON_EXTRACT" in call_args[0]


def test_reset(polardb_instance):
    """Test resetting the collection."""
    polardb_instance.reset()

    conn = polardb_instance.connection_pool.connection()
    cursor = conn.cursor()
    # Should call execute at least twice (drop and create)
    assert cursor.execute.call_count >= 2


def test_metric_map():
    """Test metric mapping completeness."""
    assert METRIC_MAP["cosine"] == "COSINE"
    assert METRIC_MAP["euclidean"] == "EUCLIDEAN"
    assert METRIC_MAP["inner_product"] == "DOT"


def test_supported_index_types():
    """Test supported index types."""
    assert "FAISS_HNSW_FLAT" in SUPPORTED_INDEX_TYPES
    assert "FAISS_HNSW_PQ" in SUPPORTED_INDEX_TYPES
    assert "FAISS_HNSW_SQ" in SUPPORTED_INDEX_TYPES


def test_index_type_faiss_hnsw_pq(mock_connection_pool):
    """Test PolarDB with FAISS_HNSW_PQ index type generates correct comment."""
    with patch("mem0.vector_stores.polardb.PooledDB") as mock_pooled_db:
        mock_pooled_db.return_value = mock_connection_pool

        instance = PolarDB(
            host="test-host",
            port=3306,
            user="testuser",
            password="testpass",
            database="testdb",
            collection_name="test_collection",
            embedding_model_dims=128,
            index_type="FAISS_HNSW_PQ",
            pq_m=8,
            pq_nbits=8,
            ssl_disabled=True,
        )
        instance.connection_pool = mock_connection_pool

        comment = instance._build_vector_index_comment()
        assert "imci_vector_index=FAISS_HNSW_PQ(" in comment
        assert "pq_m=8" in comment
        assert "pq_nbits=8" in comment
        assert "metric=cosine" in comment


def test_index_type_faiss_hnsw_sq(mock_connection_pool):
    """Test PolarDB with FAISS_HNSW_SQ index type generates correct comment."""
    with patch("mem0.vector_stores.polardb.PooledDB") as mock_pooled_db:
        mock_pooled_db.return_value = mock_connection_pool

        instance = PolarDB(
            host="test-host",
            port=3306,
            user="testuser",
            password="testpass",
            database="testdb",
            collection_name="test_collection",
            embedding_model_dims=128,
            index_type="FAISS_HNSW_SQ",
            sq_type="SQ8",
            ssl_disabled=True,
        )
        instance.connection_pool = mock_connection_pool

        comment = instance._build_vector_index_comment()
        assert "imci_vector_index=FAISS_HNSW_SQ(" in comment
        assert "sq_type=SQ8" in comment
        assert "metric=cosine" in comment


def test_index_type_faiss_hnsw_flat_no_extra_params(polardb_instance):
    """Test FAISS_HNSW_FLAT does not include PQ/SQ params in comment."""
    comment = polardb_instance._build_vector_index_comment()
    assert "pq_m" not in comment
    assert "pq_nbits" not in comment
    assert "sq_type" not in comment


def test_invalid_index_type(mock_connection_pool):
    """Test PolarDB initialization with invalid index type."""
    with patch("mem0.vector_stores.polardb.PooledDB") as mock_pooled_db:
        mock_pooled_db.return_value = mock_connection_pool

        with pytest.raises(ValueError, match="Unsupported index_type"):
            PolarDB(
                host="test-host",
                port=3306,
                user="testuser",
                password="testpass",
                database="testdb",
                collection_name="test_collection",
                embedding_model_dims=128,
                index_type="INVALID",
                ssl_disabled=True,
            )


def test_output_data_model():
    """Test OutputData model."""
    data = OutputData(id="test_id", score=0.95, payload={"text": "test"})

    assert data.id == "test_id"
    assert data.score == 0.95
    assert data.payload == {"text": "test"}


def test_output_data_model_optional_fields():
    """Test OutputData model with optional fields."""
    data = OutputData(id=None, score=None, payload=None)

    assert data.id is None
    assert data.score is None
    assert data.payload is None
