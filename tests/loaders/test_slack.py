import pytest

from embedchain.loaders.slack import SlackLoader


@pytest.fixture
def slack_loader(mocker, monkeypatch):
    # Mocking necessary dependencies
    mocker.patch("slack_sdk.WebClient")
    mocker.patch("ssl.create_default_context")
    mocker.patch("certifi.where")

    monkeypatch.setenv("SLACK_USER_TOKEN", "slack_user_token")

    return SlackLoader()


def test_slack_loader_initialization(slack_loader):
    assert slack_loader.client is not None
    assert slack_loader.config == {"base_url": "https://www.slack.com/api/"}


def test_slack_loader_setup_loader(slack_loader):
    slack_loader._setup_loader({"base_url": "https://custom.slack.api/"})

    assert slack_loader.client is not None


def test_slack_loader_check_query(slack_loader):
    valid_json_query = "test_query"
    invalid_query = 123

    slack_loader._check_query(valid_json_query)

    with pytest.raises(ValueError):
        slack_loader._check_query(invalid_query)


def test_slack_loader_load_data(slack_loader, mocker):
    valid_json_query = "in:random"

    mocker.patch.object(slack_loader.client, "search_messages", return_value={"messages": {}})

    result = slack_loader.load_data(valid_json_query)

    assert "doc_id" in result
    assert "data" in result
