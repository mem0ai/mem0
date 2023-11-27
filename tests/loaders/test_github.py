import hashlib

import pytest
import requests

from embedchain.loaders.github import GithubLoader


def test_github_loader_init():
    config = {"base_url": "https://api.github.com", "username": "your_username", "token": "your_token"}
    loader = GithubLoader(config)
    assert loader.config == config
    assert loader.base_url == "https://api.github.com"
    assert loader.headers == {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": "Basic your_username:your_token",
    }


def test_github_loader_parse_github_query():
    loader = GithubLoader()
    url = "https://github.com/owner/repo"
    parsed_query = loader._parse_github_query(url)
    assert parsed_query == "owner/repo"

    url = "https://github.com/owner"
    with pytest.raises(ValueError):
        parsed_query = loader._parse_github_query(url)


def test_github_loader_get_repo_file_paths(monkeypatch):
    class MockRepo:
        @staticmethod
        def clone_from(repo_url, local_path):
            return MockRepo()

        @property
        def remotes(self):
            return MockRemote()

        @property
        def head(self):
            return MockHead()

    class MockRemote:
        def fetch(self):
            pass

    class MockHead:
        @property
        def commit(self):
            return MockCommit()

    class MockTree:
        type = ""
        path = ""

        def __init__(self, type, path):
            self.type = type
            self.path = path

    class MockCommit:
        @property
        def tree(self):
            return [
                MockTree(type="blob", path="dir1/file1.txt"),
            ]

    # Apply the monkeypatch to replace the Repo class with the MockRepo class
    monkeypatch.setattr("git.Repo", MockRepo)

    loader = GithubLoader()
    repo_url = "https://github.com/owner/repo"
    file_paths = loader._get_repo_file_paths(repo_url)

    repo_hash = hashlib.sha256(repo_url.encode()).hexdigest()
    assert isinstance(file_paths, list)
    assert file_paths == [
        f"/tmp/{repo_hash}/repo/dir1/file1.txt",
    ]


def test_github_loader_get_github_actions():
    loader = GithubLoader()
    urls = ["https://github.com/owner/repo/pulls", "https://github.com/owner/repo/issues/1"]
    actions = loader._get_github_actions(urls)

    assert isinstance(actions, dict)
    assert len(actions) == 2

    assert actions["https://github.com/owner/repo/pulls"] == [
        ("pulls", "https://api.github.com/repos/owner/repo/pulls"),
    ]

    assert actions["https://github.com/owner/repo/issues/1"] == [
        ("issues", "https://api.github.com/repos/owner/repo/issues/1")
    ]


def test_github_loader_get_github_repo_data(monkeypatch):
    loader = GithubLoader()
    path = "/tmp/test.txt"

    # Test case 1: File exists
    with open(path, "w+") as f:
        f.write("Test content")
    result = loader._get_github_repo_data(path)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "content" in result[0]
    assert "meta_data" in result[0]
    assert result[0]["content"] == "Test content"


def test_github_loader_get_github_api_data(monkeypatch):
    loader = GithubLoader()
    url = "https://api.github.com/repos/owner/repo/issues/1"

    # Mock the requests.get method
    def mock_get(url, headers):
        class MockResponse:
            def __init__(self, json_data, status_code):
                self.json_data = json_data
                self.status_code = status_code

            def json(self):
                return self.json_data

            def raise_for_status(self):
                pass

        return MockResponse(
            [
                {
                    "title": "Test Issue",
                    "body": "This is a test issue",
                }
            ],
            200,
        )

    monkeypatch.setattr(requests, "get", mock_get)

    # Test the method
    result = loader._get_github_api_data(url)

    assert isinstance(result, list)
    assert len(result) == 1
    assert "content" in result[0]
    assert "meta_data" in result[0]
    assert result[0]["content"] == "Title: Test Issue Description: This is a test issue"
    assert result[0]["meta_data"] == {"url": url}


def test_github_loader_get_github_data(monkeypatch):
    loader = GithubLoader()
    action = ("repo", "https://github.com/owner/repo")

    # Mock the _get_github_repo_data method
    def mock_get_github_repo_data(url):
        return [{"content": "Test content", "meta_data": {"url": url}}]

    # Mock the _get_github_api_data method
    def mock_get_github_api_data(url):
        return [{"content": "Test content", "meta_data": {"url": url}}]

    monkeypatch.setattr(loader, "_get_github_repo_data", mock_get_github_repo_data)
    monkeypatch.setattr(loader, "_get_github_api_data", mock_get_github_api_data)

    # Test case 1: Action type is "repo"
    result = loader._get_github_data(action)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "content" in result[0]
    assert "meta_data" in result[0]
    assert result[0]["content"] == "Test content"
    assert result[0]["meta_data"]["url"] == "https://github.com/owner/repo"

    # Test case 2: Action type is "pulls"
    action = ("pulls", "https://github.com/owner/repo/pulls")
    result = loader._get_github_data(action)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "content" in result[0]
    assert "meta_data" in result[0]
    assert result[0]["content"] == "Test content"
    assert result[0]["meta_data"]["url"] == "https://github.com/owner/repo/pulls"

    # Test case 3: Action type is "issues"
    action = ("issues", "https://github.com/owner/repo/issues")
    result = loader._get_github_data(action)
    assert isinstance(result, list)
    assert len(result) == 1
    assert "content" in result[0]
    assert "meta_data" in result[0]
    assert result[0]["content"] == "Test content"
    assert result[0]["meta_data"]["url"] == "https://github.com/owner/repo/issues"

    # Test case 4: Invalid action type
    action = ("invalid", "https://github.com/owner/repo")
    with pytest.raises(ValueError):
        loader._get_github_data(action)


def test_github_loader_load_data(monkeypatch):
    loader = GithubLoader()
    urls = ["https://github.com/owner/repo1", "https://github.com/owner/repo2"]

    # Mock the _get_github_actions method
    def mock_get_github_actions(urls):
        return {"https://github.com/owner/repo1": ["repo"], "https://github.com/owner/repo2": ["pulls", "issues"]}

    # Mock the _get_github_data method
    def mock_get_github_data(action):
        if action == "repo":
            return [{"content": "Test content 1", "meta_data": {"url": "https://github.com/owner/repo1"}}]
        elif action == "pulls":
            return [{"content": "Test content 2", "meta_data": {"url": "https://github.com/owner/repo2/pulls"}}]
        elif action == "issues":
            return [{"content": "Test content 3", "meta_data": {"url": "https://github.com/owner/repo2/issues"}}]

    monkeypatch.setattr(loader, "_get_github_actions", mock_get_github_actions)
    monkeypatch.setattr(loader, "_get_github_data", mock_get_github_data)

    result = loader.load_data(urls)

    expected_doc_id = hashlib.sha256(
        (
            str(urls)
            + ", ".join(
                [
                    "https://github.com/owner/repo1",
                    "https://github.com/owner/repo2/pulls",
                    "https://github.com/owner/repo2/issues",
                ]
            )
        ).encode()
    ).hexdigest()

    assert isinstance(result, dict)
    assert "doc_id" in result
    assert "data" in result
    assert len(result["data"]) == 3
    assert result["doc_id"] == expected_doc_id
