import json
from unittest.mock import Mock, patch

import pytest

pytest.importorskip("google.auth")

from mem0.utils.gcp_auth import GCPAuthenticator

# A project_id with non-ASCII characters; the file must be read as UTF-8 for it to survive.
NON_ASCII_PROJECT_ID = "proyecto-niño"


@pytest.fixture
def credentials_file(tmp_path):
    """Write a UTF-8 encoded service account JSON with a non-ASCII project_id."""
    path = tmp_path / "service_account.json"
    payload = {
        "type": "service_account",
        "project_id": NON_ASCII_PROJECT_ID,
        "client_email": "svc@example.iam.gserviceaccount.com",
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def test_get_credentials_reads_credentials_path_as_utf8(credentials_file):
    with patch(
        "mem0.utils.gcp_auth.service_account.Credentials.from_service_account_file",
        return_value=Mock(),
    ) as mock_loader:
        credentials, project_id = GCPAuthenticator.get_credentials(credentials_path=credentials_file)

    mock_loader.assert_called_once_with(credentials_file, scopes=None)
    assert credentials is mock_loader.return_value
    assert project_id == NON_ASCII_PROJECT_ID


def test_get_credentials_reads_env_credentials_as_utf8(credentials_file, monkeypatch):
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", credentials_file)

    with patch(
        "mem0.utils.gcp_auth.service_account.Credentials.from_service_account_file",
        return_value=Mock(),
    ) as mock_loader:
        credentials, project_id = GCPAuthenticator.get_credentials()

    mock_loader.assert_called_once_with(credentials_file, scopes=None)
    assert credentials is mock_loader.return_value
    assert project_id == NON_ASCII_PROJECT_ID
