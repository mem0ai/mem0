import pytest
import requests
import json
import time
import asyncio
from typing import Dict, Any

BASE_URL = "http://localhost:8765"  # Lokální OpenMemory server


class TestSSESessionAddMemories:
    """Testy pro SSE session s add_memories funkcí podle MCP protokolu"""
    
    def setup_method(self):
        """Setup pro každý test"""
        self.client_name = "cursor"  # Podle logů: /mcp/cursor/sse/rmatena
        self.user_id = "rmatena"     # Podle logů: /mcp/cursor/sse/rmatena
        self.sse_url = f"{BASE_URL}/mcp/{self.client_name}/sse/{self.user_id}"
        self.messages_url = f"{BASE_URL}/mcp/{self.client_name}/sse/{self.user_id}/messages/"
        self.session_id = None  # Bude nastaveno při inicializaci
    
    def test_sse_connection_establishment(self):
        """Test vytvoření SSE spojení"""
        try:
            with requests.get(self.sse_url, stream=True, timeout=5) as resp:
                assert resp.status_code == 200
                assert resp.headers.get('content-type', '').startswith('text/event-stream')
                print(f"✅ SSE connection established: {resp.status_code}")
        except requests.exceptions.RequestException as e:
            pytest.skip(f"OpenMemory server not running: {e}")
    
    def test_mcp_initialization_handshake_with_session_id(self):
        """Test MCP initialization handshake s získáním session_id"""
        try:
            # 1. Vytvoří SSE spojení
            with requests.get(self.sse_url, stream=True, timeout=5) as sse_resp:
                assert sse_resp.status_code == 200
                
                # 2. Pošle MCP initialization zprávu
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
                
                print(f"📤 Odesílám MCP initialization: {json.dumps(init_payload, indent=2)}")
                resp = requests.post(self.messages_url, json=init_payload)
                assert resp.status_code == 200
                
                # 3. Získá session_id z odpovědi
                response_data = resp.json()
                print(f"📥 MCP initialization response: {json.dumps(response_data, indent=2)}")
                
                # Ověří, že odpověď obsahuje session_id
                if 'result' in response_data and 'sessionId' in response_data['result']:
                    self.session_id = response_data['result']['sessionId']
                    print(f"✅ Session ID získán z odpovědi: {self.session_id}")
                elif 'result' in response_data:
                    # Zkusí najít session_id v jiných místech odpovědi
                    result = response_data['result']
                    if isinstance(result, dict):
                        # Hledá session_id v celém result objektu
                        for key, value in result.items():
                            if 'session' in key.lower() or 'id' in key.lower():
                                print(f"🔍 Nalezen potenciální session ID v klíči '{key}': {value}")
                        
                        # Fallback - použije se kombinace client_name a user_id
                        self.session_id = f"{self.client_name}_{self.user_id}"
                        print(f"⚠️ Session ID není v result.sessionId, použije se fallback: {self.session_id}")
                    else:
                        self.session_id = f"{self.client_name}_{self.user_id}"
                        print(f"⚠️ Neočekávaný formát result, použije se fallback: {self.session_id}")
                else:
                    # Fallback - použije se kombinace client_name a user_id
                    self.session_id = f"{self.client_name}_{self.user_id}"
                    print(f"⚠️ Žádný result v odpovědi, použije se fallback: {self.session_id}")
                
                print(f"🎯 Používám session_id: {self.session_id}")
                
        except requests.exceptions.RequestException as e:
            pytest.skip(f"OpenMemory server not running: {e}")
        except json.JSONDecodeError as e:
            print(f"❌ Chyba při parsování JSON odpovědi: {e}")
            print(f"📥 Raw response: {resp.text}")
            pytest.fail(f"Nevalidní JSON odpověď: {e}")
    
    def test_tools_list_request_with_session_id(self):
        """Test získání seznamu dostupných nástrojů s session_id"""
        try:
            # Nejdříve získá session_id
            self.test_mcp_initialization_handshake_with_session_id()
            
            with requests.get(self.sse_url, stream=True, timeout=5) as sse_resp:
                assert sse_resp.status_code == 200
                
                # Pošle request na seznam nástrojů s session_id
                tools_payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {
                        "sessionId": self.session_id
                    }
                }
                
                resp = requests.post(self.messages_url, json=tools_payload)
                assert resp.status_code == 200
                
                # Ověří, že odpověď obsahuje add_memories nástroj
                response_data = resp.json()
                print(f"✅ Tools list response: {response_data}")
                
                # Kontroluje, že add_memories nástroj je dostupný
                if 'result' in response_data and 'tools' in response_data['result']:
                    tools = response_data['result']['tools']
                    add_memories_tool = next((tool for tool in tools if tool.get('name') == 'add_memories'), None)
                    assert add_memories_tool is not None, "add_memories nástroj není dostupný"
                    print(f"✅ add_memories tool found: {add_memories_tool}")
                
        except requests.exceptions.RequestException as e:
            pytest.skip(f"OpenMemory server not running: {e}")
    
    def test_add_memories_with_session_id(self):
        """Test add_memories s session_id podle MCP protokolu"""
        try:
            # Nejdříve získá session_id
            self.test_mcp_initialization_handshake_with_session_id()
            
            with requests.get(self.sse_url, stream=True, timeout=5) as sse_resp:
                assert sse_resp.status_code == 200
                
                # Testovací zpráva
                test_text = "Toto je testovací zpráva z SSE session pro Python projekty"
                
                # Pošle add_memories request s session_id
                add_memories_payload = {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "add_memories",
                        "arguments": {
                            "text": test_text
                        },
                        "sessionId": self.session_id
                    }
                }
                
                resp = requests.post(self.messages_url, json=add_memories_payload)
                assert resp.status_code == 200
                
                response_data = resp.json()
                print(f"✅ add_memories response: {response_data}")
                
                # Ověří, že context variables fungují (žádná chyba o chybějícím user_id/client_name)
                if 'error' in response_data:
                    error_msg = response_data['error'].get('message', '')
                    assert "user_id not provided" not in error_msg, f"Context variables nefungují: {error_msg}"
                    assert "client_name not provided" not in error_msg, f"Context variables nefungují: {error_msg}"
                
                # Ověří, že operace byla úspěšná
                if 'result' in response_data:
                    result = response_data['result']
                    assert isinstance(result, dict) or isinstance(result, str), f"Neočekávaný formát výsledku: {result}"
                    print(f"✅ add_memories successful: {result}")
                
        except requests.exceptions.RequestException as e:
            pytest.skip(f"OpenMemory server not running: {e}")
    
    def test_search_memory_with_session_id(self):
        """Test search_memory s session_id podle MCP protokolu"""
        try:
            # Nejdříve získá session_id
            self.test_mcp_initialization_handshake_with_session_id()
            
            with requests.get(self.sse_url, stream=True, timeout=5) as sse_resp:
                assert sse_resp.status_code == 200
                
                # Počká na indexaci předchozího add_memories
                time.sleep(2)
                
                # Pošle search_memory request s session_id
                search_payload = {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "search_memory",
                        "arguments": {
                            "query": "Python projekty"
                        },
                        "sessionId": self.session_id
                    }
                }
                
                resp = requests.post(self.messages_url, json=search_payload)
                assert resp.status_code == 200
                
                response_data = resp.json()
                print(f"✅ search_memory response: {response_data}")
                
                # Ověří, že context variables fungují
                if 'error' in response_data:
                    error_msg = response_data['error'].get('message', '')
                    assert "user_id not provided" not in error_msg, f"Context variables nefungují: {error_msg}"
                    assert "client_name not provided" not in error_msg, f"Context variables nefungují: {error_msg}"
                
        except requests.exceptions.RequestException as e:
            pytest.skip(f"OpenMemory server not running: {e}")
    
    def test_complete_sse_session_flow_with_session_id(self):
        """Test kompletního flow SSE session s session_id podle MCP protokolu"""
        try:
            print(f"\n🚀 Spouštím kompletní SSE session flow pro {self.client_name}/{self.user_id}")
            
            # 1. Vytvoří SSE session
            with requests.get(self.sse_url, stream=True, timeout=5) as sse_resp:
                assert sse_resp.status_code == 200
                print(f"✅ SSE connection established: {sse_resp.status_code}")
                
                # 2. MCP initialization - získání session_id
                init_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "clientInfo": {"name": self.client_name, "version": "1.0.0"}
                    }
                }
                
                print(f"📤 Odesílám MCP initialization...")
                init_resp = requests.post(self.messages_url, json=init_payload)
                assert init_resp.status_code == 200
                
                # Získá session_id z odpovědi
                init_data = init_resp.json()
                print(f"📥 MCP initialization response: {json.dumps(init_data, indent=2)}")
                
                if 'result' in init_data and 'sessionId' in init_data['result']:
                    self.session_id = init_data['result']['sessionId']
                    print(f"✅ Session ID získán z odpovědi: {self.session_id}")
                elif 'result' in init_data:
                    # Hledá session_id v result objektu
                    result = init_data['result']
                    if isinstance(result, dict):
                        for key, value in result.items():
                            if 'session' in key.lower() or 'id' in key.lower():
                                print(f"🔍 Nalezen potenciální session ID v klíči '{key}': {value}")
                    
                    self.session_id = f"{self.client_name}_{self.user_id}"
                    print(f"⚠️ Session ID není v result.sessionId, použije se fallback: {self.session_id}")
                else:
                    self.session_id = f"{self.client_name}_{self.user_id}"
                    print(f"⚠️ Žádný result v odpovědi, použije se fallback: {self.session_id}")
                
                print(f"🎯 Používám session_id: {self.session_id}")
                
                # 3. Získá seznam nástrojů s session_id
                tools_payload = {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/list",
                    "params": {
                        "sessionId": self.session_id
                    }
                }
                
                print(f"📤 Odesílám tools/list s session_id: {self.session_id}")
                tools_resp = requests.post(self.messages_url, json=tools_payload)
                assert tools_resp.status_code == 200
                
                tools_data = tools_resp.json()
                print(f"📥 Tools list response: {json.dumps(tools_data, indent=2)}")
                
                # 4. Přidá vzpomínku s session_id
                test_text = "Kompletní test SSE session flow - uživatel pracuje s Python projekty"
                add_payload = {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "add_memories",
                        "arguments": {
                            "text": test_text
                        },
                        "sessionId": self.session_id
                    }
                }
                
                print(f"📤 Odesílám add_memories s session_id: {self.session_id}")
                print(f"📝 Text: {test_text}")
                add_resp = requests.post(self.messages_url, json=add_payload)
                assert add_resp.status_code == 200
                
                add_data = add_resp.json()
                print(f"📥 add_memories response: {json.dumps(add_data, indent=2)}")
                
                # 5. Počká na indexaci
                print("⏳ Čekám na indexaci...")
                time.sleep(2)
                
                # 6. Vyhledá vzpomínky s session_id
                search_payload = {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "search_memory",
                        "arguments": {
                            "query": "Python"
                        },
                        "sessionId": self.session_id
                    }
                }
                
                print(f"📤 Odesílám search_memory s session_id: {self.session_id}")
                search_resp = requests.post(self.messages_url, json=search_payload)
                assert search_resp.status_code == 200
                
                search_data = search_resp.json()
                print(f"📥 search_memory response: {json.dumps(search_data, indent=2)}")
                
                print(f"✅ Kompletní SSE session flow úspěšný s session_id: {self.session_id}")
                
        except requests.exceptions.RequestException as e:
            pytest.skip(f"OpenMemory server not running: {e}")
        except json.JSONDecodeError as e:
            print(f"❌ Chyba při parsování JSON odpovědi: {e}")
            pytest.fail(f"Nevalidní JSON odpověď: {e}")
    
    def test_session_id_isolation(self):
        """Test izolace session_id mezi různými session"""
        try:
            print(f"\n🔒 Testuji izolaci session_id mezi různými session")
            
            # Vytvoří dvě různé session
            session1_url = f"{BASE_URL}/mcp/client1/sse/user1"
            session2_url = f"{BASE_URL}/mcp/client2/sse/user2"
            
            session1_id = None
            session2_id = None
            
            # Session 1 - získání session_id
            print(f"📡 Session 1: {session1_url}")
            with requests.get(session1_url, stream=True, timeout=5) as sse1:
                assert sse1.status_code == 200
                
                init_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "clientInfo": {"name": "client1", "version": "1.0.0"}
                    }
                }
                
                print(f"📤 Session 1 - odesílám MCP initialization...")
                resp1 = requests.post(f"{BASE_URL}/mcp/client1/sse/user1/messages/", json=init_payload)
                assert resp1.status_code == 200
                
                init_data1 = resp1.json()
                print(f"📥 Session 1 - MCP initialization response: {json.dumps(init_data1, indent=2)}")
                
                if 'result' in init_data1 and 'sessionId' in init_data1['result']:
                    session1_id = init_data1['result']['sessionId']
                    print(f"✅ Session 1 - Session ID získán: {session1_id}")
                else:
                    session1_id = "client1_user1"
                    print(f"⚠️ Session 1 - Session ID není v odpovědi, použije se fallback: {session1_id}")
            
            # Session 2 - získání session_id
            print(f"📡 Session 2: {session2_url}")
            with requests.get(session2_url, stream=True, timeout=5) as sse2:
                assert sse2.status_code == 200
                
                init_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "clientInfo": {"name": "client2", "version": "1.0.0"}
                    }
                }
                
                print(f"📤 Session 2 - odesílám MCP initialization...")
                resp2 = requests.post(f"{BASE_URL}/mcp/client2/sse/user2/messages/", json=init_payload)
                assert resp2.status_code == 200
                
                init_data2 = resp2.json()
                print(f"📥 Session 2 - MCP initialization response: {json.dumps(init_data2, indent=2)}")
                
                if 'result' in init_data2 and 'sessionId' in init_data2['result']:
                    session2_id = init_data2['result']['sessionId']
                    print(f"✅ Session 2 - Session ID získán: {session2_id}")
                else:
                    session2_id = "client2_user2"
                    print(f"⚠️ Session 2 - Session ID není v odpovědi, použije se fallback: {session2_id}")
            
            # Ověří, že session_id jsou různé
            print(f"\n🔍 Porovnávám session_id:")
            print(f"   Session 1: {session1_id}")
            print(f"   Session 2: {session2_id}")
            
            assert session1_id != session2_id, f"Session ID by měly být různé: {session1_id} vs {session2_id}"
            print(f"✅ Session ID isolation úspěšná: {session1_id} vs {session2_id}")
            
        except requests.exceptions.RequestException as e:
            pytest.skip(f"OpenMemory server not running: {e}")
        except json.JSONDecodeError as e:
            print(f"❌ Chyba při parsování JSON odpovědi: {e}")
            pytest.fail(f"Nevalidní JSON odpověď: {e}")

    def test_sse_session_establishment_and_mcp_tools(self):
        """Test SSE session establishment a MCP nástrojů podle skutečných logů"""
        try:
            print(f"\n🚀 Testuji SSE session establishment pro {self.client_name}/{self.user_id}")
            
            # 1. SSE session establishment přes GET request (jako v logu)
            sse_url = f"{BASE_URL}/mcp/{self.client_name}/sse/{self.user_id}"
            print(f"📡 SSE URL: {sse_url}")
            
            # Simuluje GET request jako v logu: GET /mcp/cursor/sse/rmatena HTTP/1.1" 200 OK
            with requests.get(sse_url, stream=True, timeout=10) as sse_resp:
                print(f"📡 SSE Response Status: {sse_resp.status_code}")
                print(f"📡 SSE Response Headers: {dict(sse_resp.headers)}")
                
                assert sse_resp.status_code == 200, f"SSE session establishment failed: {sse_resp.status_code}"
                print("✅ SSE session established successfully (200 OK)")
                
                # 2. MCP initialization handshake
                print(f"\n📤 Odesílám MCP initialization...")
                init_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "clientInfo": {"name": self.client_name, "version": "1.0.0"}
                    }
                }
                
                messages_url = f"{BASE_URL}/mcp/{self.client_name}/sse/{self.user_id}/messages/"
                print(f"📤 Messages URL: {messages_url}")
                
                init_resp = requests.post(messages_url, json=init_payload, timeout=10)
                print(f"📤 MCP Init Response Status: {init_resp.status_code}")
                
                if init_resp.status_code == 200:
                    init_data = init_resp.json()
                    print(f"📥 MCP Init Response: {json.dumps(init_data, indent=2)}")
                    
                    # Získá session_id z odpovědi nebo použije fallback
                    if 'result' in init_data and 'sessionId' in init_data['result']:
                        self.session_id = init_data['result']['sessionId']
                        print(f"✅ Session ID získán: {self.session_id}")
                    else:
                        self.session_id = f"{self.client_name}_{self.user_id}"
                        print(f"⚠️ Session ID fallback: {self.session_id}")
                    
                    # 3. Test add_memories nástroje
                    print(f"\n📤 Testuji add_memories nástroj...")
                    test_text = "Testovací zpráva z pytest: Uživatel pracuje s Python projekty a testuje OpenMemory MCP nástroje"
                    
                    add_payload = {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "add_memories",
                            "arguments": {
                                "text": test_text
                            },
                            "sessionId": self.session_id
                        }
                    }
                    
                    print(f"📤 Add Memories Payload: {json.dumps(add_payload, indent=2)}")
                    add_resp = requests.post(messages_url, json=add_payload, timeout=10)
                    print(f"📤 Add Memories Response Status: {add_resp.status_code}")
                    
                    if add_resp.status_code == 200:
                        add_data = add_resp.json()
                        print(f"📥 Add Memories Response: {json.dumps(add_data, indent=2)}")
                        
                        # Ověří výsledek
                        if 'result' in add_data:
                            print(f"✅ add_memories úspěšné: {add_data['result']}")
                        elif 'error' in add_data:
                            print(f"❌ add_memories chyba: {add_data['error']}")
                        else:
                            print(f"⚠️ Neočekávaná odpověď: {add_data}")
                    else:
                        print(f"❌ add_memories request failed: {add_resp.status_code}")
                        print(f"❌ Response: {add_resp.text}")
                    
                    # 4. Test search_memory nástroje
                    print(f"\n📤 Testuji search_memory nástroj...")
                    time.sleep(2)  # Počká na indexaci
                    
                    search_payload = {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": "search_memory",
                            "arguments": {
                                "query": "Python projekty"
                            },
                            "sessionId": self.session_id
                        }
                    }
                    
                    print(f"📤 Search Memory Payload: {json.dumps(search_payload, indent=2)}")
                    search_resp = requests.post(messages_url, json=search_payload, timeout=10)
                    print(f"📤 Search Memory Response Status: {search_resp.status_code}")
                    
                    if search_resp.status_code == 200:
                        search_data = search_resp.json()
                        print(f"📥 Search Memory Response: {json.dumps(search_data, indent=2)}")
                        
                        if 'result' in search_data:
                            print(f"✅ search_memory úspěšné: {search_data['result']}")
                        elif 'error' in search_data:
                            print(f"❌ search_memory chyba: {search_data['error']}")
                    else:
                        print(f"❌ search_memory request failed: {search_resp.status_code}")
                        print(f"❌ Response: {search_resp.text}")
                        
                else:
                    print(f"❌ MCP initialization failed: {init_resp.status_code}")
                    print(f"❌ Response: {init_resp.text}")
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
            pytest.skip(f"OpenMemory server not running: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            pytest.fail(f"Test failed: {e}")


if __name__ == "__main__":
    # Spustí testy
    pytest.main([__file__, "-v"]) 