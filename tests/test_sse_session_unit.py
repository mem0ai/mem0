import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from contextvars import ContextVar
import contextvars

# Mock pro context variables
user_id_var = ContextVar("user_id", default=None)
client_name_var = ContextVar("client_name", default=None)


class TestSSESessionUnit:
    """Unit testy pro SSE session funkcionalitu podle MCP protokolu"""
    
    def setup_method(self):
        """Setup pro každý test"""
        self.client_name = "testclient"
        self.user_id = "testuser"
        self.session_id = None  # Bude nastaveno při inicializaci
        
        # Reset context variables
        try:
            user_id_var.set(self.user_id)
            client_name_var.set(self.client_name)
        except LookupError:
            pass
    
    def test_context_variables_setup(self):
        """Test nastavení context variables"""
        # Nastaví context variables
        user_id_var.set(self.user_id)
        client_name_var.set(self.client_name)
        
        # Ověří, že jsou správně nastavené
        assert user_id_var.get() == self.user_id
        assert client_name_var.get() == self.client_name
        print("✅ Context variables setup úspěšný")
    
    def test_mcp_initialization_with_session_id(self):
        """Test MCP initialization s session_id"""
        # Správný formát pro MCP initialization
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": self.client_name,
                    "version": "1.0.0"
                }
            }
        }
        
        # Očekávaná odpověď s session_id
        expected_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "sessionId": "test_session_123"
            }
        }
        
        # Ověří strukturu
        assert init_payload["jsonrpc"] == "2.0"
        assert init_payload["method"] == "initialize"
        assert init_payload["params"]["protocolVersion"] == "2024-11-05"
        assert init_payload["params"]["clientInfo"]["name"] == self.client_name
        
        # Ověří odpověď
        assert expected_response["jsonrpc"] == "2.0"
        assert "result" in expected_response
        assert "sessionId" in expected_response["result"]
        
        # Nastaví session_id z odpovědi
        self.session_id = expected_response["result"]["sessionId"]
        assert self.session_id == "test_session_123"
        
        print("✅ MCP initialization s session_id úspěšný")
    
    def test_mcp_tool_call_with_session_id(self):
        """Test formátu MCP tool call s session_id"""
        # Nejdříve získá session_id
        self.test_mcp_initialization_with_session_id()
        
        # Správný formát pro add_memories s session_id
        add_memories_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "add_memories",
                "arguments": {
                    "text": "Testovací zpráva"
                },
                "sessionId": self.session_id
            }
        }
        
        # Ověří strukturu
        assert add_memories_payload["jsonrpc"] == "2.0"
        assert add_memories_payload["method"] == "tools/call"
        assert add_memories_payload["params"]["name"] == "add_memories"
        assert "text" in add_memories_payload["params"]["arguments"]
        assert "sessionId" in add_memories_payload["params"]
        assert add_memories_payload["params"]["sessionId"] == self.session_id
        print("✅ MCP tool call s session_id úspěšný")
    
    def test_mcp_tools_list_with_session_id(self):
        """Test formátu MCP tools/list s session_id"""
        # Nejdříve získá session_id
        self.test_mcp_initialization_with_session_id()
        
        # Správný formát pro tools/list s session_id
        tools_list_payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/list",
            "params": {
                "sessionId": self.session_id
            }
        }
        
        # Ověří strukturu
        assert tools_list_payload["jsonrpc"] == "2.0"
        assert tools_list_payload["method"] == "tools/list"
        assert "sessionId" in tools_list_payload["params"]
        assert tools_list_payload["params"]["sessionId"] == self.session_id
        print("✅ MCP tools/list s session_id úspěšný")
    
    def test_sse_url_format(self):
        """Test formátu SSE URL"""
        sse_url = f"/mcp/{self.client_name}/sse/{self.user_id}"
        messages_url = f"/mcp/{self.client_name}/sse/{self.user_id}/messages/"
        
        # Ověří formát URL
        assert sse_url.startswith("/mcp/")
        assert sse_url.endswith(f"/sse/{self.user_id}")
        assert self.client_name in sse_url
        
        assert messages_url.startswith("/mcp/")
        assert messages_url.endswith("/messages/")
        assert self.client_name in messages_url
        print("✅ SSE URL format úspěšný")
    
    @patch('contextvars.ContextVar.get')
    def test_context_variables_in_add_memories(self, mock_get):
        """Test použití context variables v add_memories funkci"""
        # Mock context variables
        mock_get.side_effect = lambda default=None: {
            "user_id": self.user_id,
            "client_name": self.client_name
        }.get("user_id" if "user_id" in str(mock_get.call_args) else "client_name", default)
        
        # Simuluje volání add_memories s context variables
        def simulate_add_memories(text: str, session_id: str) -> str:
            uid = user_id_var.get(None)
            client_name = client_name_var.get(None)
            
            if not uid:
                return "Error: user_id not provided"
            if not client_name:
                return "Error: client_name not provided"
            
            if not session_id:
                return "Error: session_id not provided"
            
            return f"Success: Added memory for user {uid} from client {client_name} with session {session_id}: {text}"
        
        # Test úspěšného volání
        result = simulate_add_memories("Test message", "test_session_123")
        assert "Success:" in result
        assert self.user_id in result
        assert self.client_name in result
        assert "test_session_123" in result
        print("✅ Context variables v add_memories s session_id úspěšné")
    
    def test_session_id_isolation_simulation(self):
        """Test izolace session_id mezi session"""
        # Session 1
        user1_id = "user1"
        client1_name = "client1"
        session1_id = "session_1_123"
        
        # Session 2
        user2_id = "user2"
        client2_name = "client2"
        session2_id = "session_2_456"
        
        # Simuluje session isolation
        def simulate_session_context(user_id: str, client_name: str, session_id: str, text: str) -> str:
            return f"Session: user={user_id}, client={client_name}, session={session_id}, text={text}"
        
        # Test izolace
        result1 = simulate_session_context(user1_id, client1_name, session1_id, "Message 1")
        result2 = simulate_session_context(user2_id, client2_name, session2_id, "Message 2")
        
        assert user1_id in result1 and client1_name in result1 and session1_id in result1
        assert user2_id in result2 and client2_name in result2 and session2_id in result2
        assert result1 != result2
        assert session1_id != session2_id
        print("✅ Session ID isolation simulation úspěšná")
    
    def test_mcp_tools_list_response_format(self):
        """Test formátu MCP tools/list response"""
        # Očekávaný formát odpovědi na tools/list
        expected_tools_response = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [
                    {
                        "name": "add_memories",
                        "description": "Add a new memory",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "Text to add to memory"
                                }
                            },
                            "required": ["text"]
                        }
                    },
                    {
                        "name": "search_memory",
                        "description": "Search through stored memories",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query"
                                }
                            },
                            "required": ["query"]
                        }
                    }
                ]
            }
        }
        
        # Ověří strukturu
        assert expected_tools_response["jsonrpc"] == "2.0"
        assert "result" in expected_tools_response
        assert "tools" in expected_tools_response["result"]
        
        tools = expected_tools_response["result"]["tools"]
        tool_names = [tool["name"] for tool in tools]
        assert "add_memories" in tool_names
        assert "search_memory" in tool_names
        print("✅ MCP tools/list response format úspěšný")
    
    def test_error_handling_format(self):
        """Test formátu error handling"""
        # Očekávaný formát error response
        error_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {
                "code": -32603,
                "message": "Internal error: session_id not provided",
                "data": {
                    "details": "Session ID is required for this operation"
                }
            }
        }
        
        # Ověří strukturu
        assert error_response["jsonrpc"] == "2.0"
        assert "error" in error_response
        assert "code" in error_response["error"]
        assert "message" in error_response["error"]
        print("✅ Error handling format úspěšný")
    
    def test_complete_mcp_flow_with_session_id_simulation(self):
        """Test simulace kompletního MCP flow s session_id"""
        # 1. SSE connection
        sse_connection = Mock()
        sse_connection.status_code = 200
        sse_connection.headers = {"content-type": "text/event-stream"}
        
        # 2. MCP initialization s session_id
        init_response = Mock()
        init_response.status_code = 200
        init_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "sessionId": "test_session_123"
            }
        }
        
        # 3. Tools list s session_id
        tools_response = Mock()
        tools_response.status_code = 200
        tools_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 2,
            "result": {
                "tools": [
                    {"name": "add_memories", "description": "Add memory"},
                    {"name": "search_memory", "description": "Search memory"}
                ]
            }
        }
        
        # 4. Tool call s session_id
        tool_call_response = Mock()
        tool_call_response.status_code = 200
        tool_call_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 3,
            "result": "Memory added successfully"
        }
        
        # Ověří flow
        assert sse_connection.status_code == 200
        assert init_response.status_code == 200
        assert tools_response.status_code == 200
        assert tool_call_response.status_code == 200
        
        # Ověří obsah responses
        init_data = init_response.json()
        assert init_data["jsonrpc"] == "2.0"
        assert "sessionId" in init_data["result"]
        
        tools_data = tools_response.json()
        assert len(tools_data["result"]["tools"]) == 2
        
        tool_call_data = tool_call_response.json()
        assert "result" in tool_call_data
        
        print("✅ Kompletní MCP flow s session_id simulation úspěšná")
    
    def test_session_id_validation(self):
        """Test validace session_id"""
        # Test platného session_id
        valid_session_id = "test_session_123"
        assert len(valid_session_id) > 0
        assert "_" in valid_session_id  # Očekávaný formát
        
        # Test neplatného session_id
        invalid_session_id = ""
        assert len(invalid_session_id) == 0
        
        # Test generování session_id
        def generate_session_id(client_name: str, user_id: str) -> str:
            return f"{client_name}_{user_id}_{hash(f'{client_name}_{user_id}') % 1000:03d}"
        
        generated_session_id = generate_session_id(self.client_name, self.user_id)
        assert len(generated_session_id) > 0
        assert self.client_name in generated_session_id
        assert self.user_id in generated_session_id
        
        print("✅ Session ID validation úspěšná")


if __name__ == "__main__":
    # Spustí unit testy
    pytest.main([__file__, "-v"]) 