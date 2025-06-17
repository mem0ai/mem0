# ChatGPT MCP Integration - Deployment Guide

## Overview

This implementation adds ChatGPT Deep Research support to your existing Jean Memory MCP server. ChatGPT users can now search and fetch memories using the exact schema required by OpenAI.

## What We Built

### 🔧 **Cloudflare Worker Updates**
- **New Route**: `/mcp/chatgpt/sse/{user_id}` and `/mcp/chatgpt/messages/{user_id}`
- **Client Detection**: Automatically identifies ChatGPT requests via URL pattern
- **User Mapping**: Uses real Supabase user IDs (same as Claude integration)

### 🎯 **Backend ChatGPT Tools**
- **`search`** - Searches memories using OpenAI's exact schema
- **`fetch`** - Retrieves individual memories by ID with OpenAI format
- **Isolation** - ChatGPT clients only see these two tools (not the full Claude toolset)

### 📋 **Response Format**
```json
// Search Response
{
  "results": [
    {
      "id": "memory-uuid",
      "title": "Memory preview...", 
      "text": "Full memory content",
      "url": null
    }
  ]
}

// Fetch Response  
{
  "id": "memory-uuid",
  "title": "Memory preview...",
  "text": "Complete memory content", 
  "url": null,
  "metadata": {...}
}
```

## Deployment Steps

### 1. Deploy Backend Changes

```bash
# Deploy your backend with the updated mcp_server.py
cd openmemory/api
# Use your existing deployment method (Docker, etc.)
```

### 2. Deploy Cloudflare Worker

```bash
cd cloudflare
npm run deploy  # or your deployment command
```

### 3. Test the Implementation

```bash
# Run the test script with a real user ID
cd scripts
python test-chatgpt-endpoints.py
```

Update the script with:
- Your API URL (if different from https://api.jeanmemory.com)
- A real Supabase user ID that has memories

### 4. Connect to ChatGPT

1. **Get your Supabase User ID** from your existing Claude setup
2. **Add MCP Server in ChatGPT**:
   - URL: `https://api.jeanmemory.com/mcp/chatgpt/sse/{your-user-id}`
   - Replace `{your-user-id}` with your actual Supabase UUID
   - Authentication: None (for now)

3. **Test in ChatGPT Deep Research**:
   - Ask: "Search my memories for programming"
   - Ask: "What do you know about my work preferences?"

## URL Format Comparison

| Client  | URL Format |
|---------|------------|
| Claude  | `/mcp/claude/sse/56092932-7e9f-4934-9bdc-84ed97bc49af` |
| ChatGPT | `/mcp/chatgpt/sse/56092932-7e9f-4934-9bdc-84ed97bc49af` |

## Key Differences from Claude

| Aspect | Claude | ChatGPT |
|--------|--------|---------|
| **Tools** | Full suite (ask_memory, add_memories, search_memory, etc.) | Only `search` and `fetch` |
| **Response Format** | MCP standard with content wrapper | Direct OpenAI schema |
| **Use Case** | General memory assistant | Deep Research only |
| **Schema** | Flexible | Strict OpenAI compliance |

## No Breaking Changes

✅ **Claude integration continues working unchanged**  
✅ **API endpoints continue working unchanged**  
✅ **Existing user data accessible via both interfaces**  
✅ **Zero impact on production Claude users**

## Authentication Roadmap

**Phase 1 (Current)**: No authentication - uses user ID in URL  
**Phase 2 (Future)**: OAuth 2.1 integration per OpenAI recommendations

## Troubleshooting

### Test Endpoints Manually

```bash
# Test tools/list
curl -X POST https://api.jeanmemory.com/mcp/chatgpt/messages/{user_id} \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Test search
curl -X POST https://api.jeanmemory.com/mcp/chatgpt/messages/{user_id} \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search","arguments":{"query":"test"}}}'
```

### Expected Response Validation

Search responses must have:
- `results` array
- Each result must have: `id`, `title`, `text` 
- `url` can be null but must be present

Fetch responses must have:
- `id`, `title`, `text` (required)
- `url`, `metadata` (optional)

### Common Issues

1. **No search results**: User may not have memories yet
2. **Wrong schema**: Check response format matches OpenAI spec exactly  
3. **User not found**: Verify Supabase user ID is correct
4. **URL routing**: Ensure `/mcp/chatgpt/` path is detected properly

## Success Criteria

- ✅ ChatGPT shows only `search` and `fetch` tools
- ✅ Search returns results in OpenAI format
- ✅ Fetch retrieves individual memories
- ✅ User data isolated correctly  
- ✅ Claude integration unaffected

## Next Steps

1. **Test with real users** using their Supabase IDs
2. **Monitor usage** in ChatGPT Deep Research
3. **Implement OAuth 2.1** when ready for production auth
4. **Optimize performance** based on ChatGPT usage patterns 