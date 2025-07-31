# SSE Session Tests pro OpenMemory MCP

Tento adresář obsahuje testy pro SSE (Server-Sent Events) session funkcionalitu v OpenMemory MCP serveru podle MCP protokolu.

## Přehled testů

### 1. `test_sse_session_add_memories.py` - Integrační testy
**Požadavky:** Spuštěný OpenMemory server na `http://localhost:8765`

Testuje kompletní flow podle MCP protokolu:
- ✅ Vytvoření SSE session
- ✅ MCP initialization handshake s získáním session_id
- ✅ Získání seznamu nástrojů s session_id
- ✅ Volání `add_memories` s session_id
- ✅ Volání `search_memory` s session_id
- ✅ Kompletní SSE session flow s session_id
- ✅ Izolace session_id mezi session

### 2. `test_sse_session_unit.py` - Unit testy
**Požadavky:** Žádné externí závislosti

Testuje:
- ✅ Formát MCP zpráv s session_id
- ✅ Context variables logiku
- ✅ URL formáty
- ✅ Error handling
- ✅ Simulace SSE flow s session_id
- ✅ Validace session_id

## Spuštění testů

### Unit testy (bez serveru)
```bash
# Spustí pouze unit testy
pytest tests/test_sse_session_unit.py -v

# Nebo
python tests/test_sse_session_unit.py
```

### Integrační testy (se serverem)
```bash
# Nejdříve spusťte OpenMemory server
cd openmemory
docker-compose up -d

# Pak spusťte integrační testy
pytest tests/test_sse_session_add_memories.py -v

# Nebo
python tests/test_sse_session_add_memories.py
```

### Všechny testy
```bash
# Spustí všechny SSE testy
pytest tests/test_sse_session_*.py -v
```

## MCP Protokol s Session ID

### 1. SSE Session Establishment
```python
# Testuje vytvoření SSE spojení
GET /mcp/{client_name}/sse/{user_id}
```

### 2. Context Variables Setup
```python
# Testuje nastavení context variables při SSE connection
user_id_var.set(user_id)
client_name_var.set(client_name)
```

### 3. MCP Protocol Flow s Session ID

#### A) Initialization - získání session_id
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "clientInfo": {"name": "testclient", "version": "1.0.0"}
    }
}
```

**Očekávaná odpověď:**
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "sessionId": "test_session_123"
    }
}
```

#### B) Tools list s session_id
```json
{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {
        "sessionId": "test_session_123"
    }
}
```

#### C) Tool call s session_id
```json
{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
        "name": "add_memories",
        "arguments": {"text": "Test message"},
        "sessionId": "test_session_123"
    }
}
```

### 4. Session ID Isolation
```python
# Session 1: /mcp/client1/sse/user1 -> sessionId: "session_1_123"
# Session 2: /mcp/client2/sse/user2 -> sessionId: "session_2_456"
# Každá session má vlastní session_id
```

## Očekávané výsledky

### Úspěšný test
```
✅ SSE connection established: 200
✅ MCP initialization response: {...}
✅ Session ID získán: test_session_123
✅ Tools list response: {...}
✅ add_memories tool found: {...}
✅ add_memories response: {...}
✅ add_memories successful: {...}
✅ search_memory response: {...}
✅ Kompletní SSE session flow úspěšný s session_id: test_session_123
✅ Session ID isolation úspěšná: session_1_123 vs session_2_456
```

### Chybové stavy
- **Server není spuštěný:** Test se přeskočí s `pytest.skip()`
- **Context variables nefungují:** Chyba "user_id not provided" nebo "client_name not provided"
- **Session ID chybí:** Chyba "session_id not provided"
- **MCP protokol chyba:** Nevalidní JSON-RPC formát

## Debugging

### Logy OpenMemory serveru
```bash
# Sledujte logy serveru
docker-compose logs -f openmemory-mcp
```

### Testovací výstup
```bash
# Verbose výstup
pytest tests/test_sse_session_add_memories.py -v -s

# S logy
pytest tests/test_sse_session_add_memories.py -v -s --log-cli-level=DEBUG
```

### Manuální testování
```bash
# Test SSE connection
curl -N http://localhost:8765/mcp/testclient/sse/testuser

# Test MCP initialization
curl -X POST http://localhost:8765/mcp/testclient/sse/testuser/messages/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {"tools": {}},
      "clientInfo": {"name": "testclient", "version": "1.0.0"}
    }
  }'

# Test add_memories s session_id
curl -X POST http://localhost:8765/mcp/testclient/sse/testuser/messages/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "add_memories",
      "arguments": {"text": "Test message"},
      "sessionId": "test_session_123"
    }
  }'
```

## Klíčové změny v MCP protokolu

### Před (bez session_id):
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "add_memories",
        "arguments": {"text": "Test"}
    }
}
```

### Po (s session_id):
```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "add_memories",
        "arguments": {"text": "Test"},
        "sessionId": "test_session_123"
    }
}
```

## Výhody Session ID

1. **Izolace session** - každá SSE session má vlastní session_id
2. **Bezpečnost** - session_id zajišťuje, že operace probíhají v rámci správné session
3. **Sledovatelnost** - lze sledovat operace podle session_id
4. **MCP kompatibilita** - dodržuje MCP protokol specifikaci
5. **Context variables** - session_id doplňuje context variables pro lepší izolaci 