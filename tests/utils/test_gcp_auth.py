"""Regression tests for issue #7209: GCP credential JSON must be read as UTF-8.

``GCPAuthenticator.get_credentials()`` re-opens the service account file with
``json.load()`` to extract ``project_id``. Those ``open()`` calls historically
used the platform default encoding, so on hosts whose default encoding is not
UTF-8 (e.g. Windows with a legacy ANSI code page) a non-ASCII ``project_id``
was silently misread, even though Google's own loader had already read the
same file correctly as UTF-8.

Service account JSON files are UTF-8 by spec (RFC 8259; Google documents its
credential files as UTF-8), so the reads must pass ``encoding="utf-8"``.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

gcp_auth = pytest.importorskip("mem0.utils.gcp_auth", reason="google-auth is required for gcp_auth tests")

PROJECT_ID = "proyecto-ni\u00f1o"

# Throwaway RSA key used only to satisfy the credential-file loader; not a secret.
_TEST_PEM = (
    "-----BEGIN RSA PRIVATE KEY-----\n"
    "MIIEpAIBAAKCAQEAovxB4PDbkwHUgq+0ogqBTJ4/iwqtR4W+n2CU4fDwQupvNtUa\n"
    "ArIFTMzB8bujoLhfEkKJIoWzBhaFzPQR1ASkDQ6FRB+Rc9KU6TeXY/BnLBlfnjBL\n"
    "p0rhxKKUt8bj94b6ZLvF2FBOtP7uWxKuoOzb0wEB44sdMF97oLNQTp4onwneIEYT\n"
    "hN0RK6+8ZTqlTIbkDdHDDcsyAdRKcT/zaOEYSVKuRsqASxhBV7O3I42NbEMWb3Yn\n"
    "t4waFWZ2X8CDxj3tV7vuLhvcy9WeNZNa/tQWqM1HTtRZUT4yUoLCLvKebhr+35wj\n"
    "vwCx8AeP+YhOgL7874sH250RB6S1rB2TlV1h0wIDAQABAoIBABEpASCstgRPjC8+\n"
    "+QREmeIrboz2UKc3+t7Z8uL/v17e7bBhay3UeNViC5t8LO62QCBH4XDBO0eipcTI\n"
    "qns0X+IWC3b64ebGybHtDfinmPKeMKCS/NbTfgYk3gakH2Ac6zkhl2OT6lgz19G+\n"
    "m6SgO5wxk3WAh1AOsDwLv81Uk/n74IqhBTSylXycfms9GiESpcdLqBKsJYsdIWup\n"
    "61bPpO6i2utw27moFpyg2xXT5MdbsIXsN2SxlcU+w2UU7gKY2ZO1FCuguejlulj5\n"
    "hNjZR5LmXTX7IVuVqQgPJb/YhkdMRnkUzQ42xuT1T9epWd9x3bAwETTVnyNzon1f\n"
    "0x0p2M0CgYEA5ESLv+fDHCKMupZIvdK4ShV8gnjaSy4uEIriyIxSvNIOnzH4Jo9v\n"
    "okUlYEv4L8BC1fYtKAam5pHLm5ZRrmXsD6CJG1AXaM94zdt77OKC4mDw3Txc0UpU\n"
    "P59fWGh2i+6MmKuxpyS64y46efWWn1RDSxlOqEuYoCJTqzmdHb2XKh0CgYEAtslW\n"
    "BnR6WAAXU1DboVY/jaxfPk50RdzOhB73fkYKLXNnJdTf736770NzFk4aGf9Pu1i9\n"
    "NF1gaEVsUbS/7PvLez4QzQQpHPr8Fv8Ifcvz5JzsKM/T7hnontgodbQSlzz+8Jya\n"
    "guvpmKyb6qbrbOUfr8HaGqIluKCA4ldbdYpSeK8CgYEAimJv4pirtTvQ2zFOyh2c\n"
    "cfVStXp0xI0rigXY9MH1StmB2cseaKoegF6xCQ8lWDWTj0keGRznQ/LxX9KilDrg\n"
    "AJ1PYYqNlpHo58v+9h5gQMOKYmU80/je2G9TCzLRY4XsIIY+PllLH30gIF3dwZwA\n"
    "699cyzSBQ9tro+tar/QHV5UCgYAXZbxKRTyn6RMTSiVjCIxIEUl7y0Uc8D/LL7+U\n"
    "fViuKriIYjBsErfxz5t6vnKe40yMebZ2boF5t3E/IDj1F+IbG33BEIhGumXsd6bZ\n"
    "m3LTz7Z3HutM7ioVsyuyrWM30sn7eMBag+I59dZbehRmswmUUOcfQ6Q6dukoj/AY\n"
    "IqWd5wKBgQDfqt394JsMRoNaTLxIh2+hvB/S5+On1Kjx78q5x9ZtuwUklmihLrRY\n"
    "tg+AG5mi2a6Z4vZXTxnPZ3BuDMlLM4V4crvGqWZZT8wW22GTaL9aic8KKZDmKkye\n"
    "8rhQvXBKbKN3huMIuHWxfX+6HmqgN0idC7PBLRHCoEzYz8xfXvlmEQ==\n"
    "-----END RSA PRIVATE KEY-----\n"
)

_SA_DICT = {
    "type": "service_account",
    "project_id": PROJECT_ID,
    "private_key_id": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
    "private_key": _TEST_PEM,
    "client_email": "sa@proyecto-nino.iam.gserviceaccount.com",
    "client_id": "123456789012345678901",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": "https://certain-url.iam.gserviceaccount.com",
    "universe_domain": "googleapis.com",
}


def _write_service_account_json(tmp_path: Path) -> Path:
    path = tmp_path / "service-account.json"
    # ensure_ascii=False is what makes the file contain real UTF-8 bytes.
    path.write_text(json.dumps(_SA_DICT, ensure_ascii=False), encoding="utf-8")
    return path


def test_get_credentials_reads_non_ascii_project_id_as_utf8(tmp_path):
    path = _write_service_account_json(tmp_path)

    _, project_id = gcp_auth.GCPAuthenticator.get_credentials(credentials_path=str(path))

    assert project_id == PROJECT_ID


def test_get_credentials_env_var_path_reads_non_ascii_project_id_as_utf8(tmp_path, monkeypatch):
    path = _write_service_account_json(tmp_path)
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(path))

    _, project_id = gcp_auth.GCPAuthenticator.get_credentials()

    assert project_id == PROJECT_ID


def test_get_credentials_project_id_read_does_not_depend_on_locale(tmp_path):
    """The project_id re-read must not use the locale default encoding.

    Runs the loader in a subprocess with ``-X warn_default_encoding`` (PEP 597):
    an ``EncodingWarning`` attributed to ``gcp_auth.py`` means the file was
    opened without an explicit encoding, which is the bug in issue #7209.
    """
    path = _write_service_account_json(tmp_path)

    code = "\n".join(
        [
            "import json",
            "from mem0.utils.gcp_auth import GCPAuthenticator",
            "creds, project_id = GCPAuthenticator.get_credentials(credentials_path=%r)" % str(path),
            "print(json.dumps(project_id))",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-X", "warn_default_encoding", "-c", code],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(__file__).resolve().parents[2]),
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == PROJECT_ID
    warnings_from_gcp_auth = [
        line for line in result.stderr.splitlines() if "EncodingWarning" in line and "gcp_auth.py" in line
    ]
    assert warnings_from_gcp_auth == [], (
        "gcp_auth.py opened the credential file without an explicit encoding: " + "\n".join(warnings_from_gcp_auth)
    )
