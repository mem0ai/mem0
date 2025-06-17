# ChatGPT MCP Integration - Clean Implementation Plan

## Why We're Doing This

ChatGPT now supports custom MCP (Model Context Protocol) connectors for "Deep Research" functionality. This allows ChatGPT's 400+ million users to search through their personal Jean Memory data during research sessions, providing massive value and distribution for our product.

## What We're Building

A ChatGPT-compatible MCP server that exposes exactly two tools:
- `search` - Find memories using natural language queries
- `fetch` - Retrieve full memory content by ID for citations

**Constraint**: ChatGPT Deep Research only supports these two tools - no adding memories, just searching existing ones.

## Current Implementation Status

Based on the git diff, we have:

### ✅ Cloudflare Worker (Adapter Layer)
- **Path**: `/mcp/chatgpt/sse` and `/mcp/chatgpt/messages`
- **Detection**: Recognizes ChatGPT requests via client name
- **Tool Mapping**: Maps ChatGPT's `search`/`fetch` to our existing `ask_memory`/`search_memory`
- **Response Format**: Converts our responses to ChatGPT's required schema

### ✅ Backend MCP Tools
- **ChatGPT Detection**: Uses User-Agent and client context to identify ChatGPT requests
- **Tool Isolation**: Only exposes `search` and `fetch` tools to ChatGPT clients
- **Schema Compliance**: Tools match OpenAI's exact specifications

### 🔧 Missing Pieces
1. Backend `search` and `fetch` tool implementations with correct schemas
2. Proper response formatting for ChatGPT citations
3. Authentication handling (API key validation)

## Implementation Plan

### Step 1: Complete Backend Tool Implementation

Add the missing `search` and `fetch` tools to `openmemory/api/app/mcp_server.py`:

```python
def get_chatgpt_tools_schema():
    """Returns ONLY search and fetch tools for ChatGPT clients"""
    return [
        {
            "name": "search",
            "description": "Searches for resources using the provided query string and returns matching results.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"]
            }
        },
        {
            "name": "fetch", 
            "description": "Retrieves detailed content for a specific resource identified by the given ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "ID of the resource to fetch."}
                },
                "required": ["id"]
            }
        }
    ]

async def handle_chatgpt_search(query: str, user_id: str):
    """Handle ChatGPT search tool - returns OpenAI-compliant format"""
    # Use existing search logic
    results = await _search_memory_unified_impl(user_id, query, limit=10)
    
    # Format for ChatGPT
    return {
        "results": [
            {
                "id": str(result["id"]),
                "title": result["memory"][:100] + "..." if len(result["memory"]) > 100 else result["memory"],
                "text": result["memory"],
                "url": None
            } for result in results
        ]
    }

async def handle_chatgpt_fetch(memory_id: str, user_id: str):
    """Handle ChatGPT fetch tool - returns single memory details"""
    # Use existing get memory logic
    result = await _get_memory_details_impl(user_id, memory_id)
    
    # Format for ChatGPT
    return {
        "id": str(result["id"]),
        "title": result["memory"][:100] + "..." if len(result["memory"]) > 100 else result["memory"],
        "text": result["memory"],
        "url": None,
        "metadata": result.get("metadata", {})
    }
```

### Step 2: Fix Authentication

Currently hardcoded to a test user ID. Need to:
1. Extract API key from `Authorization: Bearer` header
2. Validate API key against backend
3. Map to correct user_id

### Step 3: Clean Up Cloudflare Worker

The current worker has complex tool mapping. Simplify it to:
1. Detect ChatGPT requests
2. Validate auth token
3. Pass `search`/`fetch` calls directly to backend
4. Let backend handle the tool logic

### Step 4: Testing

1. Deploy to staging Cloudflare environment
2. Test with ChatGPT Enterprise connector:
   - URL: `https://api.jeanmemory.com/mcp/chatgpt/sse` 
   - Auth: API key as Bearer token
3. Validate search and fetch work correctly
4. Ensure existing Claude integration unaffected

## Authentication Strategy

**Phase 1 - Demo/Testing (Current)**:
- No authentication required for initial testing
- Uses hardcoded demo user with sample memories
- Allows immediate ChatGPT integration testing

**Phase 2 - Production Authentication**:
Based on OpenAI's official documentation, they recommend OAuth 2.1:
> "We recommend using OAuth and dynamic client registration"

- **Recommended**: Full OAuth 2.1 provider for seamless user experience
- **Alternative**: Bearer token authentication (if ChatGPT supports it)
- **User Flow**: After connecting server, users get OAuth flow to authenticate with Jean Memory

**Note**: OpenAI's docs emphasize OAuth as the recommended approach for production use.

## Success Criteria

- ✅ ChatGPT can search user's memories
- ✅ Search results appear with proper citations
- ✅ Fetch tool retrieves full memory content
- ✅ Only authorized users can access their own data
- ✅ Existing Claude integration continues working
- ✅ No impact on production systems

## Deployment

1. **Backend**: Add new tools to `mcp_server.py`, deploy to production API
2. **Cloudflare**: Update worker with simplified logic, deploy to production
3. **Documentation**: Create user setup guide

## Timeline

- **Day 1**: Complete backend tool implementations
- **Day 2**: Fix authentication and deploy to staging  
- **Day 3**: End-to-end testing with ChatGPT
- **Day 4**: Production deployment and user documentation

This approach leverages our existing infrastructure while adding the minimal changes needed for ChatGPT compatibility.

## Building From Scratch (Starting from Main Branch)

To implement this cleanly from the main branch without existing complexity:

### File Changes Required

#### 1. Cloudflare Worker Changes

**File**: `cloudflare/src/index.ts`
```typescript
// Add ChatGPT route detection (around line 20, after existing route parsing)
// Special handling for ChatGPT - detect /mcp/chatgpt/* routes
if (pathParts[1] === 'chatgpt') {
    client_name = 'chatgpt';
    // For initial testing without auth, use a demo user ID
    user_id = 'demo_chatgpt_user'; 
    endpoint = pathParts[2]; // 'sse' or 'messages'
}
```

**File**: `cloudflare/src/mcp-session.ts`
```typescript
// Add ChatGPT tool handling (in handleMessages method)
// 1. Override tools/list for ChatGPT to only show search/fetch
if (message.method === "tools/list" && this.clientName === "chatgpt") {
    const chatgptTools = {
        jsonrpc: "2.0",
        id: message.id,
        result: {
            tools: [
                {
                    name: "search",
                    description: "Search for memories using natural language queries",
                    inputSchema: {
                        type: "object",
                        properties: {
                            query: { type: "string", description: "Search query" }
                        },
                        required: ["query"]
                    }
                },
                {
                    name: "fetch", 
                    description: "Retrieve full memory content by ID",
                    inputSchema: {
                        type: "object",
                        properties: {
                            id: { type: "string", description: "Memory ID" }
                        },
                        required: ["id"]
                    }
                }
            ]
        }
    };
    this.sendSseResponse(chatgptTools, message.id);
    return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
}

// 2. Pass search/fetch tools directly to backend (no mapping needed)
// Let backend handle ChatGPT tool calls directly
```

#### 2. Backend Changes

**File**: `openmemory/api/app/mcp_server.py`

Add these functions:
```python
def get_chatgpt_tools_schema():
    """Returns ONLY search and fetch tools for ChatGPT clients - OpenAI compliant schemas"""
    return [
        {
            "name": "search",
            "description": "Searches the user's personal memory bank for resources using a natural language query string and returns matching results. Use this to find relevant memories based on topics, concepts, or specific information the user has stored.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."}
                },
                "required": ["query"]
            }
        },
        {
            "name": "fetch",
            "description": "Retrieves detailed content for a specific memory resource identified by the given ID.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "ID of the resource to fetch."}
                },
                "required": ["id"]
            }
        }
    ]

async def handle_chatgpt_search(user_id: str, query: str):
    """ChatGPT search implementation - returns OpenAI compliant format"""
    try:
        # Use existing search logic
        results = await _search_memory_unified_impl(user_id, query, limit=10)
        
        # Format for ChatGPT schema - must match OpenAI's exact specification
        formatted_results = []
        for result in results:
            memory_text = result.get("memory", "")
            formatted_results.append({
                "id": str(result.get("id", "")),
                "title": memory_text[:100] + "..." if len(memory_text) > 100 else memory_text,
                "text": memory_text,
                "url": None  # Required by OpenAI spec, needed for citations
            })
        
        return {"results": formatted_results}
    except Exception as e:
        logger.error(f"ChatGPT search error: {e}")
        return {"results": []}

async def handle_chatgpt_fetch(user_id: str, memory_id: str):
    """ChatGPT fetch implementation - returns OpenAI compliant format"""
    try:
        # Use existing get memory logic  
        result = await _get_memory_details_impl(user_id, memory_id)
        
        # Format for ChatGPT schema - must match OpenAI's exact specification
        memory_text = result.get("memory", "")
        return {
            "id": str(result.get("id", memory_id)),
            "title": memory_text[:100] + "..." if len(memory_text) > 100 else memory_text,
            "text": memory_text,  # Complete textual content as per OpenAI spec
            "url": None,  # Required by OpenAI spec, needed for citations
            "metadata": result.get("metadata", {})  # Optional additional context
        }
    except Exception as e:
        logger.error(f"ChatGPT fetch error: {e}")
        raise ValueError(f"unknown id")  # OpenAI spec expects this exact error message
```

Modify the `handle_post_message` function:
```python
elif method_name == "tools/list":
    # Detect ChatGPT requests
    user_agent = request.headers.get('user-agent', '').lower()
    
    # Check for ChatGPT client (simple detection for now)
    is_chatgpt = 'chatgpt' in user_agent or request.url.path.find('/chatgpt/') != -1
    
    if is_chatgpt:
        tools_to_show = get_chatgpt_tools_schema()
    elif is_api_key_path:
        tools_to_show = get_api_tools_schema()
    else:
        tools_to_show = get_original_tools_schema()

elif method_name == "tools/call":
    tool_name = params.get("name")
    tool_args = params.get("arguments", {})
    
    # Handle ChatGPT tools
    if tool_name == "search":
        result = await handle_chatgpt_search(user_id, tool_args.get("query", ""))
        return JSONResponse(content={"jsonrpc": "2.0", "id": request_id, "result": result})
    
    elif tool_name == "fetch":
        try:
            result = await handle_chatgpt_fetch(user_id, tool_args.get("id", ""))
            return JSONResponse(content={"jsonrpc": "2.0", "id": request_id, "result": result})
        except ValueError as e:
            return JSONResponse(content={"jsonrpc": "2.0", "id": request_id, "error": {"code": -1, "message": str(e)}})
    
    # ... rest of existing tool handling
```

#### 3. Demo User Setup

**File**: Create `scripts/setup-chatgpt-demo.sql`
```sql
-- Create a demo user for ChatGPT testing
INSERT INTO auth.users (id, email) 
VALUES ('demo_chatgpt_user', 'chatgpt-demo@jeanmemory.com')
ON CONFLICT (id) DO NOTHING;

-- Add some demo memories for testing
INSERT INTO memories (id, user_id, memory, created_at)
VALUES 
  (gen_random_uuid(), 'demo_chatgpt_user', 'I love working on AI projects and building innovative tools', NOW()),
  (gen_random_uuid(), 'demo_chatgpt_user', 'My favorite programming languages are Python and TypeScript', NOW()),
  (gen_random_uuid(), 'demo_chatgpt_user', 'I work at a startup building memory and AI tools', NOW())
ON CONFLICT DO NOTHING;
```

### Implementation Steps

#### Step 1: Backend Implementation (Day 1)
```bash
# 1. Start from clean main branch
git checkout main
git pull origin main
git checkout -b feature/chatgpt-mcp-clean

# 2. Add ChatGPT tools to backend
# Edit openmemory/api/app/mcp_server.py with changes above

# 3. Test backend locally
cd openmemory/api
python -m uvicorn app.main:app --reload --port 8000

# 4. Test ChatGPT tools locally
curl -X POST http://localhost:8000/mcp/messages \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

#### Step 2: Cloudflare Worker (Day 1)
```bash
# 1. Edit cloudflare/src/index.ts and mcp-session.ts with changes above

# 2. Deploy to staging first
cd cloudflare
npm run deploy-staging  # or whatever your staging command is

# 3. Test staging worker
curl https://staging-api.jeanmemory.com/mcp/chatgpt/messages \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

#### Step 3: Production Testing (Day 2)
```bash
# 1. Deploy backend to production
cd openmemory
# Deploy however you currently deploy (Docker, etc.)

# 2. Deploy Cloudflare worker to production  
cd cloudflare
npm run deploy

# 3. Test with ChatGPT Enterprise
# URL: https://api.jeanmemory.com/mcp/chatgpt/sse
# Auth: None (using demo user for now)
```

#### Step 4: Validation (Day 2)
- ✅ ChatGPT connector shows only `search` and `fetch` tools
- ✅ Search returns properly formatted results  
- ✅ Fetch retrieves individual memory details
- ✅ Existing Claude integration still works unchanged
- ✅ Demo user has searchable content

#### Step 5: Add Authentication (Day 3)
Once basic functionality works:
```bash
# 1. Add Bearer token extraction in Cloudflare worker
# 2. Add API key validation endpoint in backend
# 3. Map API keys to real user IDs
# 4. Update ChatGPT connector to require API key
```

### Testing URLs & Validation

- **ChatGPT MCP Server**: `https://api.jeanmemory.com/mcp/chatgpt/sse`
- **Demo User**: No auth required initially (hardcoded demo user)
- **Existing Claude**: `https://api.jeanmemory.com/mcp/claude/sse/{user_id}` (unchanged)

### Pre-Production Testing

Before connecting to ChatGPT, use OpenAI's API Playground to validate:
1. **Tool Discovery**: Test `tools/list` endpoint returns only `search` and `fetch`
2. **Search Functionality**: Test search with various queries
3. **Fetch Functionality**: Test fetch with memory IDs returned from search
4. **Recommended**: Test with GPT-4 or o1-preview/o1-mini models in Playground

### Safety Measures

1. **Zero Risk**: Changes only add new routes, don't modify existing ones
2. **Feature Detection**: ChatGPT tools only appear for ChatGPT clients  
3. **Demo User**: Isolated test data, no access to real user data initially
4. **Rollback Plan**: Remove ChatGPT routes if issues arise
5. **Monitoring**: Use existing logging to track ChatGPT requests

This approach gets ChatGPT working quickly while keeping all existing functionality intact. 