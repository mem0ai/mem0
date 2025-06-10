# MCP (Model Context Protocol) Compatibility

This document explains the MCP implementation in Jean Memory and the fixes applied to ensure seamless local development.

## Overview

Jean Memory supports MCP to integrate with AI applications like Claude Desktop. The implementation uses Server-Sent Events (SSE) for real-time communication between the client and server.

## Architecture

### Endpoints

1. **SSE Connection**: `GET /mcp/{client_name}/sse/{user_id}`
   - Establishes persistent connection for receiving responses
   - Sends endpoint information and heartbeat events
   - Uses in-memory message queues for response delivery

2. **Messages**: `POST /mcp/{client_name}/messages/{user_id}`
   - Handles MCP tool calls and protocol messages
   - Sends responses through the SSE queue (not HTTP response)
   - Supports all standard MCP methods

### Tool Compatibility

Both local and production environments expose identical tools:
- `ask_memory` - Fast conversational memory search
- `add_memories` - Store new information
- `search_memory` - Keyword-based search
- `list_memories` - Browse stored memories
- `deep_memory_query` - Comprehensive analysis

## Local Development Fixes

### Issue 1: SSL Connection Errors

**Problem**: Local Docker Qdrant doesn't use SSL, but cloud configuration had `QDRANT_API_KEY` set, causing mem0 library to attempt SSL connections.

**Solution**: 
- Setup scripts automatically clear `QDRANT_API_KEY=""` for local development
- Updated `env.example` with clear documentation
- Added configuration validation

**Code Location**: `openmemory/api/app/utils/memory.py` lines 41-48

### Issue 2: SSE Response Mechanism

**Problem**: supergateway expects responses through SSE stream, but initial implementation returned HTTP responses directly.

**Solution**:
- Implemented in-memory message queue system
- Messages endpoint sends responses to SSE queue
- SSE endpoint streams queued responses to client

**Code Location**: `openmemory/api/app/mcp_server.py` lines 1284-1456

### Issue 3: Tool Definition Inconsistency

**Problem**: Local SSE endpoints had simplified tool definitions different from production.

**Solution**:
- Unified tool definitions across both endpoints
- Used comprehensive tool descriptions for all environments
- Ensured feature parity between local and production

## Configuration

### Local Development
```bash
# Environment settings for local Docker setup
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=                    # Empty - no SSL needed
USER_ID=00000000-0000-0000-0000-000000000001
```

### Claude Desktop Configuration
```json
{
  "mcpServers": {
    "local-memory": {
      "command": "npx",
      "args": ["supergateway", "sse://http://localhost:8765/mcp/claude/sse/local_dev_user"]
    }
  }
}
```

### Production Configuration
```bash
# Environment settings for cloud deployment
QDRANT_HOST=your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your_cloud_api_key   # Required for cloud Qdrant
SUPABASE_URL=https://your-project.supabase.co
# ... other production settings
```

## Testing MCP Connection

### Verify SSE Endpoint
```bash
curl -N http://localhost:8765/mcp/claude/sse/local_dev_user
```
Expected output:
```
event: endpoint
data: /mcp/claude/messages/local_dev_user

event: heartbeat
data: {"timestamp": "2024-01-01T00:00:00.000Z"}
```

### Test Tool Call
```bash
curl -X POST http://localhost:8765/mcp/claude/messages/local_dev_user \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'
```
Expected response: `{"status":"sent_via_sse"}`

### Verify Memory Tools
```bash
curl -X POST http://localhost:8765/mcp/claude/messages/local_dev_user \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"list_memories","arguments":{"limit":5}},"id":2}'
```

## Troubleshooting

### SSL Errors in Memory Tools
```
Error: [SSL: WRONG_VERSION_NUMBER] wrong version number (_ssl.c:1010)
```
**Fix**: Ensure `QDRANT_API_KEY=""` (empty) in `api/.env` and restart backend

### MCP Connection Timeouts
```
Error: MCP error -32001: Request timed out
```
**Fix**: Check that responses are being sent through SSE queue, not HTTP responses

### Tool Not Found Errors
```
Error: Tool 'tool_name' not found
```
**Fix**: Ensure tool registry includes all required tools and they're properly imported

## Implementation Notes

### Message Queue System
- Uses `asyncio.Queue()` for each SSE connection
- Connection ID format: `{client_name}_{user_id}`
- Automatic cleanup when SSE connection closes
- 10-second timeout with heartbeat fallback

### Error Handling
- Graceful fallback for missing environment variables
- Proper JSON-RPC error responses
- Context variable cleanup in finally blocks

### Authentication
- Local development uses fixed UUID: `00000000-0000-0000-0000-000000000001`
- Production uses Supabase authentication
- Context variables for request-scoped user identification

## Future Improvements

1. **Persistent Storage**: Consider Redis for message queues in production
2. **Load Balancing**: SSE sticky sessions for multi-instance deployments
3. **Monitoring**: Add metrics for MCP connection health
4. **Rate Limiting**: Implement per-user rate limits for tool calls 