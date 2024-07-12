import pytest

from embedchain.loaders.github import GithubLoader


@pytest.fixture
def mock_github_loader_config():
    return {
        "token": "your_mock_token",
    }


@pytest.fixture
def mock_github_loader(mocker, mock_github_loader_config):
    mock_github = mocker.patch("github.Github")
    _ = mock_github.return_value
    return GithubLoader(config=mock_github_loader_config)


def test_github_loader_init(mocker, mock_github_loader_config):
    mock_github = mocker.patch("github.Github")
    GithubLoader(config=mock_github_loader_config)
    mock_github.assert_called_once_with("your_mock_token")


def test_github_loader_init_empty_config(mocker):
    with pytest.raises(ValueError, match="requires a personal access token"):
        GithubLoader()


def test_github_loader_init_missing_token():
    with pytest.raises(ValueError, match="requires a personal access token"):
        GithubLoader(config={})
