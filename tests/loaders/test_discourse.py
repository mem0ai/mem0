import pytest
import requests

from embedchain.loaders.discourse import DiscourseLoader


@pytest.fixture
def discourse_loader_config():
    return {
        "domain": "https://example.com/",
    }


@pytest.fixture
def discourse_loader(discourse_loader_config):
    return DiscourseLoader(config=discourse_loader_config)


def test_discourse_loader_init_with_valid_config():
    config = {"domain": "https://example.com/"}
    loader = DiscourseLoader(config=config)
    assert loader.domain == "https://example.com/"


def test_discourse_loader_init_with_missing_config():
    with pytest.raises(ValueError, match="DiscourseLoader requires a config"):
        DiscourseLoader()


def test_discourse_loader_init_with_missing_domain():
    config = {"another_key": "value"}
    with pytest.raises(ValueError, match="DiscourseLoader requires a domain"):
        DiscourseLoader(config=config)


def test_discourse_loader_check_query_with_valid_query(discourse_loader):
    discourse_loader._check_query("sample query")


def test_discourse_loader_check_query_with_empty_query(discourse_loader):
    with pytest.raises(ValueError, match="DiscourseLoader requires a query"):
        discourse_loader._check_query("")


def test_discourse_loader_check_query_with_invalid_query_type(discourse_loader):
    with pytest.raises(ValueError, match="DiscourseLoader requires a query"):
        discourse_loader._check_query(123)


def test_discourse_loader_load_post_with_valid_post_id(discourse_loader, monkeypatch):
    def mock_get(*args, **kwargs):
        class MockResponse:
            def json(self):
                return {"raw": "Sample post content"}

            def raise_for_status(self):
                pass

        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)

    post_data = discourse_loader._load_post(123)

    assert post_data["content"] == "Sample post content"
    assert "meta_data" in post_data


def test_discourse_loader_load_data_with_valid_query(discourse_loader, monkeypatch):
    def mock_get(*args, **kwargs):
        class MockResponse:
            def json(self):
                return {"grouped_search_result": {"post_ids": [123, 456, 789]}}

            def raise_for_status(self):
                pass

        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)

    def mock_load_post(*args, **kwargs):
        return {
            "content": "Sample post content",
            "meta_data": {
                "url": "https://example.com/posts/123.json",
                "created_at": "2021-01-01",
                "username": "test_user",
                "topic_slug": "test_topic",
                "score": 10,
            },
        }

    monkeypatch.setattr(discourse_loader, "_load_post", mock_load_post)

    data = discourse_loader.load_data("sample query")

    assert len(data["data"]) == 3
    assert data["data"][0]["content"] == "Sample post content"
    assert data["data"][0]["meta_data"]["url"] == "https://example.com/posts/123.json"
    assert data["data"][0]["meta_data"]["created_at"] == "2021-01-01"
    assert data["data"][0]["meta_data"]["username"] == "test_user"
    assert data["data"][0]["meta_data"]["topic_slug"] == "test_topic"
    assert data["data"][0]["meta_data"]["score"] == 10
