import json
from unittest.mock import MagicMock, patch
import pytest

from tcvectordb.model import index as vdb_index
from tcvectordb.model.enum import IndexType
from mem0.vector_stores.tencentvector import TencentVectorDB


class TestTencentVectorDB:
    """Test suite for TencentVectorDB vector store."""

    @pytest.fixture
    def mock_tencent_client(self):
        """Mock RPCVectorDBClient to avoid requiring actual database connection."""
        with patch("mem0.vector_stores.tencentvector.tcvectordb.RPCVectorDBClient") as mock_client:
            mock_instance = MagicMock()
            mock_db = MagicMock()
            mock_col = MagicMock()
            
            mock_instance.database.return_value = mock_db
            mock_db.exists_collection.return_value = False
            mock_db.create_collection_if_not_exists.return_value = mock_col
            mock_db.collection.return_value = mock_col
            mock_client.return_value = mock_instance
            
            yield {
                "client": mock_instance,
                "db": mock_db,
                "col": mock_col,
            }

    @pytest.fixture
    def tencent_db(self, mock_tencent_client):
        """Create TencentVectorDB instance with mocked client."""
        return TencentVectorDB(
            url="http://localhost:8000",
            key="test_key",
            collection_name="test_collection",
            embedding_model_dims=1536,
            metric_type="COSINE",
            database_name="test_db",
            index_type="HNSW",
            index_params={"m": 16, "efconstruction": 200},
            sparse_language="en",
        )

    def test_initialization(self, mock_tencent_client):
        """Test that TencentVectorDB initializes correctly with params."""
        db = TencentVectorDB(
            url="http://localhost:8000",
            key="test_key",
            collection_name="test_collection",
            embedding_model_dims=1536,
            metric_type="L2",
            database_name="test_db",
            index_type="HNSW",
            index_params={"m": 32, "efconstruction": 150},
            sparse_language="zh",
        )
        assert db.collection_name == "test_collection"
        assert db.embedding_model_dims == 1536
        assert db.metric_type == "L2"
        assert db.database_name == "test_db"
        assert db.index_type == "HNSW"
        assert db.sparse_language == "zh"
        assert db.index_params == {"m": 32, "efconstruction": 150}

    def test_create_col_hnsw(self, mock_tencent_client):
        """Test collection creation with HNSW index parameters."""
        mock_db = mock_tencent_client["db"]
        TencentVectorDB(
            url="http://localhost:8000",
            key="test_key",
            collection_name="test_collection",
            embedding_model_dims=128,
            index_type="HNSW",
            index_params={"m": 24, "efconstruction": 100},
        )
        mock_db.create_collection_if_not_exists.assert_called_once()
        kwargs = mock_db.create_collection_if_not_exists.call_args[1]
        created_index = kwargs["index"]
        vector_index = created_index.indexes["vector"]
        assert vector_index._index_type == IndexType.HNSW
        assert isinstance(vector_index.param, vdb_index.HNSWParams)
        assert vector_index.param.M == 24
        assert vector_index.param.efConstruction == 100

    def test_create_col_ivf_pq(self, mock_tencent_client):
        """Test collection creation with IVF_PQ index parameters."""
        mock_db = mock_tencent_client["db"]
        TencentVectorDB(
            url="http://localhost:8000",
            key="test_key",
            collection_name="test_collection",
            embedding_model_dims=128,
            index_type="IVF_PQ",
            index_params={"nlist": 2048, "m": 16},
        )
        kwargs = mock_db.create_collection_if_not_exists.call_args[1]
        vector_index = kwargs["index"].indexes["vector"]
        assert vector_index._index_type == IndexType.IVF_PQ
        assert isinstance(vector_index.param, vdb_index.IVFPQParams)
        assert vector_index.param._nlist == 2048
        assert vector_index.param._M == 16

    def test_create_col_ivf_sq8(self, mock_tencent_client):
        """Test collection creation with IVF_SQ8 index parameters."""
        mock_db = mock_tencent_client["db"]
        TencentVectorDB(
            url="http://localhost:8000",
            key="test_key",
            collection_name="test_collection",
            embedding_model_dims=128,
            index_type="IVF_SQ8",
            index_params={"nlist": 4096},
        )
        kwargs = mock_db.create_collection_if_not_exists.call_args[1]
        vector_index = kwargs["index"].indexes["vector"]
        assert vector_index._index_type == IndexType.IVF_SQ8
        assert isinstance(vector_index.param, vdb_index.IVFSQ8Params)
        assert vector_index.param._nlist == 4096

    def test_create_col_ivf_rabitq(self, mock_tencent_client):
        """Test collection creation with IVF_RABITQ index parameters."""
        mock_db = mock_tencent_client["db"]
        TencentVectorDB(
            url="http://localhost:8000",
            key="test_key",
            collection_name="test_collection",
            embedding_model_dims=128,
            index_type="IVF_RABITQ",
            index_params={"nlist": 1024, "bits": 8},
        )
        kwargs = mock_db.create_collection_if_not_exists.call_args[1]
        vector_index = kwargs["index"].indexes["vector"]
        assert vector_index._index_type == IndexType.IVF_RABITQ
        assert isinstance(vector_index.param, vdb_index.IVFRABITQParams)
        assert vector_index.param.nlist == 1024
        assert vector_index.param.bits == 8

    def test_create_col_flat(self, mock_tencent_client):
        """Test collection creation with FLAT index (no params class)."""
        mock_db = mock_tencent_client["db"]
        TencentVectorDB(
            url="http://localhost:8000",
            key="test_key",
            collection_name="test_collection",
            embedding_model_dims=128,
            index_type="FLAT",
        )
        kwargs = mock_db.create_collection_if_not_exists.call_args[1]
        vector_index = kwargs["index"].indexes["vector"]
        assert vector_index._index_type == IndexType.FLAT
        assert vector_index.param is None

    def test_dict_to_tencent_expr(self, tencent_db):
        """Test metadata filter expression creation."""
        filters = {"user_id": "alice", "age": 25, "active": True, "wildcard": "*"}
        expr = tencent_db._dict_to_tencent_expr(filters)
        
        # wildcard should be ignored
        assert 'wildcard' not in expr
        # string filter should be quoted and escaped
        assert 'user_id = "alice"' in expr
        # numeric filter should be unquoted
        assert "age = 25" in expr
        # boolean filter should be lowercase unquoted
        assert "active = true" in expr
        # joined by and
        assert " and " in expr

    def test_dict_to_tencent_expr_advanced(self, tencent_db):
        """Test advanced and nested comparison metadata filter expression creation."""
        filters = {
            "user_id": {"eq": "alice"},
            "age": {"gt": 20, "lt": 30},
            "status": {"nin": ["deleted", "suspended"]},
            "tags": {"contains": "urgent"},
        }
        expr = tencent_db._dict_to_tencent_expr(filters)
        assert 'user_id = "alice"' in expr
        assert 'age > 20 and age < 30' in expr
        assert 'status not in ("deleted", "suspended")' in expr
        assert 'tags include ("urgent")' in expr

    def test_dict_to_tencent_expr_logical(self, tencent_db):
        """Test logical operators OR, AND, NOT in filter expression creation."""
        filters = {
            "OR": [{"user_id": "alice"}, {"user_id": "bob"}],
            "AND": [{"category": "work"}, {"NOT": [{"status": "archived"}]}]
        }
        expr = tencent_db._dict_to_tencent_expr(filters)
        assert '(user_id = "alice") or (user_id = "bob")' in expr
        assert '(category = "work") and (not (status = "archived"))' in expr

    def test_insert(self, tencent_db, mock_tencent_client):
        """Test batch insertion of vectors."""
        mock_col = mock_tencent_client["col"]
        vectors = [[0.1] * 1536, [0.2] * 1536]
        payloads = [{"data": "hello", "user_id": "alice"}, {"data": "world", "user_id": "bob"}]
        ids = ["id1", "id2"]

        tencent_db.insert(vectors, payloads, ids)
        
        mock_col.upsert.assert_called_once()
        docs = mock_col.upsert.call_args[0][0]
        assert len(docs) == 2
        assert docs[0].__dict__.get("id") == "id1"
        assert docs[0].__dict__.get("vector") == vectors[0]
        assert docs[0].__dict__.get("text") == "hello"
        assert docs[0].__dict__.get("user_id") == "alice"
        
        assert docs[1].__dict__.get("id") == "id2"
        assert docs[1].__dict__.get("vector") == vectors[1]
        assert docs[1].__dict__.get("text") == "world"
        assert docs[1].__dict__.get("user_id") == "bob"

    def test_search(self, tencent_db, mock_tencent_client):
        """Test vector similarity search."""
        mock_col = mock_tencent_client["col"]
        # Mock returned matches from search
        mock_col.search.return_value = [[
            {
                "id": "doc1",
                "score": 0.95,
                "metadata": json.dumps({"data": "hello", "user_id": "alice"}),
            }
        ]]

        query_vector = [0.1] * 1536
        filters = {"user_id": "alice"}
        results = tencent_db.search(query="test", vectors=query_vector, top_k=5, filters=filters)

        mock_col.search.assert_called_once()
        kwargs = mock_col.search.call_args[1]
        assert kwargs["vectors"] == [query_vector]
        assert kwargs["limit"] == 5
        assert kwargs["filter"].cond == 'user_id = "alice"'

        assert len(results) == 1
        assert results[0].id == "doc1"
        assert results[0].score == 0.95
        assert results[0].payload == {"data": "hello", "user_id": "alice"}

    def test_delete(self, tencent_db, mock_tencent_client):
        """Test deleting a document by ID."""
        mock_col = mock_tencent_client["col"]
        tencent_db.delete("doc1")
        mock_col.delete.assert_called_once_with(document_ids=["doc1"])

    def test_update(self, tencent_db, mock_tencent_client):
        """Test updating a document (delete + insert)."""
        # We patch the delete and insert methods of the instance
        with patch.object(tencent_db, "delete") as mock_delete, \
             patch.object(tencent_db, "insert") as mock_insert:
            
            vector = [0.1] * 1536
            payload = {"data": "hello"}
            
            tencent_db.update("doc1", vector, payload)
            
            mock_delete.assert_called_once_with("doc1")
            mock_insert.assert_called_once_with([vector], [payload], ["doc1"])

    def test_get(self, tencent_db, mock_tencent_client):
        """Test retrieving a document by ID."""
        mock_col = mock_tencent_client["col"]
        mock_col.query.return_value = [
            {
                "id": "doc1",
                "text": "hello",
                "metadata": json.dumps({"data": "hello", "user_id": "alice"}),
            }
        ]

        result = tencent_db.get("doc1")
        
        mock_col.query.assert_called_once_with(document_ids=["doc1"], retrieve_vector=False)
        assert result is not None
        assert result.id == "doc1"
        assert result.payload == {"data": "hello", "user_id": "alice"}

    def test_list(self, tencent_db, mock_tencent_client):
        """Test listing documents matching filters."""
        mock_col = mock_tencent_client["col"]
        mock_col.query.return_value = [
            {"id": "doc1", "text": "hello", "user_id": "alice"}
        ]

        results = tencent_db.list(filters={"user_id": "alice"}, top_k=10)

        mock_col.query.assert_called_once_with(
            filter='user_id = "alice"',
            limit=10,
            retrieve_vector=False,
        )
        assert len(results) == 1
        assert results[0].id == "doc1"
        assert results[0].payload == {"data": "hello", "user_id": "alice"}

    def test_delete_col(self, tencent_db, mock_tencent_client):
        """Test deleting the collection."""
        mock_db = mock_tencent_client["db"]
        tencent_db.delete_col()
        mock_db.drop_collection.assert_called_once_with("test_collection")
        assert tencent_db.collection is None

    def test_reset(self, tencent_db, mock_tencent_client):
        """Test resetting the collection (drop + recreate)."""
        with patch.object(tencent_db, "delete_col") as mock_delete, \
             patch.object(tencent_db, "create_col") as mock_create:
             
            tencent_db.reset()
            mock_delete.assert_called_once()
            mock_create.assert_called_once_with(
                name="test_collection",
                vector_size=1536,
                distance="COSINE",
            )
