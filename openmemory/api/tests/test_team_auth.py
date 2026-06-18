"""Tests for team authentication middleware (task_11 / ADR-006)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.team_auth import TeamAuthMiddleware, load_team_tokens

TOKENS = {"tok-alpha": "alpha", "tok-beta": "beta"}


def _app(mode):
    app = FastAPI()
    app.add_middleware(TeamAuthMiddleware, mode=mode, token_to_team=TOKENS)

    @app.get("/x")
    def x():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


def test_enforce_valid_api_key():
    with TestClient(_app("enforce")) as c:
        assert c.get("/x", headers={"x-api-key": "tok-alpha"}).status_code == 200


def test_enforce_valid_bearer():
    with TestClient(_app("enforce")) as c:
        assert c.get("/x", headers={"authorization": "Bearer tok-beta"}).status_code == 200


def test_enforce_missing_token_401():
    with TestClient(_app("enforce")) as c:
        assert c.get("/x").status_code == 401


def test_enforce_invalid_token_401():
    with TestClient(_app("enforce")) as c:
        assert c.get("/x", headers={"x-api-key": "nope"}).status_code == 401


def test_warn_missing_token_passes():
    with TestClient(_app("warn")) as c:
        assert c.get("/x").status_code == 200


def test_off_mode_passes():
    with TestClient(_app("off")) as c:
        assert c.get("/x").status_code == 200


def test_enforce_skips_health():
    with TestClient(_app("enforce")) as c:
        assert c.get("/health").status_code == 200


# -- token loader ----------------------------------------------------------

def test_load_tokens_from_inline_env(monkeypatch):
    monkeypatch.delenv("AUTH_TOKENS_FILE", raising=False)
    monkeypatch.setenv("AUTH_TOKENS", "alpha:tok1, beta:tok2")
    tokens = load_team_tokens()
    assert tokens == {"tok1": "alpha", "tok2": "beta"}


def test_load_tokens_from_json_file(tmp_path, monkeypatch):
    f = tmp_path / "tokens.json"
    f.write_text('{"alpha": "tokA", "beta": "tokB"}', encoding="utf-8")
    monkeypatch.setenv("AUTH_TOKENS_FILE", str(f))
    tokens = load_team_tokens()
    assert tokens == {"tokA": "alpha", "tokB": "beta"}
