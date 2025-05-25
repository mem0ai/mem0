# OpenMemory Integration Architecture Plan

## Current System Understanding

### Memory Flow
1. **Memory Creation**:
   - UI creates memories with `app_name: "openmemory"`
   - MCP tools create memories with `app_name: <client_name>` (e.g., "cursor", "claude")
   - Apps are auto-created via `get_user_and_app()` when memories are created

2. **Storage**:
   - **mem0**: Vector storage for semantic search
   - **PostgreSQL**: Metadata, state, relationships, access logs
   - Each memory has: content, app_id, user_id, state, categories, metadata

3. **MCP Integration**:
   - Tools run in context with `user_id` and `client_name`
   - Tools use `memory_client` (mem0) and SQL database
   - Access via `/mcp/{client_name}/sse/{user_id}`

## Proposed Integration Approach

### 1. Content Source Integration (Substack, Medium, Twitter)

**Key Insight**: These should be MCP tools that fetch and store content as memories, NOT separate API endpoints.

#### Implementation Strategy:
1. **Add new MCP tools** in `mcp_server.py`:
   - `sync_substack_posts(substack_url: str, max_posts: int = 20)`
   - `sync_medium_posts(medium_username: str, max_posts: int = 20)`
   - `sync_twitter_posts(twitter_handle: str, max_posts: int = 50)`

2. **Memory Storage Pattern**:
   ```python
   # Each post/tweet becomes a memory with:
   - app_name: "substack" / "medium" / "twitter"
   - content: Full text of post/tweet
   - metadata: {
       "source_url": "...",
       "author": "...",
       "published_date": "...",
       "title": "..." (for articles),
       "source_type": "article" / "tweet"
   }
   ```

3. **Deduplication**: Check `metadata.source_url` before creating

### 2. Gemini Long-Context Tool

**Purpose**: Query across ALL user memories with Gemini's long context window

#### Implementation:
1. **New MCP tool**: `query_all_memories_gemini(query: str)`
2. **Process**:
   - Fetch ALL user memories from SQL (not just mem0 search results)
   - Format into structured context
   - Send to Gemini 2.0 Flash with the query
   - Return synthesized answer

### 3. UI Integration

**No UI changes needed initially** because:
- Apps auto-appear when memories are created
- Users can pause/resume apps
- Memory counts update automatically

**Future enhancement**: Add "Sync" button in app details to trigger MCP tools

## Implementation Steps

### Phase 1: MCP Tools (Backend Only)
1. Add Substack scraper utility (adapt from your existing code)
2. Add MCP tool for Substack sync
3. Add Gemini service utility
4. Add MCP tool for Gemini queries
5. Test via MCP client

### Phase 2: Additional Sources
1. Add Medium scraper utility
2. Add Twitter scraper utility (using Apify)
3. Add corresponding MCP tools

### Phase 3: UI Enhancements (Optional)
1. Add sync buttons in app management
2. Add last sync timestamp display
3. Add configuration for sync frequency

## Key Benefits of This Approach

1. **Fits existing architecture**: No new models, routers, or major changes
2. **Leverages MCP**: External tools can trigger syncs
3. **Automatic app management**: Apps created/managed automatically
4. **State control**: Users can pause any source
5. **Unified memory system**: All content searchable together

## Example Usage

```python
# In Claude/Cursor via MCP:
"Sync my latest Substack posts"
-> Calls sync_substack_posts("https://myname.substack.com")
-> Creates memories with app_name="substack"
-> App appears in UI automatically

"What themes have I been writing about across all my content?"
-> Calls query_all_memories_gemini("analyze themes...")
-> Gemini processes ALL memories
-> Returns comprehensive analysis
```

## Next Steps

1. Start with Substack MCP tool (simplest)
2. Add Gemini query tool
3. Test end-to-end flow
4. Add Medium and Twitter 