from unittest.mock import MagicMock

import psycopg
import pytest

from embedchain.loaders.postgres import PostgresLoader


@pytest.fixture
def postgres_loader(mocker):
    loader = PostgresLoader()
    with mocker.patch.object(psycopg, "connect"):
        yield loader


def test_setup_loader(postgres_loader):
    config = {"url": "postgres://user:password@localhost:5432/database"}
    postgres_loader.setup_loader(config)
    assert postgres_loader.connection is not None
    assert postgres_loader.cursor is not None


def test_setup_loader_invalid_config(postgres_loader):
    with pytest.raises(ValueError, match="Must provide the valid config. Received: None"):
        postgres_loader.setup_loader()


def test_load_data(postgres_loader, monkeypatch):
    mock_cursor = MagicMock()
    monkeypatch.setattr(postgres_loader, "cursor", mock_cursor)

    query = "SELECT * FROM table"
    mock_cursor.fetchall.return_value = [(1, "data1"), (2, "data2")]

    result = postgres_loader.load_data(query)

    assert "doc_id" in result
    assert "data" in result
    assert len(result["data"]) == 2
    assert result["data"][0]["meta_data"]["url"] == f"postgres_query-({query})"
    assert result["data"][1]["meta_data"]["url"] == f"postgres_query-({query})"
    assert mock_cursor.execute.called_with(query)


def test_load_data_no_cursor(postgres_loader):
    with pytest.raises(ValueError, match="PostgreLoader cursor is not initialized. Call setup_loader first."):
        postgres_loader.load_data("SELECT * FROM table")


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
