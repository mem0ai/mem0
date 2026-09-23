"""Tests for the MemoryClient profile methods.

These assert request construction — path, verb, body — rather than echoing a
mocked response back. The profile payload itself is the customer's own JSON
Schema shape, so the tests also pin that the SDK passes it through untouched.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_memory_client():
    """A MemoryClient whose transport is mocked."""
    with patch("mem0.client.main.httpx.Client") as mock_httpx:
        mock_http_client = MagicMock()
        mock_http_client.get.return_value = MagicMock(
            json=lambda: {"org_id": "org1", "project_id": "proj1", "user_email": "test@test.com"},
            raise_for_status=lambda: None,
        )
        mock_httpx.return_value = mock_http_client

        with patch("mem0.client.main.capture_client_event"):
            from mem0.client.main import MemoryClient

            client = MemoryClient(api_key="test-api-key")
            # The constructor pings through this same mock; drop that call.
            mock_http_client.get.reset_mock()
            yield client


def _assert_job_call(post_mock, expected_json):
    """One jobs collection, operation in the body, idempotency key per attempt."""
    post_mock.assert_called_once()
    args, kwargs = post_mock.call_args
    assert args[0] == "/v2/profiles/jobs/"
    assert kwargs["json"] == expected_json
    assert kwargs["headers"]["Idempotency-Key"]


def _mock_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class TestGetProfile:
    def test_reads_the_v2_entity_route(self, mock_memory_client):
        mock_memory_client.client.get.return_value = _mock_response(
            {"profile": {}, "status": "pending", "entity_type": "user", "entity_id": "alice"}
        )

        mock_memory_client.get_profile("alice")

        mock_memory_client.client.get.assert_called_once_with("/v2/entities/user/alice/profile/")

    def test_encodes_path_segments(self, mock_memory_client):
        """An id with a slash must not open a new path segment."""
        mock_memory_client.client.get.return_value = _mock_response({"profile": {}, "status": "pending"})

        mock_memory_client.get_profile("tenant/alice")

        mock_memory_client.client.get.assert_called_once_with("/v2/entities/user/tenant%2Falice/profile/")

    def test_returns_the_envelope_verbatim(self, mock_memory_client):
        """The customer's schema keys reach the caller exactly as stored."""
        payload = {
            "profile": {"favorite_topics": ["hiking"], "work_style": {"preferred_hours": "mornings"}},
            "status": "succeeded",
            "entity_type": "user",
            "entity_id": "alice",
            "updated_at": "2026-02-08T00:00:00Z",
            "generation_count": 3,
        }
        mock_memory_client.client.get.return_value = _mock_response(payload)

        assert mock_memory_client.get_profile("alice") == payload


class TestGenerateProfile:
    def test_posts_entity_type_and_id(self, mock_memory_client):
        mock_memory_client.client.post.return_value = _mock_response(
            {"job_id": "j1", "status": "QUEUED", "status_url": "/v2/profiles/jobs/j1/"}
        )

        mock_memory_client.generate_profile("alice")

        _assert_job_call(
            mock_memory_client.client.post,
            {"operation": "trigger", "entity_type": "user", "entity_id": "alice"},
        )

    def test_reuses_caller_idempotency_key(self, mock_memory_client):
        """A caller-supplied key lets a retry hit the same job instead of billing twice."""
        mock_memory_client.client.post.return_value = _mock_response({"job_id": "j1", "status": "QUEUED"})

        mock_memory_client.generate_profile("alice", idempotency_key="retry-key-123")

        _, kwargs = mock_memory_client.client.post.call_args
        assert kwargs["headers"]["Idempotency-Key"] == "retry-key-123"


class TestProfileSettings:
    def test_get_reads_v2(self, mock_memory_client):
        mock_memory_client.client.get.return_value = _mock_response(
            {"enabled": True, "entities": {"user": {"schema": None, "custom_instructions": None}}}
        )

        mock_memory_client.get_profile_settings()

        mock_memory_client.client.get.assert_called_once_with("/v2/profiles/settings/")

    def test_update_sends_only_supplied_fields(self, mock_memory_client):
        """A partial update must not blank the fields it never mentions."""
        mock_memory_client.client.post.return_value = _mock_response({"enabled": False})

        mock_memory_client.update_profile_settings(enabled=False)

        mock_memory_client.client.post.assert_called_once_with(
            "/v2/profiles/settings/",
            json={"enabled": False},
        )

    def test_update_nests_schema_under_entities(self, mock_memory_client):
        """The API takes only ``enabled`` and ``entities`` at the top level.

        A flat body is rejected with ``Unsupported settings``, so this nesting is
        what makes the call work at all.
        """
        schema = {"type": "object", "properties": {"x": {"type": "string", "description": "d"}}}
        mock_memory_client.client.post.return_value = _mock_response({"enabled": True})

        mock_memory_client.update_profile_settings(enabled=True, schema=schema)

        _, kwargs = mock_memory_client.client.post.call_args
        assert set(kwargs["json"]) == {"enabled", "entities"}
        assert "schema" not in kwargs["json"]

    def test_update_targets_the_user_entity_type(self, mock_memory_client):
        schema = {"type": "object", "properties": {"x": {"type": "string", "description": "d"}}}
        mock_memory_client.client.post.return_value = _mock_response({"enabled": True})

        mock_memory_client.update_profile_settings(schema=schema)

        _, kwargs = mock_memory_client.client.post.call_args
        assert kwargs["json"] == {"entities": {"user": {"schema": schema}}}

    def test_update_passes_schema_verbatim(self, mock_memory_client):
        schema = {
            "type": "object",
            "properties": {
                "favorite_topics": {
                    "type": "array",
                    "description": "Topics the user returns to",
                    "items": {"type": "string"},
                }
            },
        }
        mock_memory_client.client.post.return_value = _mock_response({"enabled": True})

        mock_memory_client.update_profile_settings(enabled=True, schema=schema, custom_instructions="Keep it durable")

        mock_memory_client.client.post.assert_called_once_with(
            "/v2/profiles/settings/",
            json={
                "enabled": True,
                "entities": {"user": {"schema": schema, "custom_instructions": "Keep it durable"}},
            },
        )

    def test_update_clears_fields_with_explicit_none(self, mock_memory_client):
        """Explicit ``None`` clears a field; the sentinel default leaves it untouched."""
        mock_memory_client.client.post.return_value = _mock_response({"enabled": True})

        mock_memory_client.update_profile_settings(schema=None, custom_instructions=None)

        _, kwargs = mock_memory_client.client.post.call_args
        assert kwargs["json"] == {"entities": {"user": {"schema": None, "custom_instructions": None}}}


class TestSampleProfiles:
    def test_sample_without_limit(self, mock_memory_client):
        mock_memory_client.client.post.return_value = _mock_response({"sampled": 5, "entity_ids": []})

        mock_memory_client.sample_profiles()

        _assert_job_call(mock_memory_client.client.post, {"operation": "sample", "entity_type": "user"})

    def test_sample_with_limit(self, mock_memory_client):
        mock_memory_client.client.post.return_value = _mock_response({"sampled": 3, "entity_ids": []})

        mock_memory_client.sample_profiles(limit=3)

        _assert_job_call(
            mock_memory_client.client.post,
            {"operation": "sample", "limit": 3, "entity_type": "user"},
        )


class TestAsyncClientParity:
    """The async client must speak the same wire protocol as the sync one."""

    @pytest.fixture
    def async_client(self):
        # AsyncMemoryClient validates the key synchronously, through requests.
        validation = MagicMock()
        validation.json.return_value = {
            "org_id": "org1",
            "project_id": "proj1",
            "user_email": "test@test.com",
        }
        validation.raise_for_status.return_value = None

        with patch("mem0.client.main.httpx.AsyncClient") as mock_httpx:
            mock_httpx.return_value = MagicMock()
            with patch("mem0.client.main.requests.get", return_value=validation):
                with patch("mem0.client.main.capture_client_event"):
                    from mem0.client.main import AsyncMemoryClient

                    yield AsyncMemoryClient(api_key="test-api-key")

    def test_get_profile(self, async_client):
        async_client.async_client.get = AsyncMock(return_value=_mock_response({"profile": {}, "status": "pending"}))

        asyncio.run(async_client.get_profile("alice"))

        async_client.async_client.get.assert_called_once_with("/v2/entities/user/alice/profile/")

    def test_generate_profile(self, async_client):
        async_client.async_client.post = AsyncMock(return_value=_mock_response({"job_id": "j1", "status": "QUEUED"}))

        asyncio.run(async_client.generate_profile("alice"))

        _assert_job_call(
            async_client.async_client.post,
            {"operation": "trigger", "entity_type": "user", "entity_id": "alice"},
        )

    def test_update_settings_partial(self, async_client):
        async_client.async_client.post = AsyncMock(return_value=_mock_response({"enabled": True}))

        asyncio.run(async_client.update_profile_settings(enabled=True))

        async_client.async_client.post.assert_called_once_with(
            "/v2/profiles/settings/",
            json={"enabled": True},
        )

    def test_update_settings_nests_schema(self, async_client):
        """The async client builds the same body as the sync one."""
        schema = {"type": "object", "properties": {"x": {"type": "string", "description": "d"}}}
        async_client.async_client.post = AsyncMock(return_value=_mock_response({"enabled": True}))

        asyncio.run(async_client.update_profile_settings(enabled=True, schema=schema))

        async_client.async_client.post.assert_called_once_with(
            "/v2/profiles/settings/",
            json={"enabled": True, "entities": {"user": {"schema": schema}}},
        )

    def test_update_settings_clears_with_none(self, async_client):
        async_client.async_client.post = AsyncMock(return_value=_mock_response({"enabled": True}))

        asyncio.run(async_client.update_profile_settings(custom_instructions=None))

        async_client.async_client.post.assert_called_once_with(
            "/v2/profiles/settings/",
            json={"entities": {"user": {"custom_instructions": None}}},
        )
