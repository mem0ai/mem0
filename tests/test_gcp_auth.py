import json

from mem0.utils.gcp_auth import GCPAuthenticator


def test_get_credentials_reads_service_account_json_as_utf8(monkeypatch, tmp_path):
    credentials_path = tmp_path / "service-account.json"
    credentials_path.write_text(
        json.dumps({"project_id": "proyecto-niño"}),
        encoding="utf-8",
    )

    class Credentials:
        @staticmethod
        def from_service_account_file(path, scopes=None):
            return {"path": path, "scopes": scopes}

    monkeypatch.setattr(
        "mem0.utils.gcp_auth.service_account.Credentials",
        Credentials,
    )

    credentials, project_id = GCPAuthenticator.get_credentials(
        credentials_path=str(credentials_path),
        scopes=["scope"],
    )

    assert credentials == {"path": str(credentials_path), "scopes": ["scope"]}
    assert project_id == "proyecto-niño"


def test_get_credentials_reads_env_service_account_json_as_utf8(
    monkeypatch,
    tmp_path,
):
    credentials_path = tmp_path / "env-service-account.json"
    credentials_path.write_text(
        json.dumps({"project_id": "proyecto-niño"}),
        encoding="utf-8",
    )

    class Credentials:
        @staticmethod
        def from_service_account_file(path, scopes=None):
            return {"path": path, "scopes": scopes}

    monkeypatch.setattr(
        "mem0.utils.gcp_auth.service_account.Credentials",
        Credentials,
    )
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(credentials_path))

    credentials, project_id = GCPAuthenticator.get_credentials(scopes=["scope"])

    assert credentials == {"path": str(credentials_path), "scopes": ["scope"]}
    assert project_id == "proyecto-niño"
