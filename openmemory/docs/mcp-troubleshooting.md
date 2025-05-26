# MCP Connection Troubleshooting Guide

## Common Issues and Solutions

### Issue: MCP Tools Stop Working After Extended Use

**Symptoms:**
- Memory tools work initially but stop responding after Claude/Cursor has been open for a while
- Requires restarting the client application to restore functionality
- Tools appear in the interface but calls fail or timeout

**Root Causes:**
1. SSE connection timeouts
2. Session ID expiration
3. Transport state corruption
4. Network connectivity issues

### Solutions

#### 1. Improved Claude Desktop Configuration

For **Windows**, edit `%APPDATA%\Claude\claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jean-memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-everything"],
      "env": {
        "MCP_SERVER_URL": "http://localhost:8765/mcp/claude/sse/your-username",
        "MCP_CONNECTION_TIMEOUT": "300000",
        "MCP_HEARTBEAT_INTERVAL": "30000",
        "MCP_RETRY_ATTEMPTS": "3",
        "MCP_RETRY_DELAY": "5000"
      }
    }
  }
}
```

For **macOS**, edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "jean-memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-everything"],
      "env": {
        "MCP_SERVER_URL": "http://localhost:8765/mcp/claude/sse/your-username",
        "MCP_CONNECTION_TIMEOUT": "300000",
        "MCP_HEARTBEAT_INTERVAL": "30000",
        "MCP_RETRY_ATTEMPTS": "3",
        "MCP_RETRY_DELAY": "5000"
      }
    }
  }
}
```

#### 2. Alternative: Direct SSE Configuration

If the above doesn't work, try configuring as a direct SSE server:

```json
{
  "mcpServers": {
    "jean-memory": {
      "type": "sse",
      "url": "http://localhost:8765/mcp/claude/sse/your-username",
      "headers": {
        "User-Agent": "Claude-Desktop-MCP-Client",
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache"
      },
      "timeout": 300000,
      "retryInterval": 30000
    }
  }
}
```

#### 3. Connection Health Monitoring

You can check your connection health by visiting:
```
http://localhost:8765/mcp/health/claude/your-username
```

This will show:
- Connection status
- Last heartbeat time
- Connection age
- Health status

#### 4. Server-Side Improvements

The Jean Memory server now includes:

- **Heartbeat mechanism**: Sends periodic heartbeat messages every 30 seconds
- **Connection cleanup**: Automatically removes stale connections after 2 minutes
- **Better error handling**: Graceful connection recovery
- **Health monitoring**: Real-time connection status

#### 5. Debugging Steps

1. **Check server logs**: Look for connection errors or timeouts
2. **Monitor heartbeats**: Verify heartbeat messages are being sent/received
3. **Test connection health**: Use the health endpoint to check status
4. **Restart sequence**: 
   - First try refreshing in Claude/Cursor
   - If that fails, restart the client application
   - As last resort, restart the Jean Memory server

#### 6. Prevention Tips

- **Regular breaks**: Close and reopen Claude/Cursor periodically during long sessions
- **Monitor memory usage**: High memory usage can cause connection issues
- **Network stability**: Ensure stable internet connection
- **Firewall settings**: Make sure localhost connections aren't blocked

#### 7. Windows-Specific Issues

- **Antivirus interference**: Some antivirus software blocks localhost connections
- **Windows Firewall**: May need to allow Node.js/npx through firewall
- **WSL compatibility**: If using WSL, ensure proper port forwarding

#### 8. Emergency Recovery

If connections are completely broken:

1. Stop Jean Memory server: `Ctrl+C` in terminal
2. Close Claude Desktop completely
3. Clear Claude's cache (optional):
   - Windows: Delete `%APPDATA%\Claude\Cache`
   - macOS: Delete `~/Library/Caches/Claude`
4. Restart Jean Memory server: `make up`
5. Restart Claude Desktop
6. Test connection with a simple memory operation

### Expected Behavior After Fixes

- Connections should remain stable for hours without requiring restarts
- Heartbeat messages will keep connections alive
- Automatic recovery from temporary network issues
- Better error messages when connections do fail

### Still Having Issues?

If problems persist:

1. Check the Jean Memory server logs for specific error messages
2. Verify your username in the MCP URL matches your actual user ID
3. Ensure Jean Memory server is running on the correct port (8765)
4. Try using a different client (Cursor) to isolate the issue
5. Consider using the HTTP-based MCP tools as a fallback 