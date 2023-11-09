import hashlib
from unittest.mock import MagicMock

import pytest

from embedchain.loaders.mysql import MySQLLoader


@pytest.fixture
def mysql_loader(mocker):
    with mocker.patch("mysql.connector.connection.MySQLConnection"):
        config = {
            "host": "localhost",
            "port": "3306",
            "user": "your_username",
            "password": "your_password",
            "database": "your_database",
        }
        loader = MySQLLoader(config=config)
        yield loader


def test_mysql_loader_initialization(mysql_loader):
    assert mysql_loader.config is not None
    assert mysql_loader.connection is not None
    assert mysql_loader.cursor is not None


def test_mysql_loader_invalid_config():
    with pytest.raises(ValueError, match="Invalid sql config: None"):
        MySQLLoader(config=None)


def test_mysql_loader_setup_loader_successful(mysql_loader):
    assert mysql_loader.connection is not None
    assert mysql_loader.cursor is not None


def test_mysql_loader_setup_loader_connection_error(mysql_loader, mocker):
    mocker.patch("mysql.connector.connection.MySQLConnection", side_effect=IOError("Mocked connection error"))
    with pytest.raises(ValueError, match="Unable to connect with the given config:"):
        mysql_loader._setup_loader(config={})


def test_mysql_loader_check_query_successful(mysql_loader):
    query = "SELECT * FROM table"
    mysql_loader._check_query(query=query)


def test_mysql_loader_check_query_invalid(mysql_loader):
    with pytest.raises(ValueError, match="Invalid mysql query: 123"):
        mysql_loader._check_query(query=123)


def test_mysql_loader_load_data_successful(mysql_loader, mocker):
    mock_cursor = MagicMock()
    mocker.patch.object(mysql_loader, "cursor", mock_cursor)
    mock_cursor.fetchall.return_value = [(1, "data1"), (2, "data2")]

    query = "SELECT * FROM table"
    result = mysql_loader.load_data(query)

    assert "doc_id" in result
    assert "data" in result
    assert len(result["data"]) == 2
    assert result["data"][0]["meta_data"]["url"] == query
    assert result["data"][1]["meta_data"]["url"] == query

    doc_id = hashlib.sha256((query + ", ".join([d["content"] for d in result["data"]])).encode()).hexdigest()

    assert result["doc_id"] == doc_id
    assert mock_cursor.execute.called_with(query)


def test_mysql_loader_load_data_invalid_query(mysql_loader):
    with pytest.raises(ValueError, match="Invalid mysql query: 123"):
        mysql_loader.load_data(query=123)
