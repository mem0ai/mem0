import asyncio

import httpx
import pytest

from mem0.client.main import MemoryClient


class TestMemoryClient:
    @pytest.fixture
    def mock_client(self, mocker):
        """Fixture that provides a mocked HTTPX client for testing.

        Returns:
            MagicMock: A mocked httpx.Client instance with pre-configured responses.
        """
        mock = mocker.MagicMock(spec=httpx.Client)
        mock.headers = {"Authorization": "Token test_key", "Mem0-User-ID": "test_user_id"}
        request = httpx.Request("GET", "https://api.mem0.ai/v1/ping/")
        mock.get.return_value = httpx.Response(200, json={"status": "ok"}, request=request)
        return mock

    def test_init_with_custom_client(self, mock_client, mocker):
        """Test MemoryClient initialization with custom HTTPX client.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - API key is set correctly
            - Base URL is configured properly
            - Required headers are present
        """
        # Given
        api_key = "test_key"
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")

        # When
        client = MemoryClient(api_key=api_key, client=mock_client)

        # Then
        assert client.api_key == api_key
        assert str(mock_client.base_url) == "https://api.mem0.ai"
        assert "Authorization" in mock_client.headers
        assert "Mem0-User-ID" in mock_client.headers

    def test_init_missing_api_key(self, mocker):
        """Test MemoryClient initialization without API key.

        Args:
            mocker: Pytest mocker fixture

        Verifies:
            - Raises ValueError when no API key is provided
        """
        # Given/When/Then
        mocker.patch.dict("os.environ", {"MEM0_API_KEY": ""})
        with pytest.raises(ValueError, match="Mem0 API Key not provided"):
            MemoryClient(api_key=None)

    def test_add_memory(self, mock_client, mocker):
        """Test adding a memory through the client.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Request payload is properly formatted
            - Response is correctly returned
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("POST", "https://api.mem0.ai/v1/memories/")
        mock_client.post.return_value = httpx.Response(200, json={"id": "mem123"}, request=request)

        # When
        result = client.add("test message")

        # Then
        assert result == {"id": "mem123"}
        mock_client.post.assert_called_once_with(
            "/v1/memories/",
            json={"messages": [{"role": "user", "content": "test message"}], "output_format": "v1.1", "version": "v2"},
        )

    def test_get_memory(self, mock_client, mocker):
        """Test retrieving a memory by ID.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Response is correctly returned
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("GET", "https://api.mem0.ai/v1/memories/mem123/")
        mock_client.get.return_value = httpx.Response(200, json={"id": "mem123"}, request=request)

        # When
        result = client.get("mem123")

        # Then
        assert result == {"id": "mem123"}
        mock_client.get.assert_called_once_with("/v1/memories/mem123/", params={})

    def test_search_memory_v1_format(self, mock_client, mocker):
        """Test memory search with v1.0 output format.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Request payload includes output_format
            - Response is correctly returned
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("POST", "https://api.mem0.ai/v1/memories/search/")
        mock_client.post.return_value = httpx.Response(200, json=[{"id": "mem123"}], request=request)

        # When
        result = client.search("test query", output_format="v1.0")

        # Then
        assert result == [{"id": "mem123"}]
        mock_client.post.assert_called_once_with(
            "/v1/memories/search/", json={"query": "test query", "output_format": "v1.0"}
        )

    def test_search_memory_v1_1_format(self, mock_client, mocker):
        """Test memory search with v1.1 output format.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Response format matches v1.1 specification
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("POST", "https://api.mem0.ai/v1/memories/search/")
        mock_client.post.return_value = httpx.Response(200, json={"results": [{"id": "mem123"}]}, request=request)

        # When
        result = client.search("test query", output_format="v1.1")

        # Then
        assert result == {"results": [{"id": "mem123"}]}

    def test_delete_memory(self, mock_client, mocker):
        """Test deleting a memory by ID.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Response indicates successful deletion
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("DELETE", "https://api.mem0.ai/v1/memories/mem123/")
        mock_client.delete.return_value = httpx.Response(200, json={"status": "deleted"}, request=request)

        # When
        result = client.delete("mem123")

        # Then
        assert result == {"status": "deleted"}
        mock_client.delete.assert_called_once_with("/v1/memories/mem123/", params={})

    def test_api_error_handling(self, mock_client):
        """Test error handling for API requests.

        Args:
            mock_client: Mocked httpx.Client fixture

        Verifies:
            - Proper exception is raised for API errors
        """
        # Given
        client = MemoryClient(api_key="test_key", client=mock_client)
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Not found",
            request=httpx.Request("GET", "/test"),
            response=httpx.Response(404, json={"detail": "Not found"}),
        )

        # When/Then
        with pytest.raises(Exception, match="API request failed"):
            client.get("mem123")

    def test_get_all_memories(self, mock_client, mocker):
        """Test retrieving all memories.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called for v1 and v2
            - Parameters are passed correctly
            - Response is properly returned
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)

        # Test v1
        request_v1 = httpx.Request("GET", "https://api.mem0.ai/v1/memories/")
        mock_client.get.return_value = httpx.Response(200, json=[{"id": "mem1"}, {"id": "mem2"}], request=request_v1)

        # When
        result_v1 = client.get_all(version="v1", user_id="user123")

        # Then
        assert result_v1 == [{"id": "mem1"}, {"id": "mem2"}]
        mock_client.get.assert_called_once_with("/v1/memories/", params={"user_id": "user123"})

        # Reset mock for v2 test
        mock_client.reset_mock()
        request_v2 = httpx.Request("POST", "https://api.mem0.ai/v2/memories/")
        mock_client.post.return_value = httpx.Response(200, json=[{"id": "mem3"}, {"id": "mem4"}], request=request_v2)

        # When
        result_v2 = client.get_all(version="v2", agent_id="agent123")

        # Then
        assert result_v2 == [{"id": "mem3"}, {"id": "mem4"}]
        mock_client.post.assert_called_once_with("/v2/memories/", json={"agent_id": "agent123"})

    def test_update_memory(self, mock_client, mocker):
        """Test updating a memory.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Request payload is properly formatted
            - Response is correctly returned
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("PUT", "https://api.mem0.ai/v1/memories/mem123/")
        mock_client.put.return_value = httpx.Response(200, json={"id": "mem123", "status": "updated"}, request=request)

        # When
        result = client.update("mem123", "new content")

        # Then
        assert result == {"id": "mem123", "status": "updated"}
        mock_client.put.assert_called_once_with("/v1/memories/mem123/", json={"text": "new content"}, params={})

    def test_delete_all_memories(self, mock_client, mocker):
        """Test deleting all memories.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Parameters are passed correctly
            - Response indicates successful deletion
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("DELETE", "https://api.mem0.ai/v1/memories/")
        mock_client.delete.return_value = httpx.Response(200, json={"status": "deleted", "count": 42}, request=request)

        # When
        result = client.delete_all(app_id="app123")

        # Then
        assert result == {"status": "deleted", "count": 42}
        mock_client.delete.assert_called_once_with("/v1/memories/", params={"app_id": "app123"})

    def test_get_memory_history(self, mock_client, mocker):
        """Test retrieving memory history.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Response contains history records
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("GET", "https://api.mem0.ai/v1/memories/mem123/history/")
        mock_client.get.return_value = httpx.Response(
            200, json=[{"version": 1, "text": "old content"}, {"version": 2, "text": "new content"}], request=request
        )

        # When
        result = client.history("mem123")

        # Then
        assert result == [{"version": 1, "text": "old content"}, {"version": 2, "text": "new content"}]
        mock_client.get.assert_called_once_with("/v1/memories/mem123/history/", params={})

    def test_get_users(self, mock_client, mocker):
        """Test retrieving users/entities.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Response contains user/entity data
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("GET", "https://api.mem0.ai/v1/entities/")
        mock_client.get.return_value = httpx.Response(
            200, json={"results": [{"type": "user", "name": "user1"}]}, request=request
        )

        # When
        result = client.users()

        # Then
        assert result == {"results": [{"type": "user", "name": "user1"}]}
        mock_client.get.assert_called_once_with("/v1/entities/", params={})

    def test_delete_users(self, mock_client, mocker):
        """Test deleting users/entities.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called
            - Handles both filtered and unfiltered cases
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)

        # Test filtered delete
        request1 = httpx.Request("DELETE", "https://api.mem0.ai/v2/entities/user/user1/")
        mock_client.delete.return_value = httpx.Response(
            200, json={"message": "Entity deleted successfully."}, request=request1
        )

        # When
        result1 = client.delete_users(user_id="user1")

        # Then
        assert result1 == {"message": "Entity deleted successfully."}
        mock_client.delete.assert_called_once_with("/v2/entities/user/user1/", params={})

        # Reset mock for unfiltered delete
        mock_client.reset_mock()
        request2 = httpx.Request("GET", "https://api.mem0.ai/v1/entities/")
        mock_client.get.return_value = httpx.Response(
            200,
            json={"results": [{"type": "user", "name": "user1"}, {"type": "agent", "name": "agent1"}]},
            request=request2,
        )
        request3 = httpx.Request("DELETE", "https://api.mem0.ai/v2/entities/user/user1/")
        request4 = httpx.Request("DELETE", "https://api.mem0.ai/v2/entities/agent/agent1/")
        mock_client.delete.side_effect = [httpx.Response(200, request=request3), httpx.Response(200, request=request4)]

        # When
        result2 = client.delete_users()

        # Then
        assert result2 == {"message": "All users, agents, apps and runs deleted."}
        assert mock_client.delete.call_count == 2

    def test_reset_client(self, mock_client, mocker):
        """Test resetting client by deleting all users/memories.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Calls delete_users()
            - Returns correct success message
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        mocker.patch.object(client, "delete_users", return_value=asyncio.Future())
        client.delete_users.return_value.set_result({"message": "All users deleted"})

        # When
        result = client.reset()

        # Then
        assert result == {"message": "Client reset successful. All users and memories deleted."}
        client.delete_users.assert_called_once()

    def test_batch_operations(self, mock_client, mocker):
        """Test batch memory operations.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called
            - Request payloads are properly formatted
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)

        # Test batch update
        request1 = httpx.Request("PUT", "https://api.mem0.ai/v1/batch/")
        mock_client.put.return_value = httpx.Response(200, json={"status": "updated"}, request=request1)
        memories = [{"memory_id": "mem1", "text": "text1"}]

        # When
        result1 = client.batch_update(memories)

        # Then
        assert result1 == {"status": "updated"}
        mock_client.put.assert_called_once_with("/v1/batch/", json={"memories": memories})

        # Reset mock for batch delete
        mock_client.reset_mock()
        request2 = httpx.Request("DELETE", "https://api.mem0.ai/v1/batch/")
        mock_client.request.return_value = httpx.Response(200, json={"status": "deleted"}, request=request2)

        # When
        result2 = client.batch_delete(memories)

        # Then
        assert result2 == {"status": "deleted"}
        mock_client.request.assert_called_once_with("DELETE", "/v1/batch/", json={"memories": memories})

    def test_memory_exports(self, mock_client, mocker):
        """Test memory export operations.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called for export operations
            - Request payloads are properly formatted
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)

        # Test create export
        schema = {"fields": ["content", "timestamp"]}
        request1 = httpx.Request("POST", "https://api.mem0.ai/v1/exports/")
        mock_client.post.return_value = httpx.Response(
            200, json={"export_id": "exp123", "status": "processing"}, request=request1
        )

        # When
        result1 = client.create_memory_export(schema, user_id="user1")

        # Then
        assert result1 == {"export_id": "exp123", "status": "processing"}
        mock_client.post.assert_called_once_with("/v1/exports/", json={"schema": schema, "user_id": "user1"})

        # Reset mock for get export
        mock_client.reset_mock()
        request2 = httpx.Request("POST", "https://api.mem0.ai/v1/exports/get/")
        mock_client.post.return_value = httpx.Response(
            200, json={"data": [{"content": "test", "timestamp": "2025-01-01"}]}, request=request2
        )

        # When
        result2 = client.get_memory_export(export_id="exp123")

        # Then
        assert result2 == {"data": [{"content": "test", "timestamp": "2025-01-01"}]}
        mock_client.post.assert_called_once_with("/v1/exports/get/", json={"export_id": "exp123"})

    def test_project_operations(self, mock_client, mocker):
        """Test project-related operations.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called for project operations
            - Handles org_id and project_id requirements
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        client.org_id = "org123"
        client.project_id = "proj456"

        # Test get project
        request1 = httpx.Request("GET", "https://api.mem0.ai/api/v1/orgs/organizations/org123/projects/proj456/")
        mock_client.get.return_value = httpx.Response(
            200, json={"name": "Test Project", "custom_instructions": "Be helpful"}, request=request1
        )

        # When
        result1 = client.get_project(fields=["name", "custom_instructions"])

        # Then
        assert result1 == {"name": "Test Project", "custom_instructions": "Be helpful"}
        mock_client.get.assert_called_once_with(
            "/api/v1/orgs/organizations/org123/projects/proj456/",
            params={"fields": ["name", "custom_instructions"], "org_id": "org123", "project_id": "proj456"},
        )

        # Reset mock for update project
        mock_client.reset_mock()
        request2 = httpx.Request("PATCH", "https://api.mem0.ai/api/v1/orgs/organizations/org123/projects/proj456/")
        mock_client.patch.return_value = httpx.Response(200, json={"status": "updated"}, request=request2)

        # When
        result2 = client.update_project(custom_instructions="New instructions", custom_categories=["cat1", "cat2"])

        # Then
        assert result2 == {"status": "updated"}
        mock_client.patch.assert_called_once_with(
            "/api/v1/orgs/organizations/org123/projects/proj456/",
            json={
                "custom_instructions": "New instructions",
                "custom_categories": ["cat1", "cat2"],
                "org_id": "org123",
                "project_id": "proj456",
            },
        )

    def test_webhook_operations(self, mock_client, mocker):
        """Test webhook operations.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoints are called for webhook CRUD operations
            - Request payloads are properly formatted
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)

        # Test get webhooks
        request1 = httpx.Request("GET", "https://api.mem0.ai/api/v1/webhooks/projects/proj123/")
        mock_client.get.return_value = httpx.Response(
            200, json={"webhooks": [{"id": 1, "name": "Test Webhook"}]}, request=request1
        )

        # When
        result1 = client.get_webhooks("proj123")

        # Then
        assert result1 == {"webhooks": [{"id": 1, "name": "Test Webhook"}]}
        mock_client.get.assert_called_once_with(
            "api/v1/webhooks/projects/proj123/",
        )

        # Reset mock for create webhook
        mock_client.reset_mock()
        request2 = httpx.Request("POST", "https://api.mem0.ai/api/v1/webhooks/projects/proj123/")
        mock_client.post.return_value = httpx.Response(200, json={"id": 2, "name": "New Webhook"}, request=request2)

        # When
        result2 = client.create_webhook(
            url="https://example.com/webhook", name="New Webhook", project_id="proj123", event_types=["memory.created"]
        )

        # Then
        assert result2 == {"id": 2, "name": "New Webhook"}
        mock_client.post.assert_called_once_with(
            "api/v1/webhooks/projects/proj123/",
            json={"url": "https://example.com/webhook", "name": "New Webhook", "event_types": ["memory.created"]},
        )

        # Reset mock for update webhook
        mock_client.reset_mock()
        request3 = httpx.Request("PUT", "https://api.mem0.ai/api/v1/webhooks/1/")
        mock_client.put.return_value = httpx.Response(200, json={"id": 1, "name": "Updated Webhook"}, request=request3)

        # When
        result3 = client.update_webhook(webhook_id=1, name="Updated Webhook")

        # Then
        assert result3 == {"id": 1, "name": "Updated Webhook"}
        mock_client.put.assert_called_once_with("api/v1/webhooks/1/", json={"name": "Updated Webhook"})

        # Reset mock for delete webhook
        mock_client.reset_mock()
        request4 = httpx.Request("DELETE", "https://api.mem0.ai/api/v1/webhooks/1/")
        mock_client.delete.return_value = httpx.Response(200, json={"status": "deleted"}, request=request4)

        # When
        result4 = client.delete_webhook(1)

        # Then
        assert result4 == {"status": "deleted"}
        mock_client.delete.assert_called_once_with("api/v1/webhooks/1/")

    def test_feedback(self, mock_client, mocker):
        """Test submitting feedback.

        Args:
            mock_client: Mocked httpx.Client fixture
            mocker: Pytest mocker fixture

        Verifies:
            - Correct API endpoint is called
            - Validates feedback values
            - Properly formats request payload
        """
        # Given
        mocker.patch.object(MemoryClient, "_validate_api_key", return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("POST", "https://api.mem0.ai/v1/feedback/")
        mock_client.post.return_value = httpx.Response(200, json={"status": "received"}, request=request)

        # When
        result = client.feedback(memory_id="mem123", feedback="POSITIVE", feedback_reason="Very helpful")

        # Then
        assert result == {"status": "received"}
        mock_client.post.assert_called_once_with(
            "/v1/feedback/",
            json={"memory_id": "mem123", "feedback": "POSITIVE", "feedback_reason": "Very helpful"},
        )

        # Test invalid feedback value
        with pytest.raises(ValueError, match="feedback must be one of NEGATIVE, POSITIVE, VERY_NEGATIVE or None"):
            client.feedback("mem123", "INVALID")
