import os

import pytest

from embedchain import App
from embedchain.config import AddConfig, AppConfig, ChunkerConfig
from embedchain.models.data_type import DataType

os.environ["OPENAI_API_KEY"] = "test_key"


@pytest.fixture
def app(mocker):
    mocker.patch("chromadb.api.models.Collection.Collection.add")
    return App(config=AppConfig(collect_metrics=False))


def test_add(app):
    app.add("https://example.com", metadata={"foo": "bar"})
    assert app.user_asks == [["https://example.com", "web_page", {"foo": "bar"}]]


# TODO: Make this test faster by generating a sitemap locally rather than using a remote one
# def test_add_sitemap(app):
#     app.add("https://www.google.com/sitemap.xml", metadata={"foo": "bar"})
#     assert app.user_asks == [["https://www.google.com/sitemap.xml", "sitemap", {"foo": "bar"}]]


def test_add_forced_type(app):
    data_type = "text"
    app.add("https://example.com", data_type=data_type, metadata={"foo": "bar"})
    assert app.user_asks == [["https://example.com", data_type, {"foo": "bar"}]]


def test_dry_run(app):
    chunker_config = ChunkerConfig(chunk_size=1, chunk_overlap=0, min_chunk_size=0)
    text = """0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"""

    result = app.add(source=text, config=AddConfig(chunker=chunker_config), dry_run=True)

    chunks = result["chunks"]
    metadata = result["metadata"]
    count = result["count"]
    data_type = result["type"]

    assert len(chunks) == len(text)
    assert count == len(text)
    assert data_type == DataType.TEXT
    for item in metadata:
        assert isinstance(item, dict)
        assert "local" in item["url"]
        assert "text" in item["data_type"]
