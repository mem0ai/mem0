"""
Test the store_document MCP tool functionality
"""
import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from openmemory.api.app.mcp_server import store_document, user_id_var, client_name_var
from openmemory.api.app.models import Document, Memory


@pytest.mark.asyncio
async def test_store_document_basic():
    """Test basic document storage functionality"""
    
    # Sample markdown content
    sample_title = "My Awesome Markdown File"
    sample_content = """# My Awesome Markdown File

This is a sample markdown file with:

## Features
- Lists
- **Bold text**
- *Italic text*
- Code blocks

```python
def hello_world():
    print("Hello, world!")
```

## Conclusion
This is a great example of storing large content in the memory system.
The content will be stored as a document and linked to a searchable summary memory.
"""
    
    # Mock the context variables
    with patch.object(user_id_var, 'get', return_value="test-user-123"):
        with patch.object(client_name_var, 'get', return_value="claude"):
            # Mock the database and memory client
            with patch('openmemory.api.app.mcp_server.SessionLocal') as mock_session:
                with patch('openmemory.api.app.mcp_server.get_user_and_app') as mock_get_user_app:
                    with patch('openmemory.api.app.utils.memory.get_memory_client') as mock_memory_client:
                        
                        # Setup mocks
                        mock_db = Mock()
                        mock_session.return_value = mock_db
                        
                        mock_user = Mock(id="user-uuid", email="test@example.com")
                        mock_app = Mock(id="app-uuid", name="claude", is_active=True)
                        mock_get_user_app.return_value = (mock_user, mock_app)
                        
                        mock_document = Mock(id="doc-uuid")
                        mock_db.add = Mock()
                        mock_db.flush = Mock()
                        mock_db.commit = Mock()
                        mock_db.close = Mock()
                        
                        # Mock mem0 client response
                        mock_client = Mock()
                        mock_memory_client.return_value = mock_client
                        mock_client.add.return_value = {
                            'results': [{
                                'event': 'ADD',
                                'id': 'mem0-id-123',
                                'memory': f"Document: {sample_title}\nType: markdown\nPreview: {sample_content[:500]}...",
                                'metadata': {}
                            }]
                        }
                        
                        # Mock chunking service
                        with patch('openmemory.api.app.services.chunking_service.ChunkingService') as mock_chunking:
                            mock_chunking_instance = Mock()
                            mock_chunking.return_value = mock_chunking_instance
                            mock_chunking_instance.chunk_document.return_value = 3  # 3 chunks created
                            
                            # Call the function
                            result = await store_document(
                                title=sample_title,
                                content=sample_content,
                                document_type="markdown"
                            )
                            
                            # Parse the JSON response
                            response_data = json.loads(result)
                            
                            # Assertions
                            assert response_data["success"] is True
                            assert response_data["title"] == sample_title
                            assert response_data["document_type"] == "markdown"
                            assert response_data["content_length"] == len(sample_content)
                            assert "Successfully stored document" in response_data["message"]
                            assert "search_tip" in response_data
                            
                            # Verify database operations were called
                            mock_db.add.assert_called()
                            mock_db.flush.assert_called()
                            mock_db.commit.assert_called()
                            mock_db.close.assert_called()
                            
                            # Verify mem0 client was called
                            mock_client.add.assert_called_once()
                            
                            # Verify chunking was attempted
                            mock_chunking_instance.chunk_document.assert_called_once()


@pytest.mark.asyncio
async def test_store_document_validation():
    """Test input validation for store_document"""
    
    # Mock the context variables
    with patch.object(user_id_var, 'get', return_value="test-user-123"):
        with patch.object(client_name_var, 'get', return_value="claude"):
            
            # Test empty title
            result = await store_document(title="", content="Some content")
            assert "Error: Document title is required" in result
            
            # Test empty content
            result = await store_document(title="Test", content="")
            assert "Error: Document content is required" in result
            
            # Test content too short
            result = await store_document(title="Test", content="Short")
            assert "Error: Content too short" in result
            assert "add_memories" in result  # Should suggest alternative


@pytest.mark.asyncio
async def test_store_document_missing_context():
    """Test behavior when context variables are missing"""
    
    # Test missing user_id
    with patch.object(user_id_var, 'get', return_value=None):
        with patch.object(client_name_var, 'get', return_value="claude"):
            result = await store_document(title="Test", content="Some content " * 20)
            assert "Error: Supabase user_id not available in context" in result
    
    # Test missing client_name
    with patch.object(user_id_var, 'get', return_value="test-user-123"):
        with patch.object(client_name_var, 'get', return_value=None):
            result = await store_document(title="Test", content="Some content " * 20)
            assert "Error: client_name not available in context" in result


@pytest.mark.asyncio
async def test_store_document_with_metadata():
    """Test storing document with custom metadata and source URL"""
    
    sample_title = "API Documentation"
    sample_content = "# API Documentation\n\nThis is comprehensive API documentation..." * 10
    custom_metadata = {"author": "John Doe", "version": "1.0", "category": "technical"}
    source_url = "https://example.com/api-docs"
    
    with patch.object(user_id_var, 'get', return_value="test-user-123"):
        with patch.object(client_name_var, 'get', return_value="claude"):
            with patch('openmemory.api.app.mcp_server.SessionLocal') as mock_session:
                with patch('openmemory.api.app.mcp_server.get_user_and_app') as mock_get_user_app:
                    with patch('openmemory.api.app.utils.memory.get_memory_client') as mock_memory_client:
                        with patch('openmemory.api.app.services.chunking_service.ChunkingService'):
                            
                            # Setup basic mocks
                            mock_db = Mock()
                            mock_session.return_value = mock_db
                            
                            mock_user = Mock(id="user-uuid")
                            mock_app = Mock(id="app-uuid", is_active=True)
                            mock_get_user_app.return_value = (mock_user, mock_app)
                            
                            mock_db.add = Mock()
                            mock_db.flush = Mock()
                            mock_db.commit = Mock()
                            mock_db.close = Mock()
                            
                            mock_client = Mock()
                            mock_memory_client.return_value = mock_client
                            mock_client.add.return_value = {'results': [{'event': 'ADD', 'id': 'test-id', 'memory': 'test', 'metadata': {}}]}
                            
                            result = await store_document(
                                title=sample_title,
                                content=sample_content,
                                document_type="documentation",
                                source_url=source_url,
                                metadata=custom_metadata
                            )
                            
                            response_data = json.loads(result)
                            
                            assert response_data["success"] is True
                            assert response_data["title"] == sample_title
                            assert response_data["document_type"] == "documentation"
                            
                            # Verify database operations
                            mock_db.add.assert_called()
                            mock_db.commit.assert_called()


if __name__ == "__main__":
    pytest.main([__file__]) 