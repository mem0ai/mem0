"""Integration tests for admin-gated routes.

Covers, for each affected route, the regression matrix:
- admin JWT       -> success
- ADMIN_API_KEY   -> success (no DB user required)
- AUTH_DISABLED   -> success
- member JWT      -> 403
- no auth         -> 401
"""

from __future__ import annotations


# --- GET /configure ---


def test_get_configure_admin_jwt(client, auth_admin_header):
    response = client.get("/configure", headers=auth_admin_header)
    assert response.status_code == 200


def test_get_configure_admin_api_key(client, admin_api_key_env):
    response = client.get("/configure", headers=admin_api_key_env)
    assert response.status_code == 200


def test_get_configure_auth_disabled(client, auth_disabled_env):
    response = client.get("/configure")
    assert response.status_code == 200


def test_get_configure_member_forbidden(client, auth_member_header):
    response = client.get("/configure", headers=auth_member_header)
    assert response.status_code == 403


def test_get_configure_no_auth_unauthorized(client):
    response = client.get("/configure")
    assert response.status_code == 401


# --- POST /configure ---


def _valid_config():
    return {
        "vector_store": {"provider": "pgvector", "config": {"host": "h"}},
        "llm": {"provider": "openai", "config": {"api_key": "x", "model": "m"}},
        "embedder": {"provider": "openai", "config": {"api_key": "x", "model": "e"}},
    }


def test_post_configure_admin_jwt(client, auth_admin_header):
    response = client.post("/configure", headers=auth_admin_header, json=_valid_config())
    assert response.status_code == 200


def test_post_configure_admin_api_key(client, admin_api_key_env):
    response = client.post("/configure", headers=admin_api_key_env, json=_valid_config())
    assert response.status_code == 200


def test_post_configure_auth_disabled(client, auth_disabled_env):
    response = client.post("/configure", json=_valid_config())
    assert response.status_code == 200


def test_post_configure_member_forbidden(client, auth_member_header):
    response = client.post("/configure", headers=auth_member_header, json=_valid_config())
    assert response.status_code == 403


def test_post_configure_no_auth_unauthorized(client):
    response = client.post("/configure", json=_valid_config())
    assert response.status_code == 401
