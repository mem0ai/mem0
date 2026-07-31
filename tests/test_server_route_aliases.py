"""Production-composed proof for the Python-client compatibility routes."""

import importlib
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from mem0.client.main import AsyncMemoryClient, MemoryClient


@pytest.fixture
def _mock_memory():
    server_path = os.path.join(os.path.dirname(__file__), "..", "server")
    if server_path not in sys.path:
        sys.path.insert(0, server_path)

    memory = MagicMock()
    memory.add.return_value = {"results": [{"id": "mem-1", "event": "ADD", "memory": "stored"}]}
    memory.get_all.return_value = {"results": [{"id": "mem-1", "memory": "stored"}]}
    memory.search.return_value = {"results": [{"id": "mem-1", "memory": "stored", "score": 0.9}]}
    memory.get.return_value = {"id": "mem-1", "memory": "stored"}
    memory.update.return_value = {"message": "Memory updated"}
    memory.history.return_value = [{"id": "mem-1", "event": "ADD"}]
    memory.delete.return_value = {"message": "Memory deleted successfully!"}
    memory.delete_all.return_value = {"message": "All relevant memories deleted"}
    memory.vector_store.list.return_value = [
        SimpleNamespace(
            id="mem-1",
            payload={"user_id": "u1", "created_at": "2026-01-01T00:00:00+00:00"},
        )
    ]

    with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key", "ADMIN_API_KEY": "", "AUTH_DISABLED": "true"}):
        with patch("mem0.Memory.from_config", return_value=memory):
            yield memory


@pytest.fixture
def client(_mock_memory):
    import auth as auth_module
    import server.main as server_module

    with patch.dict(os.environ, {"ADMIN_API_KEY": "", "AUTH_DISABLED": "true"}):
        importlib.reload(auth_module)
        importlib.reload(server_module)
    db = MagicMock()
    db.scalar.return_value = None
    session = MagicMock()
    session.__enter__.return_value = db
    session.__exit__.return_value = None
    with (
        patch.object(auth_module, "SessionLocal", return_value=session) as session_factory,
        patch.object(server_module, "SessionLocal", return_value=MagicMock()),
    ):
        test_client = TestClient(server_module.app)
        test_client.auth_session = session_factory
        yield test_client


@pytest.fixture
def auth_client(_mock_memory):
    import auth as auth_module
    import server.main as server_module

    with patch.dict(
        os.environ,
        {
            "ADMIN_API_KEY": "test-admin-key-for-token-auth",
            "AUTH_DISABLED": "false",
            "JWT_SECRET": "test-jwt-secret-for-token-auth-tests",
        },
    ):
        importlib.reload(auth_module)
        importlib.reload(server_module)

    db = MagicMock()
    session = MagicMock()
    session.__enter__.return_value = db
    session.__exit__.return_value = None
    with (
        patch.object(auth_module, "SessionLocal", return_value=session) as session_factory,
        patch.object(server_module, "SessionLocal", return_value=db),
    ):
        yield TestClient(server_module.app), auth_module, session, session_factory


def _sdk(client):
    with patch("mem0.client.main.Project"):
        return MemoryClient(api_key="test-client-key", host="http://localhost:8000", client=client)


def test_custom_host_reproduction_and_real_add(client, _mock_memory):
    sdk = _sdk(client)

    result = sdk.add(
        [{"role": "user", "content": "Store this"}],
        filters={"user_id": "u1"},
        metadata={"source": "test"},
        infer=False,
        custom_instructions="Extract preferences only.",
    )

    assert result["results"][0]["id"] == "mem-1"
    kwargs = _mock_memory.add.call_args.kwargs
    assert kwargs["user_id"] == "u1"
    assert kwargs["metadata"] == {"source": "test"}
    assert kwargs["infer"] is False
    assert kwargs["prompt"] == "Extract preferences only."
    assert "filters" not in kwargs


def test_real_client_get_all_preserves_nested_filters_and_false_zero(client, _mock_memory):
    sdk = _sdk(client)

    sdk.get_all(filters={"user_id": "u1"}, top_k=0, show_expired=False)

    kwargs = _mock_memory.get_all.call_args.kwargs
    assert kwargs == {"filters": {"user_id": "u1"}, "top_k": 0, "show_expired": False}
    _mock_memory.add.assert_not_called()


def test_real_client_get_all_without_filters_lists_all(client, _mock_memory):
    sdk = _sdk(client)

    result = sdk.get_all()

    assert result["results"][0]["id"] == "mem-1"
    _mock_memory.vector_store.list.assert_called_once()


def test_real_client_search_without_filters_forwards_query(client, _mock_memory):
    sdk = _sdk(client)

    sdk.search("food")

    assert _mock_memory.search.call_args.kwargs == {"query": "food", "filters": {}}


def test_real_client_search_preserves_supported_options(client, _mock_memory):
    sdk = _sdk(client)

    sdk.search(
        "food",
        filters={"user_id": "u1", "category": "food"},
        top_k=0,
        threshold=0,
        rerank=False,
        show_expired=False,
    )

    args, kwargs = _mock_memory.search.call_args
    assert args == ()
    assert kwargs == {
        "query": "food",
        "filters": {"user_id": "u1", "category": "food"},
        "top_k": 0,
        "threshold": 0,
        "rerank": False,
        "show_expired": False,
    }


def test_real_client_update_delete_and_encoded_id(client, _mock_memory):
    sdk = _sdk(client)

    sdk.update("mem/1", text="updated", metadata={"source": "test"}, expiration_date=None)
    sdk.delete("mem/1", delete_linked=False)

    assert _mock_memory.update.call_args.kwargs == {
        "memory_id": "mem/1",
        "data": "updated",
        "metadata": {"source": "test"},
        "expiration_date": None,
    }
    assert _mock_memory.delete.call_args.kwargs == {"memory_id": "mem/1"}


def test_real_client_get_and_history_use_decoded_memory_id(client, _mock_memory):
    sdk = _sdk(client)

    sdk.get("mem/1")
    sdk.history("mem/1")

    assert _mock_memory.get.call_args.args == ("mem/1",)
    assert _mock_memory.history.call_args.kwargs == {"memory_id": "mem/1"}


def test_real_client_delete_all_decodes_serialized_filters(client, _mock_memory):
    sdk = _sdk(client)

    sdk.delete_all(filters={"user_id": "u1"})

    assert _mock_memory.delete_all.call_args.kwargs == {"user_id": "u1"}


def test_real_client_users_and_no_id_delete_users(client, _mock_memory):
    sdk = _sdk(client)

    users = sdk.users()
    assert users == {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": "u1",
                "type": "user",
                "total_memories": 1,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
                "name": "u1",
            }
        ],
    }
    sdk.delete_users()
    assert _mock_memory.delete_all.call_args.kwargs == {"user_id": "u1"}


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/v3/memories/add/", {"messages": [{"role": "user", "content": "x"}], "filters": {"app_id": "a"}}),
        ("/v3/memories/add/", {"messages": [{"role": "user", "content": "x"}], "custom_categories": []}),
        ("/v3/memories/add/", {"messages": [{"role": "user", "content": "x"}], "structured_data_schema": {}}),
        ("/v3/memories/add/", {"messages": [{"role": "user", "content": "x"}], "timestamp": 1}),
        ("/v3/memories/search/", {"query": "x", "filters": {"user_id": "u1"}, "metadata": {"x": 1}}),
        ("/v3/memories/search/", {"query": "x", "filters": {"user_id": "u1"}, "fields": []}),
        ("/v3/memories/search/", {"query": "x", "filters": {"user_id": "u1"}, "categories": []}),
        ("/v3/memories/search/", {"query": "x", "filters": {"user_id": "u1"}, "unknown": 1}),
        ("/v3/memories/", {"messages": [{"role": "user", "content": "x"}]}),
        ("/v3/memories/", {"filters": {"user_id": "u1"}, "page": 1}),
        ("/v3/memories/", {"filters": {"user_id": "u1"}, "start_date": "2026-01-01"}),
        ("/v3/memories/", {"filters": {"user_id": "u1"}, "categories": []}),
        ("/v3/memories/", {"filters": {"user_id": "u1"}, "unknown": 1}),
    ],
)
def test_unsupported_versioned_fields_return_422_before_side_effects(client, _mock_memory, path, payload):
    before = (_mock_memory.add.call_count, _mock_memory.search.call_count, _mock_memory.get_all.call_count)

    response = client.post(path, json=payload)

    assert response.status_code == 422
    assert (_mock_memory.add.call_count, _mock_memory.search.call_count, _mock_memory.get_all.call_count) == before


@pytest.mark.parametrize("payload", [{"timestamp": 1}, {"delete_linked": True}])
def test_update_and_delete_unsupported_values_are_rejected(client, _mock_memory, payload):
    if "timestamp" in payload:
        response = client.put("/v1/memories/mem-1/", json=payload)
        assert response.status_code == 422
        _mock_memory.update.assert_not_called()
    else:
        response = client.delete("/v1/memories/mem-1/", params=payload)
        assert response.status_code == 422
        _mock_memory.delete.assert_not_called()


def test_update_empty_body_is_rejected_before_mutation(client, _mock_memory):
    response = client.put("/v1/memories/mem-1/", json={})

    assert response.status_code == 422
    _mock_memory.update.assert_not_called()


@pytest.mark.parametrize(
    "params",
    [
        {"filters": "[]"},
        {"filters": "not-a-mapping"},
        {"filters": '{"app_id": "a"}'},
        {"filters": '{"user_id": ""}'},
        {"filters": '{"user_id": "u1", "agent_id": "a1"}', "user_id": "u2"},
        {"app_id": "a"},
    ],
)
def test_delete_all_invalid_filters_are_rejected(client, _mock_memory, params):
    response = client.delete("/v1/memories/", params=params)

    assert response.status_code == 422
    _mock_memory.delete_all.assert_not_called()


def test_delete_all_filter_length_boundary(client, _mock_memory):
    prefix = "{'user_id': '"
    suffix = "'}"
    valid = prefix + "u" * (8192 - len(prefix) - len(suffix)) + suffix
    response = client.delete("/v1/memories/", params={"filters": valid})
    assert response.status_code == 200
    assert _mock_memory.delete_all.call_args.kwargs["user_id"] == "u" * (8192 - len(prefix) - len(suffix))

    _mock_memory.delete_all.reset_mock()
    response = client.delete("/v1/memories/", params={"filters": valid + " "})
    assert response.status_code == 422
    _mock_memory.delete_all.assert_not_called()


def test_entity_app_deletion_is_rejected_before_mutation(client, _mock_memory):
    response = client.delete("/v2/entities/app/app-1/")

    assert response.status_code == 422
    _mock_memory.delete_all.assert_not_called()


def test_versioned_routes_are_hidden_and_unversioned_routes_remain(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "/memories" in paths
    assert "/search" in paths
    assert "/entities" in paths
    assert "/v1/ping/" not in paths
    assert "/v3/memories/" not in paths
    assert "/v3/memories/add/" not in paths
    assert "/v3/memories/search/" not in paths
    assert "/v1/memories/" not in paths
    assert "/v1/memories/{memory_id}/" not in paths
    assert "/v1/reset/" not in paths
    assert "/v1/entities/" not in paths
    assert "/v2/entities/{entity_type}/{entity_id}/" not in paths


def test_async_serializer_preserves_mirrored_request_values():
    client = object.__new__(AsyncMemoryClient)

    assert client._prepare_payload(
        [{"role": "user", "content": "x"}], {"filters": {"user_id": "u1"}, "infer": False}
    ) == {"messages": [{"role": "user", "content": "x"}], "filters": {"user_id": "u1"}, "infer": False}
    assert client._prepare_params({"filters": {"user_id": "u1"}}) == {"filters": {"user_id": "u1"}}


def test_token_admin_and_empty_token_precedence(auth_client):
    client, _auth_module, session, session_factory = auth_client

    response = client.get("/v1/ping/", headers={"Authorization": "Token test-admin-key-for-token-auth"})
    assert response.status_code == 200
    session_factory.assert_not_called()

    response = client.get("/v1/ping/", headers={"Authorization": "Token "})
    assert response.status_code == 401
    session_factory.assert_not_called()


def test_invalid_token_and_missing_auth_are_rejected(auth_client):
    client, _auth_module, session, session_factory = auth_client

    response = client.get("/v1/ping/", headers={"Authorization": "Token wrong-key"})
    assert response.status_code == 401
    assert session.__exit__.called

    session.reset_mock()
    session_factory.reset_mock()
    response = client.get("/v1/ping/")
    assert response.status_code == 401
    session_factory.assert_not_called()


def test_valid_non_admin_token_uses_real_key_resolution(auth_client):
    client, auth_module, session, session_factory = auth_client
    db = session.__enter__.return_value
    candidate = SimpleNamespace(key_hash="stored-hash", created_by="user-id")
    db.execute.return_value.scalars.return_value.all.return_value = [candidate]
    db.get.return_value = SimpleNamespace(role="user")

    with patch.object(auth_module, "verify_api_key_hash", return_value=True) as verify_hash:
        response = client.get("/v1/ping/", headers={"Authorization": "Token valid-user-key"})

    assert response.status_code == 200
    verify_hash.assert_called_once_with("valid-user-key", "stored-hash")
    session_factory.assert_called_once_with()
    session.__exit__.assert_called_once_with(None, None, None)


def test_bearer_and_x_api_key_schemes_remain_supported(auth_client):
    client, auth_module, session, session_factory = auth_client

    response = client.get("/v1/ping/", headers={"X-API-Key": "test-admin-key-for-token-auth"})
    assert response.status_code == 200
    session_factory.assert_not_called()

    session.reset_mock()
    session_factory.reset_mock()
    session.__enter__.return_value.get.return_value = SimpleNamespace(role="user")
    token = auth_module.create_access_token("user-id", "user")
    response = client.get("/v1/ping/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    session_factory.assert_called_once_with()
    session.__exit__.assert_called_once_with(None, None, None)


def test_disabled_auth_ignores_token_without_opening_session(client):
    response = client.get("/v1/ping/", headers={"Authorization": "Token any-dummy-key"})

    assert response.status_code == 200
    client.auth_session.assert_not_called()


def test_valid_non_admin_token_closes_session_before_handler(auth_client):
    client, auth_module, session, session_factory = auth_client
    with patch.object(auth_module, "_resolve_user_from_api_key", return_value=SimpleNamespace(role="user")):
        response = client.get("/v1/ping/", headers={"Authorization": "Token valid-user-key"})

    assert response.status_code == 200
    session_factory.assert_called_once_with()
    session.__enter__.assert_called_once_with()
    session.__exit__.assert_called_once_with(None, None, None)


def test_auth_schemes_keep_precedence(auth_client):
    client, _auth_module, session, session_factory = auth_client
    response = client.get(
        "/v1/ping/",
        headers={"Authorization": "Token wrong-key", "X-API-Key": "test-admin-key-for-token-auth"},
    )
    assert response.status_code == 200
    session_factory.assert_not_called()
