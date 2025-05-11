import httpx
import pytest

from mem0.client.main import AsyncMemoryClient, MemoryClient


class TestMemoryClient:
    @pytest.fixture
    def mock_client(self, mocker):
        """Fixture that provides a mocked HTTPX client for testing.
        
        Returns:
            MagicMock: A mocked httpx.Client instance with pre-configured responses.
        """
        mock = mocker.MagicMock(spec=httpx.Client)
        mock.headers = {
            "Authorization": "Token test_key",
            "Mem0-User-ID": "test_user_id"
        }
        request = httpx.Request("GET", "https://api.mem0.ai/v1/ping/")
        mock.get.return_value = httpx.Response(200, 
            json={"status": "ok"}, 
            request=request
        )
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
        mocker.patch.object(MemoryClient, '_validate_api_key', return_value="test@example.com")
        
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
        mocker.patch.dict('os.environ', {'MEM0_API_KEY': ''})
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
        mocker.patch.object(MemoryClient, '_validate_api_key', return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("POST", "https://api.mem0.ai/v1/memories/")
        mock_client.post.return_value = httpx.Response(200, 
            json={"id": "mem123"},
            request=request
        )
        
        # When
        result = client.add("test message")
        
        # Then
        assert result == {"id": "mem123"}
        mock_client.post.assert_called_once_with(
            "/v1/memories/",
            json={
                "messages": [{"role": "user", "content": "test message"}],
                "output_format": "v1.1",
                "version": "v2"
            }
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
        mocker.patch.object(MemoryClient, '_validate_api_key', return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("GET", "https://api.mem0.ai/v1/memories/mem123/")
        mock_client.get.return_value = httpx.Response(200, 
            json={"id": "mem123"},
            request=request
        )
        
        # When
        result = client.get("mem123")
        
        # Then
        assert result == {"id": "mem123"}
        mock_client.get.assert_called_once_with(
            "/v1/memories/mem123/",
            params={}
        )

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
        mocker.patch.object(MemoryClient, '_validate_api_key', return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("POST", "https://api.mem0.ai/v1/memories/search/")
        mock_client.post.return_value = httpx.Response(200, 
            json=[{"id": "mem123"}],
            request=request
        )
        
        # When
        result = client.search("test query", output_format="v1.0")
        
        # Then
        assert result == [{"id": "mem123"}]
        mock_client.post.assert_called_once_with(
            "/v1/memories/search/",
            json={"query": "test query", "output_format": "v1.0"}
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
        mocker.patch.object(MemoryClient, '_validate_api_key', return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("POST", "https://api.mem0.ai/v1/memories/search/")
        mock_client.post.return_value = httpx.Response(200, 
            json={"results": [{"id": "mem123"}]},
            request=request
        )
        
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
        mocker.patch.object(MemoryClient, '_validate_api_key', return_value="test@example.com")
        client = MemoryClient(api_key="test_key", client=mock_client)
        request = httpx.Request("DELETE", "https://api.mem0.ai/v1/memories/mem123/")
        mock_client.delete.return_value = httpx.Response(200, 
            json={"status": "deleted"},
            request=request
        )
        
        # When
        result = client.delete("mem123")
        
        # Then
        assert result == {"status": "deleted"}
        mock_client.delete.assert_called_once_with(
            "/v1/memories/mem123/",
            params={}
        )

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
            response=httpx.Response(404, json={"detail": "Not found"})
        )
        
        # When/Then
        with pytest.raises(Exception, match="API request failed"):
            client.get("mem123")

class TestAsyncMemoryClient:
    @pytest.fixture
    def mock_async_client(self, mocker):
        """Fixture that provides a mocked async HTTPX client for testing.
        
        Returns:
            MagicMock: A mocked httpx.AsyncClient instance with pre-configured responses.
        """
        mock = mocker.MagicMock(spec=httpx.AsyncClient)
        request = httpx.Request("GET", "https://api.mem0.ai/v1/ping/")
        mock.get.return_value = httpx.Response(200, json={"status": "ok"}, request=request)
        return mock

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
        mocker.patch.object(AsyncMemoryClient, '_validate_api_key', return_value="test@example.com")
        
        # When
        client = AsyncMemoryClient(api_key=api_key, client=mock_async_client)
        result = await client.add(test_messages)
        
        # Then
        assert result == {"id": "mem123"}
        mock_async_client.post.assert_called_once_with(
            "/v1/memories/",
            json={
                "messages": [{"role": "user", "content": "test message"}],
                "output_format": "v1.1",
                "version": "v2"
            }
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
        mocker.patch.object(AsyncMemoryClient, '_validate_api_key', return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("GET", "https://api.mem0.ai/v1/memories/mem123/")
        mock_async_client.get.return_value = httpx.Response(200, 
            json={"id": "mem123"},
            request=request
        )
        
        # When
        result = await client.get("mem123")
        
        # Then
        assert result == {"id": "mem123"}
        mock_async_client.get.assert_called_once_with(
            "/v1/memories/mem123/",
            params={}
        )

    @pytest.mark.asyncio
    async def test_async_search(self, mock_async_client, mocker):
        """Test async memory search.
        
        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture
            
        Verifies:
            - Response format matches expected structure
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, '_validate_api_key', return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("POST", "https://api.mem0.ai/v1/memories/search/")
        mock_async_client.post.return_value = httpx.Response(200, 
            json={"results": [{"id": "mem123"}]},
            request=request
        )
        
        # When
        result = await client.search("test query", output_format="v1.1")
        
        # Then
        assert result == {"results": [{"id": "mem123"}]}

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
        mocker.patch.object(AsyncMemoryClient, '_validate_api_key', return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        mock_async_client.get.side_effect = httpx.HTTPStatusError(
            "Not found", 
            request=httpx.Request("GET", "/test"),
            response=httpx.Response(404, json={"detail": "Not found"})
        )
        
        # When/Then
        with pytest.raises(httpx.HTTPStatusError, match="Not found"):
            await client.get("mem123")

    @pytest.mark.asyncio
    async def test_async_batch_operations(self, mock_async_client, mocker):
        """Test async batch memory updates.
        
        Args:
            mock_async_client: Mocked httpx.AsyncClient fixture
            mocker: Pytest mocker fixture
            
        Verifies:
            - Correct API endpoint is called
            - Request payload includes all memories
            - Response indicates successful update
        """
        # Given
        mocker.patch.object(AsyncMemoryClient, '_validate_api_key', return_value="test@example.com")
        client = AsyncMemoryClient(api_key="test_key", client=mock_async_client)
        request = httpx.Request("PUT", "https://api.mem0.ai/v1/batch/")
        mock_async_client.put.return_value = httpx.Response(200, 
            json={"status": "updated"},
            request=request
        )
        memories = [{"memory_id": "mem1", "text": "text1"}]
        
        # When
        result = await client.batch_update(memories)
        
        # Then
        assert result == {"status": "updated"}
        mock_async_client.put.assert_called_once_with(
            "/v1/batch/",
            json={"memories": memories}
        )
