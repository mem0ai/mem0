import asyncio

import httpx
import pytest

from mem0.client.main import AsyncMemoryClient


class TestAsyncMemoryClient:
    @pytest.fixture
    def mock_async_client(self, mocker):
        """Fixture that provides a mocked async HTTPX client for testing.

        Returns:
            MagicMock: A mocked httpx.AsyncClient instance with pre-configured responses.
        """
        mock = mocker.MagicMock(spec=httpx.AsyncClient)
        mock.headers = {"Authorization": "Token test_key", "Mem0-User-ID": "test_user_id"}
        request = httpx.Request("GET", "https://api.mem0.ai/v1/ping/")
        mock.get.return_value = httpx.Response(200, json={"status": "ok"}, request=request)
        return mock

    @pytest.mark.asyncio
    async def test_async_init_with_custom_client(self, mock_async_client, mocker):
        """Test AsyncMemoryClient initialization with custom HTTPX client.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - API key is set correctly
            - Base URL is configured properly
            - Required headers are present
        """
        # Given
        api_key = "test_key"
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")

        # When
        client = AsyncMemoryClient(api_key=api_key, client=mock_async_client)

        # Then
        assert client.api_key == api_key
        assert str(mock_async_client.base_url) == "https://api.mem0.ai"
        assert "Authorization" in mock_async_client.headers
        assert "Mem0-User-ID" in mock_async_client.headers

    @pytest.mark.asyncio
    async def test_async_init_missing_api_key(self, mocker):
        """Test AsyncMemoryClient initialization without API key.

        Args:
            mocker: Pytest mocker fixture

        Verifies:
            - Raises ValueError when no API key is provided
        """
        # Given/When/Then
        mocker.patch.dict("os.environ", {"MEM0_API_KEY": ""})
        with pytest.raises(ValueError, match="Mem0 API Key not provided"):
            AsyncMemoryClient(api_key=None)

    @pytest.mark.asyncio
    async def test_async_add(self, mock_async_client, mocker):
        """Test async memory addition.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Request payload is properly formatted
            - Response is correctly returned
        """
        # Given
        api_key = "test_key"
        test_messages = "test message"
        request = httpx.Request("POST", "https://api.mem0.ai/v1/memories/")
        mock_async_client.post.return_value = httpx.Response(200, json={"id": "mem123"}, request=request)
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")

        # When
        client = AsyncMemoryClient(api_key=api_key, client=mock_async_client)
        result = await client.add(test_messages)

        # Then
        assert result == {"id": "mem123"}
        mock_async_client.post.assert_called_once_with(
            "/v1/memories/",
            json={"messages": [{"role": "user", "content": "test message"}], "output_format": "v1.1", "version": "v2"},
        )

    @pytest.mark.asyncio
    async def test_async_get(self, mock_async_client, mocker):
        """Test async memory retrieval by ID.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Response is correctly returned
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("GET", "https://api.mem0.ai/v1/memories/mem123/")
        mock_async_client.get.return_value = httpx.Response(200, json={"id": "mem123"}, request=request)

        # When
        result = await client.get("mem123")

        # Then
        assert result == {"id": "mem123"}
        mock_async_client.get.assert_called_once_with("/v1/memories/mem123/", params={})

    @pytest.mark.asyncio
    async def test_async_search_v1_format(self, mock_async_client, mocker):
        """Test async memory search with v1.0 output format.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Request payload includes output_format
            - Response is correctly returned
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("POST", "https://api.mem0.ai/v1/memories/search/")
        mock_async_client.post.return_value = httpx.Response(200, json=[{"id": "mem123"}], request=request)

        # When
        result = await client.search("test query", output_format="v1.0")

        # Then
        assert result == [{"id": "mem123"}]
        mock_async_client.post.assert_called_once_with(
            "/v1/memories/search/", json={"query": "test query", "output_format": "v1.0"}
        )

    @pytest.mark.asyncio
    async def test_async_search_v1_1_format(self, mock_async_client, mocker):
        """Test async memory search with v1.1 output format.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Response format matches v1.1 specification
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("POST", "https://api.mem0.ai/v1/memories/search/")
        mock_async_client.post.return_value = httpx.Response(200, json={"results": [{"id": "mem123"}]}, request=request)

        # When
        result = await client.search("test query", output_format="v1.1")

        # Then
        assert result == {"results": [{"id": "mem123"}]}

    @pytest.mark.asyncio
    async def test_async_delete_memory(self, mock_async_client, mocker):
        """Test deleting a memory by ID.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Response indicates successful deletion
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("DELETE", "https://api.mem0.ai/v1/memories/mem123/")
        mock_async_client.delete.return_value = httpx.Response(200, json={"status": "deleted"}, request=request)

        # When
        result = await client.delete("mem123")

        # Then
        assert result == {"status": "deleted"}
        mock_async_client.delete.assert_called_once_with("/v1/memories/mem123/", params={})

    @pytest.mark.asyncio
    async def test_async_error_handling(self, mock_async_client, mocker):
        """Test async error handling for API requests.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Proper exception is raised for API errors
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        mock_async_client.get.side_effect = httpx.HTTPStatusError(
            "Not found",
            request=httpx.Request("GET", "/test"),
            response=httpx.Response(404, json={"detail": "Not found"}),
        )

        # When/Then
        with pytest.raises(httpx.HTTPStatusError, match="Not found"):
            await client.get("mem123")

    @pytest.mark.asyncio
    async def test_async_get_all(self, mock_async_client, mocker):
        """Test async retrieval of all memories.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called for v1 and v2
            - Parameters are passed correctly
            - Response is properly returned
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)

        # Test v1
        request_v1 = httpx.Request("GET", "https://api.mem0.ai/v1/memories/")
        mock_async_client.get.return_value = httpx.Response(
            200, json=[{"id": "mem1"}, {"id": "mem2"}], request=request_v1
        )

        # When
        result_v1 = await client.get_all(version="v1", user_id="user123")

        # Then
        assert result_v1 == [{"id": "mem1"}, {"id": "mem2"}]
        mock_async_client.get.assert_called_once_with("/v1/memories/", params={"user_id": "user123"})

        # Reset mock for v2 test
        mock_async_client.reset_mock()
        request_v2 = httpx.Request("POST", "https://api.mem0.ai/v2/memories/")
        mock_async_client.post.return_value = httpx.Response(
            200, json=[{"id": "mem3"}, {"id": "mem4"}], request=request_v2
        )

        # When
        result_v2 = await client.get_all(version="v2", agent_id="agent123")

        # Then
        assert result_v2 == [{"id": "mem3"}, {"id": "mem4"}]
        mock_async_client.post.assert_called_once_with("/v2/memories/", json={"agent_id": "agent123"})

    @pytest.mark.asyncio
    async def test_async_update(self, mock_async_client, mocker):
        """Test async memory update.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Request payload is properly formatted
            - Response is correctly returned
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("PUT", "https://api.mem0.ai/v1/memories/mem123/")
        mock_async_client.put.return_value = httpx.Response(
            200, json={"id": "mem123", "status": "updated"}, request=request
        )

        # When
        result = await client.update("mem123", "new content")

        # Then
        assert result == {"id": "mem123", "status": "updated"}
        mock_async_client.put.assert_called_once_with("/v1/memories/mem123/", json={"text": "new content"}, params={})

    @pytest.mark.asyncio
    async def test_async_delete_all(self, mock_async_client, mocker):
        """Test async deletion of all memories.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Parameters are passed correctly
            - Response indicates successful deletion
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("DELETE", "https://api.mem0.ai/v1/memories/")
        mock_async_client.delete.return_value = httpx.Response(
            200, json={"status": "deleted", "count": 42}, request=request
        )

        # When
        result = await client.delete_all(app_id="app123")

        # Then
        assert result == {"status": "deleted", "count": 42}
        mock_async_client.delete.assert_called_once_with("/v1/memories/", params={"app_id": "app123"})

    @pytest.mark.asyncio
    async def test_async_history(self, mock_async_client, mocker):
        """Test async retrieval of memory history.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Response contains history records
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("GET", "https://api.mem0.ai/v1/memories/mem123/history/")
        mock_async_client.get.return_value = httpx.Response(
            200, json=[{"version": 1, "text": "old content"}, {"version": 2, "text": "new content"}], request=request
        )

        # When
        result = await client.history("mem123")

        # Then
        assert result == [{"version": 1, "text": "old content"}, {"version": 2, "text": "new content"}]
        mock_async_client.get.assert_called_once_with("/v1/memories/mem123/history/", params={})

    @pytest.mark.asyncio
    async def test_async_users(self, mock_async_client, mocker):
        """Test async retrieval of users/entities.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Response contains user/entity data
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("GET", "https://api.mem0.ai/v1/entities/")
        mock_async_client.get.return_value = httpx.Response(
            200, json={"results": [{"type": "user", "name": "user1"}]}, request=request
        )

        # When
        result = await client.users()

        # Then
        assert result == {"results": [{"type": "user", "name": "user1"}]}
        mock_async_client.get.assert_called_once_with("/v1/entities/", params={})

    @pytest.mark.asyncio
    async def test_async_delete_users(self, mock_async_client, mocker):
        """Test async deletion of users/entities.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called
            - Handles both filtered and unfiltered cases
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)

        # Test filtered delete (user_id)
        request1 = httpx.Request("DELETE", "https://api.mem0.ai/v2/entities/user/user1/")
        mock_async_client.delete.return_value = httpx.Response(
            200, json={"message": "Entity deleted successfully."}, request=request1
        )

        # When
        result1 = await client.delete_users(user_id="user1")

        # Then
        assert result1 == {"message": "Entity deleted successfully."}
        mock_async_client.delete.assert_called_once_with("/v2/entities/user/user1/", params={})

        # Reset mock for unfiltered delete
        mock_async_client.reset_mock()
        request2 = httpx.Request("GET", "https://api.mem0.ai/v1/entities/")
        mock_async_client.get.return_value = httpx.Response(
            200,
            json={"results": [{"type": "user", "name": "user1"}, {"type": "agent", "name": "agent1"}]},
            request=request2,
        )
        request3 = httpx.Request("DELETE", "https://api.mem0.ai/v2/entities/user/user1/")
        request4 = httpx.Request("DELETE", "https://api.mem0.ai/v2/entities/agent/agent1/")
        mock_async_client.delete.side_effect = [
            httpx.Response(200, request=request3),
            httpx.Response(200, request=request4),
        ]

        # When
        result2 = await client.delete_users()

        # Then
        assert result2 == {"message": "All users, agents, apps and runs deleted."}
        assert mock_async_client.delete.call_count == 2

    @pytest.mark.asyncio
    async def test_async_reset(self, mock_async_client, mocker):
        """Test async resetting client by deleting all users/memories.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Calls async_delete_users()
            - Returns correct success message
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        future = asyncio.Future()
        future.set_result({"message": "All users deleted"})
        mocker.patch.object(client, "delete_users", return_value=future)

        # When
        result = await client.reset()

        # Then
        assert result == {"message": "Client reset successful. All users and memories deleted."}
        client.delete_users.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_memory_exports(self, mock_async_client, mocker):
        """Test async memory export operations.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called for export operations
            - Request payloads are properly formatted
            - Handles both create and get export operations
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        schema = {"fields": ["content", "timestamp"]}

        # Test create export
        request1 = httpx.Request("POST", "https://api.mem0.ai/v1/exports/")
        mock_async_client.post.return_value = httpx.Response(
            200, json={"export_id": "exp123", "status": "processing"}, request=request1
        )

        # When
        result1 = await client.create_memory_export(schema, user_id="user1")

        # Then
        assert result1 == {"export_id": "exp123", "status": "processing"}
        mock_async_client.post.assert_called_once_with("/v1/exports/", json={"schema": schema, "user_id": "user1"})

        # Reset mock for get export
        mock_async_client.reset_mock()
        request2 = httpx.Request("POST", "https://api.mem0.ai/v1/exports/get/")
        mock_async_client.post.return_value = httpx.Response(
            200, json={"data": [{"content": "test", "timestamp": "2025-01-01"}]}, request=request2
        )

        # When
        result2 = await client.get_memory_export(export_id="exp123")

        # Then
        assert result2 == {"data": [{"content": "test", "timestamp": "2025-01-01"}]}
        mock_async_client.post.assert_called_once_with("/v1/exports/get/", json={"export_id": "exp123"})

    @pytest.mark.asyncio
    async def test_async_project_operations(self, mock_async_client, mocker):
        """Test async project operations.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called for project operations
            - Handles org_id and project_id requirements
            - Tests both get and update operations
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        client.org_id = "org123"
        client.project_id = "proj456"

        # Test get project
        request1 = httpx.Request("GET", "https://api.mem0.ai/api/v1/orgs/organizations/org123/projects/proj456/")
        mock_async_client.get.return_value = httpx.Response(
            200, json={"name": "Test Project", "custom_instructions": "Be helpful"}, request=request1
        )

        # When
        result1 = await client.get_project(fields=["name", "custom_instructions"])

        # Then
        assert result1 == {"name": "Test Project", "custom_instructions": "Be helpful"}
        mock_async_client.get.assert_called_once_with(
            "/api/v1/orgs/organizations/org123/projects/proj456/",
            params={"fields": ["name", "custom_instructions"], "org_id": "org123", "project_id": "proj456"},
        )

        # Reset mock for update project
        mock_async_client.reset_mock()
        request2 = httpx.Request("PATCH", "https://api.mem0.ai/api/v1/orgs/organizations/org123/projects/proj456/")
        mock_async_client.patch.return_value = httpx.Response(200, json={"status": "updated"}, request=request2)

        # When
        result2 = await client.update_project(
            custom_instructions="New instructions", custom_categories=["cat1", "cat2"]
        )

        # Then
        assert result2 == {"status": "updated"}
        mock_async_client.patch.assert_called_once_with(
            "/api/v1/orgs/organizations/org123/projects/proj456/",
            json={
                "custom_instructions": "New instructions",
                "custom_categories": ["cat1", "cat2"],
                "org_id": "org123",
                "project_id": "proj456",
            },
        )

    @pytest.mark.asyncio
    async def test_async_webhook_operations(self, mock_async_client, mocker):
        """Test async webhook operations.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called for webhook CRUD operations
            - Request payloads are properly formatted
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)

        # Test get webhooks
        request1 = httpx.Request("GET", "https://api.mem0.ai/api/v1/webhooks/projects/proj123/")
        mock_async_client.get.return_value = httpx.Response(
            200, json={"webhooks": [{"id": 1, "name": "Test Webhook"}]}, request=request1
        )

        # When
        result1 = await client.get_webhooks("proj123")

        # Then
        assert result1 == {"webhooks": [{"id": 1, "name": "Test Webhook"}]}
        mock_async_client.get.assert_called_once_with(
            "api/v1/webhooks/projects/proj123/",
        )

        # Reset mock for create webhook
        mock_async_client.reset_mock()
        request2 = httpx.Request("POST", "https://api.mem0.ai/api/v1/webhooks/projects/proj123/")
        mock_async_client.post.return_value = httpx.Response(
            200, json={"id": 2, "name": "New Webhook"}, request=request2
        )

        # When
        result2 = await client.create_webhook(
            url="https://example.com/webhook", name="New Webhook", project_id="proj123", event_types=["memory.created"]
        )

        # Then
        assert result2 == {"id": 2, "name": "New Webhook"}
        mock_async_client.post.assert_called_once_with(
            "api/v1/webhooks/projects/proj123/",
            json={"url": "https://example.com/webhook", "name": "New Webhook", "event_types": ["memory.created"]},
        )

        # Reset mock for update webhook
        mock_async_client.reset_mock()
        request3 = httpx.Request("PUT", "https://api.mem0.ai/api/v1/webhooks/1/")
        mock_async_client.put.return_value = httpx.Response(
            200, json={"id": 1, "name": "Updated Webhook"}, request=request3
        )

        # When
        result3 = await client.update_webhook(webhook_id=1, name="Updated Webhook")

        # Then
        assert result3 == {"id": 1, "name": "Updated Webhook"}
        mock_async_client.put.assert_called_once_with("api/v1/webhooks/1/", json={"name": "Updated Webhook"})

        # Reset mock for delete webhook
        mock_async_client.reset_mock()
        request4 = httpx.Request("DELETE", "https://api.mem0.ai/api/v1/webhooks/1/")
        mock_async_client.delete.return_value = httpx.Response(200, json={"status": "deleted"}, request=request4)

        # When
        result4 = await client.delete_webhook(1)

        # Then
        assert result4 == {"status": "deleted"}
        mock_async_client.delete.assert_called_once_with("api/v1/webhooks/1/")

    @pytest.mark.asyncio
    async def test_async_feedback(self, mock_async_client, mocker):
        """Test async feedback submission.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Valid feedback values are accepted
            - Invalid feedback values raise ValueError
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("POST", "https://api.mem0.ai/v1/feedback/")
        mock_async_client.post.return_value = httpx.Response(200, json={"status": "received"}, request=request)

        # Test valid feedback
        # When
        result = await client.feedback(memory_id="mem123", feedback="POSITIVE", feedback_reason="Very helpful")

        # Then
        assert result == {"status": "received"}
        mock_async_client.post.assert_called_once_with(
            "/v1/feedback/", json={"memory_id": "mem123", "feedback": "POSITIVE", "feedback_reason": "Very helpful"}
        )

        # Test invalid feedback
        mock_async_client.reset_mock()
        with pytest.raises(ValueError, match="feedback must be one of NEGATIVE, POSITIVE, VERY_NEGATIVE or None"):
            await client.feedback("mem123", "INVALID")

    @pytest.mark.asyncio
    async def test_async_batch_operations(self, mock_async_client, mocker):
        """Test async batch memory operations.

        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called
            - Request payloads are properly formatted
            - Handles both batch update and batch delete
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, "_validate_api_key", return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        memories = [{"memory_id": "mem1", "text": "text1"}]

        # Test batch update
        request1 = httpx.Request("PUT", "https://api.mem0.ai/v1/batch/")
        mock_async_client.put.return_value = httpx.Response(200, json={"status": "updated"}, request=request1)

        # When
        result1 = await client.batch_update(memories)

        # Then
        assert result1 == {"status": "updated"}
        mock_async_client.put.assert_called_once_with("/v1/batch/", json={"memories": memories})

        # Reset mock for batch delete
        mock_async_client.reset_mock()
        request2 = httpx.Request("DELETE", "https://api.mem0.ai/v1/batch/")
        mock_async_client.request.return_value = httpx.Response(200, json={"status": "deleted"}, request=request2)

        # When
        result2 = await client.batch_delete(memories)

        # Then
        assert result2 == {"status": "deleted"}
        mock_async_client.request.assert_called_once_with("DELETE", "/v1/batch/", json={"memories": memories})
