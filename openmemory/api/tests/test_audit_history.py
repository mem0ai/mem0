import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from app.models import Memory, MemoryState, MemoryStatusHistory
from app.mcp_server import add_memories, user_id_var, client_name_var

@pytest.mark.asyncio
@patch("app.mcp_server.SessionLocal")
@patch("app.mcp_server.get_user_and_app")
@patch("app.mcp_server.get_memory_client_safe")
async def test_add_memories_audit_history_new_memory(mock_get_client, mock_get_user_app, mock_session):
    # Setup context vars
    u_token = user_id_var.set("test-user")
    c_token = client_name_var.set("test-client")
    
    try:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        mock_user = MagicMock()
        mock_user.id = "user_123"
        mock_app = MagicMock()
        mock_app.id = "app_123"
        mock_app.is_active = True
        mock_get_user_app.return_value = (mock_user, mock_app)
        
        mock_client = MagicMock()
        memory_id_str = str(uuid.uuid4())
        mock_client.add.return_value = {
            "results": [
                {
                    "id": memory_id_str,
                    "event": "ADD",
                    "memory": "Test memory content"
                }
            ]
        }
        mock_get_client.return_value = mock_client
        
        # Mock that the memory does NOT exist in the database initially
        mock_db.query.return_value.filter.return_value.first.return_value = None
        
        response_str = await add_memories("Test memory", infer=False)
        assert json.loads(response_str) == mock_client.add.return_value
        
        # Verify history entry was created with old_state=None
        added_objects = mock_db.add.call_args_list
        history_entry = next((call[0][0] for call in added_objects if isinstance(call[0][0], MemoryStatusHistory)), None)
        
        assert history_entry is not None
        assert history_entry.old_state is None
        assert history_entry.new_state == MemoryState.active
        
    finally:
        user_id_var.reset(u_token)
        client_name_var.reset(c_token)


@pytest.mark.asyncio
@patch("app.mcp_server.SessionLocal")
@patch("app.mcp_server.get_user_and_app")
@patch("app.mcp_server.get_memory_client_safe")
async def test_add_memories_audit_history_existing_memory(mock_get_client, mock_get_user_app, mock_session):
    # Setup context vars
    u_token = user_id_var.set("test-user")
    c_token = client_name_var.set("test-client")
    
    try:
        mock_db = MagicMock()
        mock_session.return_value = mock_db
        
        mock_user = MagicMock()
        mock_user.id = "user_123"
        mock_app = MagicMock()
        mock_app.id = "app_123"
        mock_app.is_active = True
        mock_get_user_app.return_value = (mock_user, mock_app)
        
        mock_client = MagicMock()
        memory_id_str = str(uuid.uuid4())
        mock_client.add.return_value = {
            "results": [
                {
                    "id": memory_id_str,
                    "event": "ADD",
                    "memory": "Test memory content"
                }
            ]
        }
        mock_get_client.return_value = mock_client
        
        # Mock that the memory DOES exist in the database (e.g. was previously deleted)
        existing_memory = Memory(id=uuid.UUID(memory_id_str), state=MemoryState.deleted)
        mock_db.query.return_value.filter.return_value.first.return_value = existing_memory
        
        response_str = await add_memories("Test memory", infer=False)
        assert json.loads(response_str) == mock_client.add.return_value
        
        # Verify history entry was created with old_state=deleted
        added_objects = mock_db.add.call_args_list
        history_entry = next((call[0][0] for call in added_objects if isinstance(call[0][0], MemoryStatusHistory)), None)
        
        assert history_entry is not None
        assert history_entry.old_state == MemoryState.deleted
        assert history_entry.new_state == MemoryState.active
        
    finally:
        user_id_var.reset(u_token)
        client_name_var.reset(c_token)
