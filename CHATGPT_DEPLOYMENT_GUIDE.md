# ChatGPT MCP Integration - Complete Deployment & Testing Guide

## 🎯 Overview

**PRODUCTION READY**: ChatGPT Deep Research integration for Jean Memory is now deployed and ready for testing. This implementation adds OpenAI-compliant `search` and `fetch` tools while maintaining 100% compatibility with existing Claude Desktop integration.

### What This Enables
- **ChatGPT Deep Research** can search through user's personal memories
- **Zero Breaking Changes** - Claude Desktop continues working unchanged  
- **Production Scale** - Built on existing Cloudflare + Render infrastructure
- **OpenAI Compliant** - Matches official ChatGPT MCP specifications exactly

---

## 🏗️ Architecture Summary

### URL Structure
```
Claude Desktop:  https://api.jeanmemory.com/mcp/claude/sse/{user_id}
ChatGPT:        https://api.jeanmemory.com/mcp/chatgpt/sse/{user_id}
```

### Client Detection Flow
1. **Cloudflare Worker** detects `/mcp/chatgpt/` in URL → sets `client_name = 'chatgpt'`
2. **Backend** receives `client_name` header → routes to ChatGPT-specific handlers
3. **Response Format** varies by client:
   - **Claude**: MCP standard with content wrapper
   - **ChatGPT**: Direct OpenAI schema

### Tool Isolation
| Client | Tools Available |
|--------|----------------|
| **Claude** | `ask_memory`, `add_memories`, `search_memory`, `list_memories`, `deep_memory_query`, `sync_substack_posts` |
| **ChatGPT** | `search`, `fetch` (OpenAI Deep Research requirement) |

---

## 🚀 Production Deployment Status

### ✅ Deployed Components

#### 1. Backend (Render)
- **URL**: `https://jean-memory-api.onrender.com`
- **New Functions**: 
  - `get_chatgpt_tools_schema()` - Returns only search/fetch tools
  - `handle_chatgpt_search()` - OpenAI-compliant search results
  - `handle_chatgpt_fetch()` - OpenAI-compliant memory retrieval
- **Client Detection**: `client_name_from_header == "chatgpt"`

#### 2. Cloudflare Worker  
- **Domain**: `api.jeanmemory.com`
- **New Routes**: `/mcp/chatgpt/sse/{user_id}` and `/mcp/chatgpt/messages/{user_id}`
- **SSE Transport**: Full MCP protocol compliance
- **User Isolation**: Each user gets isolated Durable Object session

#### 3. Database (Supabase)
- **No Changes**: Uses existing user authentication and memory storage
- **User IDs**: Same Supabase UUIDs work for both Claude and ChatGPT

---

## 🧪 Testing Instructions

### For External Testers

#### Step 1: Get Your User ID
You need your Supabase user ID from the existing Claude integration. This is the UUID in your Claude MCP server URL.

**Example**: If your Claude URL is:
```
https://api.jeanmemory.com/mcp/claude/sse/56092932-7e9f-4934-9bdc-84ed97bc49af
```
Your user ID is: `56092932-7e9f-4934-9bdc-84ed97bc49af`

#### Step 2: Test Backend Directly

```bash
# Test 1: Verify ChatGPT tools are available
curl -X POST https://api.jeanmemory.com/mcp/messages/ \
  -H "Content-Type: application/json" \
  -H "X-User-Id: YOUR_USER_ID_HERE" \
  -H "X-Client-Name: chatgpt" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Expected Response:
# {
#   "jsonrpc": "2.0",
#   "result": {
#     "tools": [
#       {"name": "search", "description": "Searches for resources using the provided query string and returns matching results.", ...},
#       {"name": "fetch", "description": "Retrieves detailed content for a specific resource identified by the given ID.", ...}
#     ]
#   },
#   "id": 1
# }
```

```bash
# Test 2: Search your memories
curl -X POST https://api.jeanmemory.com/mcp/messages/ \
  -H "Content-Type: application/json" \
  -H "X-User-Id: YOUR_USER_ID_HERE" \
  -H "X-Client-Name: chatgpt" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search","arguments":{"query":"programming"}}}'

# Expected Response:
# {
#   "jsonrpc": "2.0",
#   "result": {
#     "results": [
#       {
#         "id": "some-uuid",
#         "title": "I love programming in Python and...",
#         "text": "I love programming in Python and building AI tools",
#         "url": null
#       }
#     ]
#   },
#   "id": 2
# }
```

```bash
# Test 3: Fetch specific memory (use ID from search results)
curl -X POST https://api.jeanmemory.com/mcp/messages/ \
  -H "Content-Type: application/json" \
  -H "X-User-Id: YOUR_USER_ID_HERE" \
  -H "X-Client-Name: chatgpt" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"fetch","arguments":{"id":"MEMORY_ID_FROM_SEARCH"}}}'

# Expected Response:
# {
#   "jsonrpc": "2.0",
#   "result": {
#     "id": "memory-uuid",
#     "title": "Memory preview...",
#     "text": "Complete memory content",
#     "url": null,
#     "metadata": {}
#   },
#   "id": 3
# }
```

#### Step 3: Test SSE Connection

```bash
# Test SSE endpoint (should return event stream)
curl -N https://api.jeanmemory.com/mcp/chatgpt/sse/YOUR_USER_ID_HERE

# Expected Response (SSE stream):
# event: endpoint
# data: /mcp/chatgpt/messages/YOUR_USER_ID_HERE
# 
# : keep-alive
# 
# (continues with keep-alive pings)
```

#### Step 4: Connect to ChatGPT

1. **Open ChatGPT** (requires ChatGPT Plus, Team, or Enterprise)
2. **Go to Settings** → **Data Controls** → **MCP Servers**
3. **Add New Server**:
   - **Name**: Jean Memory
   - **URL**: `https://api.jeanmemory.com/mcp/chatgpt/sse/YOUR_USER_ID_HERE`
   - **Authentication**: None
4. **Save and Test**

#### Step 5: Test in ChatGPT Deep Research

1. **Start Deep Research** in ChatGPT
2. **Add Jean Memory** as a source
3. **Test Queries**:
   - "Search my memories for work preferences"
   - "What do I remember about programming languages?"
   - "Find memories about my recent projects"

---

## 🔧 Automated Testing Scripts

### Production Testing Script

```bash
# Download and run the production test script
cd /tmp
curl -O https://raw.githubusercontent.com/jonathan-politzki/your-memory/main/scripts/test-chatgpt-endpoints.py

# Edit the script to add your user ID
# Change USER_ID = "YOUR_ACTUAL_SUPABASE_USER_ID"

python test-chatgpt-endpoints.py
```

### Expected Test Results
```
🚀 Testing ChatGPT MCP Integration (PRODUCTION)
Base URL: https://api.jeanmemory.com
Test User ID: 56092932-7e9f-4934-9bdc-84ed97bc49af
==================================================
🔍 Testing tools/list for ChatGPT...
Status: 200
Tools returned: ['search', 'fetch']
✅ SUCCESS: ChatGPT gets correct tools (search, fetch)

🔍 Testing search tool...
Status: 200
Found 5 search results
✅ SUCCESS: Search returned results in correct format

🔍 Testing fetch tool with ID: abc123...
Status: 200
✅ SUCCESS: Fetch returned correct format

==================================================
📊 Test Results: 3/3 passed
🎉 All tests passed! ChatGPT MCP integration is working correctly.
```

---

## 🔍 Response Schema Validation

### Search Response Schema
```json
{
  "results": [
    {
      "id": "string (required)",
      "title": "string (required)", 
      "text": "string (required)",
      "url": null | "string (optional but must be present)"
    }
  ]
}
```

### Fetch Response Schema
```json
{
  "id": "string (required)",
  "title": "string (required)",
  "text": "string (required)", 
  "url": null | "string (optional but must be present)",
  "metadata": {} | "object (optional)"
}
```

### Error Response Schema
```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "unknown id"
  },
  "id": "request_id"
}
```

---

## 🚨 Troubleshooting Guide

### Common Issues & Solutions

#### 1. "Tools list returns empty array"
**Cause**: Client detection not working
**Solution**: 
- Verify URL uses `/mcp/chatgpt/` path
- Check `X-Client-Name: chatgpt` header is set
- Test with curl commands above

#### 2. "Search returns no results"
**Cause**: User has no memories or wrong user ID
**Solution**:
- Verify user ID is correct Supabase UUID
- Check user has memories in Claude Desktop first
- Test with different search terms

#### 3. "Wrong response format"
**Cause**: Response doesn't match OpenAI schema
**Solution**:
- Verify `results` field is present in search responses
- Check all required fields (`id`, `title`, `text`) are present
- Ensure `url` field exists (can be null)

#### 4. "SSE connection fails"
**Cause**: Network or routing issue
**Solution**:
- Test SSE endpoint with curl
- Check Cloudflare Worker is deployed
- Verify Durable Objects are working

#### 5. "User not found error"
**Cause**: Invalid user ID or user doesn't exist
**Solution**:
- Double-check user ID from Claude integration
- Ensure user has been created in Supabase
- Test with known working user ID

### Debug Commands

```bash
# Check if backend is responding
curl -I https://jean-memory-api.onrender.com/health

# Check if Cloudflare Worker is routing correctly  
curl -I https://api.jeanmemory.com/mcp/chatgpt/sse/test

# Test with verbose output
curl -v -X POST https://api.jeanmemory.com/mcp/messages/ \
  -H "Content-Type: application/json" \
  -H "X-User-Id: YOUR_USER_ID" \
  -H "X-Client-Name: chatgpt" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

---

## 🔐 Security & Data Isolation

### User Data Protection
- **User Isolation**: Each user can only access their own memories
- **Same Database**: Uses existing Supabase Row Level Security
- **No Cross-Contamination**: ChatGPT and Claude see same user data but via different interfaces

### Authentication Status
- **Current**: User ID in URL (same as Claude Desktop)
- **Future**: OAuth 2.1 integration per OpenAI recommendations
- **Security**: Relies on URL secrecy (same model as Claude)

---

## 📊 Monitoring & Analytics

### Key Metrics to Track
1. **ChatGPT Tool Calls**: Search vs Fetch usage
2. **Response Times**: Backend performance under ChatGPT load
3. **Error Rates**: Failed searches, invalid user IDs
4. **User Adoption**: Unique users connecting ChatGPT

### Logging Points
- Cloudflare Worker: Client detection and routing
- Backend: Tool execution and response formatting
- Database: Memory access patterns

---

## 🔄 Rollback Plan

If issues arise:

1. **Disable ChatGPT Routes**: Comment out `/mcp/chatgpt/` detection in Cloudflare Worker
2. **Backend Rollback**: Deploy previous version without ChatGPT handlers
3. **Zero Impact**: Claude Desktop continues working unchanged

### Rollback Commands
```bash
# Disable ChatGPT in Cloudflare Worker
cd cloudflare/src
# Comment out lines 19-26 in index.ts
npm run deploy

# Backend rollback (if needed)
cd openmemory/api
git checkout previous-commit
# Deploy via your normal process
```

---

## 🎯 Success Criteria Checklist

### ✅ Technical Validation
- [ ] `tools/list` returns exactly `["search", "fetch"]` for ChatGPT clients
- [ ] `search` tool returns OpenAI-compliant response with `results` array
- [ ] `fetch` tool returns OpenAI-compliant response with required fields
- [ ] SSE connection establishes and sends endpoint event
- [ ] User data isolation works correctly
- [ ] Claude Desktop integration remains unchanged

### ✅ User Experience Validation  
- [ ] ChatGPT Deep Research shows Jean Memory as available source
- [ ] Search queries return relevant user memories
- [ ] Citations work correctly in ChatGPT responses
- [ ] No errors or timeouts during normal usage
- [ ] Performance is acceptable (< 5 second response times)

### ✅ Production Readiness
- [ ] All automated tests pass
- [ ] Manual testing completed by multiple users
- [ ] Monitoring and logging in place
- [ ] Rollback plan tested and documented
- [ ] External testers can successfully connect

---

## 👥 External Testing Checklist

**Send this to external testers:**

### Required Information
1. **Your Supabase User ID**: `_________________`
2. **Test URL**: `https://api.jeanmemory.com/mcp/chatgpt/sse/YOUR_USER_ID`
3. **ChatGPT Access**: Plus, Team, or Enterprise account required

### Testing Steps
1. **Run curl tests** (copy commands from Section 🧪)
2. **Connect to ChatGPT** (follow Step 4 instructions)
3. **Test Deep Research** (try example queries)
4. **Report Results** (use checklist above)

### What to Report
- ✅ **Success**: All tests pass, ChatGPT integration works
- ❌ **Failure**: Specific error messages and steps to reproduce
- ⚠️ **Partial**: Some features work, others don't (specify)

---

## 🔮 Next Steps

1. **Gather Feedback** from external testers
2. **Monitor Usage** in production
3. **Implement OAuth 2.1** for better authentication
4. **Scale Optimization** based on ChatGPT usage patterns
5. **Feature Expansion** (if OpenAI adds more MCP capabilities)

---

## 📞 Support & Contact

For testing issues or questions:
- **GitHub Issues**: [Repository Issues](https://github.com/jonathan-politzki/your-memory/issues)
- **Documentation**: This guide + `CHATGPT_MCP_IMPLEMENTATION_PLAN.md`
- **Test Scripts**: `/scripts/test-chatgpt-*.py`

**Happy Testing! 🚀** 