from unittest.mock import MagicMock

import psycopg
import pytest

from embedchain.loaders.postgres import PostgresLoader


@pytest.fixture
def postgres_loader(mocker):
    with mocker.patch.object(psycopg, "connect"):
        config = {"url": "postgres://user:password@localhost:5432/database"}
        loader = PostgresLoader(config=config)
        yield loader


def test_postgres_loader_initialization(postgres_loader):
    assert postgres_loader.connection is not None
    assert postgres_loader.cursor is not None


def test_postgres_loader_invalid_config():
    with pytest.raises(ValueError, match="Must provide the valid config. Received: None"):
        PostgresLoader(config=None)


def test_load_data(postgres_loader, monkeypatch):
    mock_cursor = MagicMock()
    monkeypatch.setattr(postgres_loader, "cursor", mock_cursor)

    query = "SELECT * FROM table"
    mock_cursor.fetchall.return_value = [(1, "data1"), (2, "data2")]

    result = postgres_loader.load_data(query)

    assert "doc_id" in result
    assert "data" in result
    assert len(result["data"]) == 2
    assert result["data"][0]["meta_data"]["url"] == query
    assert result["data"][1]["meta_data"]["url"] == query
    assert mock_cursor.execute.called_with(query)


def test_load_data_exception(postgres_loader, monkeypatch):
    mock_cursor = MagicMock()
    monkeypatch.setattr(postgres_loader, "cursor", mock_cursor)

    _ = "SELECT * FROM table"
    mock_cursor.execute.side_effect = Exception("Mocked exception")

    with pytest.raises(
        ValueError, match=r"Failed to load data using query=SELECT \* FROM table with: Mocked exception"
    ):
        postgres_loader.load_data("SELECT * FROM table")


def test_close_connection(postgres_loader):
    postgres_loader.close_connection()
    assert postgres_loader.cursor is None
    assert postgres_loader.connection is None
