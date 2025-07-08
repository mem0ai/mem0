from unittest.mock import Mock, PropertyMock, patch

import pytest
from pymochow.exception import ServerError
from pymochow.model.enum import ServerErrCode, TableState
from pymochow.model.table import (
    FloatVector,
    Table,
    VectorSearchConfig,
    VectorTopkSearchRequest,
)

from mem0.vector_stores.baidu import BaiduDB


@pytest.fixture
def mock_mochow_client():
    with patch("pymochow.MochowClient") as mock_client:
        yield mock_client


@pytest.fixture
def mock_configuration():
    with patch("pymochow.configuration.Configuration") as mock_config:
        yield mock_config


@pytest.fixture
def mock_bce_credentials():
    with patch("pymochow.auth.bce_credentials.BceCredentials") as mock_creds:
        yield mock_creds


@pytest.fixture
def mock_table():
    mock_table = Mock(spec=Table)
    # 设置 Table 类的属性
    type(mock_table).database_name = PropertyMock(return_value="test_db")
    type(mock_table).table_name = PropertyMock(return_value="test_table")
    type(mock_table).schema = PropertyMock(return_value=Mock())
    type(mock_table).replication = PropertyMock(return_value=1)
    type(mock_table).partition = PropertyMock(return_value=Mock())
    type(mock_table).enable_dynamic_field = PropertyMock(return_value=False)
    type(mock_table).description = PropertyMock(return_value="")
    type(mock_table).create_time = PropertyMock(return_value="")
    type(mock_table).state = PropertyMock(return_value=TableState.NORMAL)
    type(mock_table).aliases = PropertyMock(return_value=[])
    return mock_table


@pytest.fixture
def mochow_instance(mock_mochow_client, mock_configuration, mock_bce_credentials, mock_table):
    mock_database = Mock()
    mock_client_instance = Mock()

    # Mock the client creation
    mock_mochow_client.return_value = mock_client_instance

    # Mock database operations
    mock_client_instance.list_databases.return_value = []
    mock_client_instance.create_database.return_value = mock_database
    mock_client_instance.database.return_value = mock_database

    # Mock table operations
    mock_database.list_table.return_value = []
    mock_database.create_table.return_value = mock_table
    mock_database.describe_table.return_value = Mock(state=TableState.NORMAL)
    mock_database.table.return_value = mock_table

    return BaiduDB(
        endpoint="http://localhost:8287",
        account="test_account",
        api_key="test_api_key",
        database_name="test_db",
        table_name="test_table",
        embedding_model_dims=128,
        metric_type="COSINE",
    )


def test_insert(mochow_instance, mock_mochow_client):
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]

    mochow_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    # Verify table.upsert was called with correct data
    assert mochow_instance._table.upsert.call_count == 2
    calls = mochow_instance._table.upsert.call_args_list

    # Check first call
    first_row = calls[0][1]["rows"][0]
    assert first_row._data["id"] == "id1"
    assert first_row._data["vector"] == [0.1, 0.2, 0.3]
    assert first_row._data["metadata"] == {"name": "vector1"}

    # Check second call
    second_row = calls[1][1]["rows"][0]
    assert second_row._data["id"] == "id2"
    assert second_row._data["vector"] == [0.4, 0.5, 0.6]
    assert second_row._data["metadata"] == {"name": "vector2"}


def test_search(mochow_instance, mock_mochow_client):
    # Mock search results
    mock_search_results = Mock()
    mock_search_results.rows = [
        {"row": {"id": "id1", "metadata": {"name": "vector1"}}, "score": 0.1},
        {"row": {"id": "id2", "metadata": {"name": "vector2"}}, "score": 0.2},
    ]
    mochow_instance._table.vector_search.return_value = mock_search_results

    vectors = [0.1, 0.2, 0.3]
    results = mochow_instance.search(query="test", vectors=vectors, limit=2)

    # Verify search was called with correct parameters
    mochow_instance._table.vector_search.assert_called_once()
    call_args = mochow_instance._table.vector_search.call_args
    request = call_args[0][0] if call_args[0] else call_args[1]["request"]

    assert isinstance(request, VectorTopkSearchRequest)
    assert request._vector_field == "vector"
    assert isinstance(request._vector, FloatVector)
    assert request._vector._floats == vectors
    assert request._limit == 2
    assert isinstance(request._config, VectorSearchConfig)
    assert request._config._ef == 200

    # Verify results
    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.1
    assert results[0].payload == {"name": "vector1"}
    assert results[1].id == "id2"
    assert results[1].score == 0.2
    assert results[1].payload == {"name": "vector2"}


def test_search_with_filters(mochow_instance, mock_mochow_client):
    mochow_instance._table.vector_search.return_value = Mock(rows=[])

    vectors = [0.1, 0.2, 0.3]
    filters = {"user_id": "user123", "agent_id": "agent456"}

    mochow_instance.search(query="test", vectors=vectors, limit=2, filters=filters)

    # Verify search was called with filter
    call_args = mochow_instance._table.vector_search.call_args
    request = call_args[0][0] if call_args[0] else call_args[1]["request"]

    assert request._filter == 'metadata["user_id"] = "user123" AND metadata["agent_id"] = "agent456"'


def test_delete(mochow_instance, mock_mochow_client):
    vector_id = "id1"
    mochow_instance.delete(vector_id=vector_id)

    mochow_instance._table.delete.assert_called_once_with(primary_key={"id": vector_id})


def test_update(mochow_instance, mock_mochow_client):
    vector_id = "id1"
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"name": "updated_vector"}

    mochow_instance.update(vector_id=vector_id, vector=new_vector, payload=new_payload)

    mochow_instance._table.upsert.assert_called_once()
    call_args = mochow_instance._table.upsert.call_args
    row = call_args[0][0] if call_args[0] else call_args[1]["rows"][0]

    assert row._data["id"] == vector_id
    assert row._data["vector"] == new_vector
    assert row._data["metadata"] == new_payload


def test_get(mochow_instance, mock_mochow_client):
    # Mock query result
    mock_result = Mock()
    mock_result.row = {"id": "id1", "metadata": {"name": "vector1"}}
    mochow_instance._table.query.return_value = mock_result

    result = mochow_instance.get(vector_id="id1")

    mochow_instance._table.query.assert_called_once_with(primary_key={"id": "id1"}, projections=["id", "metadata"])

    assert result.id == "id1"
    assert result.score is None
    assert result.payload == {"name": "vector1"}


def test_list(mochow_instance, mock_mochow_client):
    # Mock select result
    mock_result = Mock()
    mock_result.rows = [{"id": "id1", "metadata": {"name": "vector1"}}, {"id": "id2", "metadata": {"name": "vector2"}}]
    mochow_instance._table.select.return_value = mock_result

    results = mochow_instance.list(limit=2)

    mochow_instance._table.select.assert_called_once_with(filter=None, projections=["id", "metadata"], limit=2)

    assert len(results[0]) == 2
    assert results[0][0].id == "id1"
    assert results[0][1].id == "id2"


def test_list_cols(mochow_instance, mock_mochow_client):
    # Mock table list
    mock_tables = [
        Mock(spec=Table, database_name="test_db", table_name="table1"),
        Mock(spec=Table, database_name="test_db", table_name="table2"),
    ]
    mochow_instance._database.list_table.return_value = mock_tables

    result = mochow_instance.list_cols()

    assert result == ["table1", "table2"]


def test_delete_col_not_exists(mochow_instance, mock_mochow_client):
    # 使用正确的 ServerErrCode 枚举值
    mochow_instance._database.drop_table.side_effect = ServerError(
        "Table not exists", code=ServerErrCode.TABLE_NOT_EXIST
    )

    # Should not raise exception
    mochow_instance.delete_col()


def test_col_info(mochow_instance, mock_mochow_client):
    mock_table_info = {"table_name": "test_table", "fields": []}
    mochow_instance._table.stats.return_value = mock_table_info

    result = mochow_instance.col_info()

    assert result == mock_table_info
