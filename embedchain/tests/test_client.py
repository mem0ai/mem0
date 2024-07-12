import pytest

from embedchain import Client


class TestClient:
    @pytest.fixture
    def mock_requests_post(self, mocker):
        return mocker.patch("embedchain.client.requests.post")

    def test_valid_api_key(self, mock_requests_post):
        mock_requests_post.return_value.status_code = 200
        client = Client(api_key="valid_api_key")
        assert client.check("valid_api_key") is True

    def test_invalid_api_key(self, mock_requests_post):
        mock_requests_post.return_value.status_code = 401
        with pytest.raises(ValueError):
            Client(api_key="invalid_api_key")

    def test_update_valid_api_key(self, mock_requests_post):
        mock_requests_post.return_value.status_code = 200
        client = Client(api_key="valid_api_key")
        client.update("new_valid_api_key")
        assert client.get() == "new_valid_api_key"

    def test_clear_api_key(self, mock_requests_post):
        mock_requests_post.return_value.status_code = 200
        client = Client(api_key="valid_api_key")
        client.clear()
        assert client.get() is None

    def test_save_api_key(self, mock_requests_post):
        mock_requests_post.return_value.status_code = 200
        api_key_to_save = "valid_api_key"
        client = Client(api_key=api_key_to_save)
        client.save()
        assert client.get() == api_key_to_save

    def test_load_api_key_from_config(self, mocker):
        mocker.patch("embedchain.Client.load_config", return_value={"api_key": "test_api_key"})
        client = Client()
        assert client.get() == "test_api_key"

    def test_load_invalid_api_key_from_config(self, mocker):
        mocker.patch("embedchain.Client.load_config", return_value={})
        with pytest.raises(ValueError):
            Client()

    def test_load_missing_api_key_from_config(self, mocker):
        mocker.patch("embedchain.Client.load_config", return_value={})
        with pytest.raises(ValueError):
            Client()
