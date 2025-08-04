from unittest.mock import Mock, patch

import pytest

from mem0.vector_stores.lance import LanceDB, OutputData


@pytest.fixture
def mock_lancedb_client():
    with patch("lancedb.connect") as mock_connect:
        yield mock_connect


@pytest.fixture
def lancedb_instance(mock_lancedb_client):
    mock_db = Mock()
    mock_table = Mock()
    mock_db.open_table.return_value = mock_table
    mock_db.table_names.return_value = []
    mock_lancedb_client.return_value = mock_db
    # Patch pyarrow schema creation
    with patch("pyarrow.schema") as mock_schema:
        mock_schema.return_value = Mock()
        instance = LanceDB(collection_name="test_collection", embedding_model_dims=3)
    instance.db = mock_db
    instance.db.open_table.return_value = mock_table
    return instance


def test_insert_vectors(lancedb_instance):
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]
    lancedb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)
    lancedb_instance.db.open_table.return_value.add.assert_called_once()


def test_search_vectors(lancedb_instance):
    mock_table = lancedb_instance.db.open_table.return_value
    mock_table.search.return_value.limit.return_value.to_pandas.return_value.to_dict.return_value = [
        {"id": "id1", "score": 0.1, "payload": '{"name": "vector1"}'},
        {"id": "id2", "score": 0.2, "payload": '{"name": "vector2"}'},
    ]
    vectors = [0.1, 0.2, 0.3]
    results = lancedb_instance.search(query="", vectors=vectors, limit=2)
    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.1
    assert results[0].payload == {"name": "vector1"}


def test_delete_vector(lancedb_instance):
    vector_id = "id1"
    lancedb_instance.delete(vector_id=vector_id)
    lancedb_instance.db.open_table.return_value.delete.assert_called_once()


def test_update_vector(lancedb_instance):
    vector_id = "id1"
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"name": "updated_vector"}
    # Mock get to return an OutputData
    lancedb_instance.get = Mock(return_value=OutputData(id=vector_id, score=1.0, payload={"name": "vector1"}))
    lancedb_instance.delete = Mock()
    lancedb_instance.insert = Mock()
    lancedb_instance.update(vector_id=vector_id, vector=new_vector, payload=new_payload)
    lancedb_instance.delete.assert_called_once_with(vector_id)
    lancedb_instance.insert.assert_called_once()


def test_get_vector(lancedb_instance):
    mock_table = lancedb_instance.db.open_table.return_value
    mock_table.to_pandas.return_value.query.return_value.empty = False
    mock_table.to_pandas.return_value.query.return_value.to_dict.return_value = [
        {"id": "id1", "payload": '{"name": "vector1"}'}
    ]
    result = lancedb_instance.get(vector_id="id1")
    assert result.id == "id1"
    assert result.payload == {"name": "vector1"}


def test_list_vectors(lancedb_instance):
    mock_table = lancedb_instance.db.open_table.return_value
    mock_table.to_pandas.return_value.to_dict.return_value = [
        {"id": "id1", "payload": '{"name": "vector1"}'},
        {"id": "id2", "payload": '{"name": "vector2"}'},
    ]
    results = lancedb_instance.list(limit=2)
    assert isinstance(results, list)
    assert isinstance(results[0], list)
    assert len(results[0]) == 2
    assert results[0][0].id == "id1"
    assert results[0][1].id == "id2"
