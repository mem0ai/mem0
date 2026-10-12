"""Tests for entity ID handling in MemoryClient add, delete_all, and delete_users."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mem0.client.main import AsyncMemoryClient, MemoryClient
from mem0.client.types import AddMemoryOptions, DeleteAllMemoryOptions

ENTITY_FIELDS = ["user_id", "agent_id", "app_id", "run_id"]
BLANK_IDS = ["", "   ", "\t\n"]


def _ok_response(body=None):
    response = MagicMock()
    response.json.return_value = body if body is not None else {"message": "ok"}
    response.raise_for_status.return_value = None
    return response


@pytest.fixture
def sync_client():
    client = MemoryClient.__new__(MemoryClient)
    client.client = MagicMock()
    client.client.post.return_value = _ok_response()
    client.client.delete.return_value = _ok_response()
    with patch("mem0.client.main.capture_client_event"):
        yield client


@pytest.fixture
def async_client():
    client = AsyncMemoryClient.__new__(AsyncMemoryClient)
    client.async_client = MagicMock()
    client.async_client.post = AsyncMock(return_value=_ok_response())
    client.async_client.delete = AsyncMock(return_value=_ok_response())
    with patch("mem0.client.main.capture_client_event"):
        yield client


class TestDeleteAllBlankEntityIds:
    @pytest.mark.parametrize("field", ENTITY_FIELDS)
    @pytest.mark.parametrize("blank", BLANK_IDS)
    def test_sync_raises_without_http_call(self, sync_client, field, blank):
        with pytest.raises(ValueError, match=field):
            sync_client.delete_all(**{field: blank})

        sync_client.client.delete.assert_not_called()

    @pytest.mark.parametrize("field", ENTITY_FIELDS)
    @pytest.mark.parametrize("blank", BLANK_IDS)
    def test_async_raises_without_http_call(self, async_client, field, blank):
        with pytest.raises(ValueError, match=field):
            asyncio.run(async_client.delete_all(**{field: blank}))

        async_client.async_client.delete.assert_not_called()

    def test_blank_id_next_to_valid_id_still_raises(self, sync_client):
        with pytest.raises(ValueError, match="agent_id"):
            sync_client.delete_all(user_id="u1", agent_id="")

        sync_client.client.delete.assert_not_called()

    def test_blank_id_in_typed_options_raises(self, sync_client):
        with pytest.raises(ValueError, match="user_id"):
            sync_client.delete_all(DeleteAllMemoryOptions(user_id=" "))

        sync_client.client.delete.assert_not_called()

    def test_error_explains_the_risk_and_the_wildcard(self, sync_client):
        with pytest.raises(ValueError) as exc_info:
            sync_client.delete_all(user_id="")

        message = str(exc_info.value)
        assert "every memory in the project" in message
        assert "'*'" in message


class TestDeleteAllValidInputs:
    def test_sync_sends_entity_id_as_query_param(self, sync_client):
        sync_client.delete_all(user_id="u1")

        sync_client.client.delete.assert_called_once_with("/v1/memories/", params={"user_id": "u1"})

    def test_async_sends_entity_id_as_query_param(self, async_client):
        asyncio.run(async_client.delete_all(user_id="u1"))

        async_client.async_client.delete.assert_called_once_with("/v1/memories/", params={"user_id": "u1"})

    def test_typed_options_send_entity_id_as_query_param(self, sync_client):
        sync_client.delete_all(DeleteAllMemoryOptions(user_id="u1"))

        sync_client.client.delete.assert_called_once_with("/v1/memories/", params={"user_id": "u1"})

    def test_wildcard_is_still_allowed(self, sync_client):
        sync_client.delete_all(user_id="*")

        sync_client.client.delete.assert_called_once_with("/v1/memories/", params={"user_id": "*"})


class TestDeleteAllRejectsFilters:
    def test_sync_raises_without_http_call(self, sync_client):
        with pytest.raises(ValueError, match="filters"):
            sync_client.delete_all(filters={"user_id": "u1"})

        sync_client.client.delete.assert_not_called()

    def test_async_raises_without_http_call(self, async_client):
        with pytest.raises(ValueError, match="filters"):
            asyncio.run(async_client.delete_all(filters={"user_id": "u1"}))

        async_client.async_client.delete.assert_not_called()


class TestDeleteUsersBlankEntityIds:
    @pytest.mark.parametrize("field", ENTITY_FIELDS)
    @pytest.mark.parametrize("blank", BLANK_IDS)
    def test_sync_raises_before_any_request(self, sync_client, field, blank):
        with patch.object(sync_client, "users") as users:
            with pytest.raises(ValueError, match=field):
                sync_client.delete_users(**{field: blank})

        users.assert_not_called()
        sync_client.client.delete.assert_not_called()

    @pytest.mark.parametrize("field", ENTITY_FIELDS)
    @pytest.mark.parametrize("blank", BLANK_IDS)
    def test_async_raises_before_any_request(self, async_client, field, blank):
        with patch.object(async_client, "users", new=AsyncMock()) as users:
            with pytest.raises(ValueError, match=field):
                asyncio.run(async_client.delete_users(**{field: blank}))

        users.assert_not_called()
        async_client.async_client.delete.assert_not_called()


class TestDeleteUsersValidInputs:
    def test_sync_deletes_the_named_entity(self, sync_client):
        sync_client.delete_users(user_id="u1")

        sync_client.client.delete.assert_called_once_with("/v2/entities/user/u1/", params={})

    def test_async_deletes_the_named_entity(self, async_client):
        asyncio.run(async_client.delete_users(user_id="u1"))

        async_client.async_client.delete.assert_called_once_with("/v2/entities/user/u1/", params={})

    def test_no_ids_still_deletes_every_listed_entity(self, sync_client):
        listing = {"results": [{"type": "user", "name": "u1"}, {"type": "agent", "name": "a1"}]}

        with patch.object(sync_client, "users", return_value=listing):
            sync_client.delete_users()

        deleted_paths = [call.args[0] for call in sync_client.client.delete.call_args_list]
        assert deleted_paths == ["/v2/entities/user/u1/", "/v2/entities/agent/a1/"]


class TestAddEntityIds:
    def test_sync_rejects_filters_without_http_call(self, sync_client):
        with pytest.raises(ValueError, match="user_id"):
            sync_client.add("hello", filters={"user_id": "u1"})

        sync_client.client.post.assert_not_called()

    def test_async_rejects_filters_without_http_call(self, async_client):
        with pytest.raises(ValueError, match="user_id"):
            asyncio.run(async_client.add("hello", filters={"user_id": "u1"}))

        async_client.async_client.post.assert_not_called()

    def test_filters_none_is_treated_as_not_provided(self, sync_client):
        sync_client.add("hello", user_id="u1", filters=None)

        payload = sync_client.client.post.call_args.kwargs["json"]
        assert payload["user_id"] == "u1"
        assert "filters" not in payload

    def test_sync_typed_options_put_entity_ids_in_payload(self, sync_client):
        sync_client.add("hello", AddMemoryOptions(user_id="u1", agent_id="a1", app_id="p1", run_id="r1"))

        payload = sync_client.client.post.call_args.kwargs["json"]
        assert payload["user_id"] == "u1"
        assert payload["agent_id"] == "a1"
        assert payload["app_id"] == "p1"
        assert payload["run_id"] == "r1"

    def test_async_typed_options_put_entity_ids_in_payload(self, async_client):
        asyncio.run(async_client.add("hello", AddMemoryOptions(user_id="u1")))

        payload = async_client.async_client.post.call_args.kwargs["json"]
        assert payload["user_id"] == "u1"

    def test_kwargs_put_entity_ids_in_payload(self, sync_client):
        sync_client.add("hello", user_id="u1")

        payload = sync_client.client.post.call_args.kwargs["json"]
        assert payload["user_id"] == "u1"
