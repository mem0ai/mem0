"""Regression tests for routes deliberately left untouched by the authz fix.

These prove the per-route changes did not accidentally regress memory CRUD,
search, or the API-key management endpoints."""

from __future__ import annotations


def test_post_memories_admin_succeeds(client, auth_admin_header):
    response = client.post(
        "/memories",
        headers=auth_admin_header,
        json={
            "messages": [{"role": "user", "content": "I love pizza."}],
            "user_id": "alice",
        },
    )
    assert response.status_code == 200


def test_post_memories_requires_identifier(client, auth_admin_header):
    response = client.post(
        "/memories",
        headers=auth_admin_header,
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert response.status_code == 400


def test_get_memories_filtered_admin_succeeds(client, auth_admin_header):
    response = client.get("/memories?user_id=alice", headers=auth_admin_header)
    assert response.status_code == 200


def test_post_search_admin_succeeds(client, auth_admin_header):
    response = client.post(
        "/search",
        headers=auth_admin_header,
        json={"query": "pizza", "user_id": "alice"},
    )
    assert response.status_code == 200


def test_get_memory_by_id_admin_succeeds(client, auth_admin_header):
    response = client.get("/memories/some-id", headers=auth_admin_header)
    assert response.status_code == 200


def test_delete_memories_filtered_admin_succeeds(client, auth_admin_header):
    response = client.delete("/memories?user_id=alice", headers=auth_admin_header)
    assert response.status_code == 200


def test_delete_memories_no_filter_returns_400(client, auth_admin_header):
    """Even admin must supply an identifier for filtered delete."""
    response = client.delete("/memories", headers=auth_admin_header)
    assert response.status_code == 400


def test_get_configure_providers_admin_succeeds(client, auth_admin_header):
    """GET /configure/providers stays on verify_auth (not admin-gated)."""
    response = client.get("/configure/providers", headers=auth_admin_header)
    assert response.status_code == 200


def test_get_configure_providers_member_succeeds(client, auth_member_header):
    """Members can still query bundled providers — not admin-gated."""
    response = client.get("/configure/providers", headers=auth_member_header)
    assert response.status_code == 200


def test_api_keys_list_admin_succeeds(client, auth_admin_header):
    response = client.get("/api-keys", headers=auth_admin_header)
    assert response.status_code == 200


def test_api_keys_list_member_succeeds(client, auth_member_header):
    """API-key management remains scoped to the caller (require_auth, not require_admin)."""
    response = client.get("/api-keys", headers=auth_member_header)
    assert response.status_code == 200


def test_auth_me_admin_succeeds(client, auth_admin_header):
    response = client.get("/auth/me", headers=auth_admin_header)
    assert response.status_code == 200


def test_setup_status_no_auth(client):
    """Open route — no auth required even after the fix."""
    response = client.get("/auth/setup-status")
    assert response.status_code == 200
