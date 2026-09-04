import pytest
from unittest.mock import MagicMock, patch

from mem0.vector_stores.clickhouse import ClickhouseDB


@pytest.fixture
def mock_clickhouse_client():
    with patch("mem0.vector_stores.clickhouse.clickhouse_connect") as mock_clickhouse:
        mock_client = MagicMock()
        mock_clickhouse.get_client.return_value = mock_client
        yield mock_client


@pytest.fixture
def clickhouse_db(mock_clickhouse_client):
    return ClickhouseDB(collection_name="test_collection")


def test_insert(clickhouse_db, mock_clickhouse_client):
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"meta": "data1"}, {"meta": "data2"}]
    ids = ["id1", "id2"]

    clickhouse_db.insert(vectors=vectors, payloads=payloads, ids=ids)

    mock_clickhouse_client.insert.assert_called_once()
    args, kwargs = mock_clickhouse_client.insert.call_args
    assert args[0] == "test_collection"
    assert len(args[1]) == 2
    assert kwargs["column_names"] == ["id", "vector", "payload"]


def test_search(clickhouse_db, mock_clickhouse_client):
    query = "test query"
    vectors = [[0.1, 0.2, 0.3]]

    mock_result = MagicMock()
    mock_result.result_rows = [("id1", 0.95, '{"meta": "data1"}'), ("id2", 0.85, '{"meta": "data2"}')]
    mock_clickhouse_client.query.return_value = mock_result

    results = clickhouse_db.search(query=query, vectors=vectors, top_k=2)

    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.95
    assert results[0].payload == {"meta": "data1"}

    # Check that search generates correct SQL (roughly)
    mock_clickhouse_client.query.assert_called_once()
    call_arg = mock_clickhouse_client.query.call_args[0][0]
    assert "cosineDistance" in call_arg
    assert "ORDER BY score DESC" in call_arg


def test_delete(clickhouse_db, mock_clickhouse_client):
    clickhouse_db.delete("id1")
    mock_clickhouse_client.command.assert_called_with("ALTER TABLE test_collection DELETE WHERE id = 'id1'")


def test_update(clickhouse_db, mock_clickhouse_client):
    vector = [0.1, 0.2, 0.3]
    payload = {"meta": "updated"}

    clickhouse_db.update(vector_id="id1", vector=vector, payload=payload)

    assert mock_clickhouse_client.command.call_count == 2
    calls = mock_clickhouse_client.command.call_args_list
    assert "UPDATE vector = [0.1, 0.2, 0.3]" in calls[0][0][0]
    assert 'UPDATE payload = \'{"meta": "updated"}\'' in calls[1][0][0]


def test_get(clickhouse_db, mock_clickhouse_client):
    mock_result = MagicMock()
    mock_result.result_rows = [("id1", [0.1, 0.2, 0.3], '{"meta": "data1"}')]
    mock_clickhouse_client.query.return_value = mock_result

    result = clickhouse_db.get("id1")

    assert result is not None
    assert result.id == "id1"
    assert result.payload == {"meta": "data1"}


def test_list(clickhouse_db, mock_clickhouse_client):
    mock_result = MagicMock()
    mock_result.result_rows = [("id1", '{"meta": "data1"}'), ("id2", '{"meta": "data2"}')]
    mock_clickhouse_client.query.return_value = mock_result

    results = clickhouse_db.list()

    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].payload == {"meta": "data1"}
