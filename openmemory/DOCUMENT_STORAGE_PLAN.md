# Document Storage Implementation Plan

## Goal
Add support for storing full documents (essays, code files) without breaking existing memory functionality.

## Design Principles
1. **Backward Compatibility**: Existing memory operations must continue working
2. **Separation of Concerns**: Documents are different from memories
3. **Rollback Safety**: Each step should be reversible
4. **Two-Tier System**: Quick access to summaries, on-demand access to full content

## Implementation Approach

### Phase 1: Database Schema (Safest Approach)
Create a new `documents` table that works alongside existing tables:

```sql
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    app_id UUID NOT NULL REFERENCES apps(id),
    
    -- Document info
    title VARCHAR NOT NULL,
    source_url VARCHAR,
    document_type VARCHAR NOT NULL, -- 'substack', 'medium', 'code', 'markdown'
    
    -- Full content
    content TEXT NOT NULL,
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_documents_user_app (user_id, app_id),
    INDEX idx_documents_type (document_type),
    INDEX idx_documents_created (created_at)
);

-- Link table between documents and memories
CREATE TABLE document_memories (
    document_id UUID REFERENCES documents(id),
    memory_id UUID REFERENCES memories(id),
    PRIMARY KEY (document_id, memory_id)
);
```

### Phase 2: Memory Creation Pattern
When syncing content:

```python
# 1. Store the full document
document = Document(
    user_id=user.id,
    app_id=app.id,
    title=essay.title,
    source_url=essay.url,
    document_type='substack',
    content=essay.full_content,
    metadata={
        'author': essay.author,
        'published_date': essay.date,
        'word_count': len(essay.content.split())
    }
)
db.add(document)
db.flush()

# 2. Create summary memory
summary_memory = Memory(
    user_id=user.id,
    app_id=app.id,
    content=f"Essay: {essay.title} - {essay.summary[:200]}...",
    metadata_={
        'document_id': str(document.id),
        'type': 'document_summary'
    }
)
db.add(summary_memory)

# 3. Extract and store key insights as separate memories
insights = extract_insights(essay.content)  # Using LLM
for insight in insights:
    insight_memory = Memory(
        user_id=user.id,
        app_id=app.id,
        content=insight,
        metadata_={
            'document_id': str(document.id),
            'type': 'document_insight'
        }
    )
    db.add(insight_memory)
```

### Phase 3: MCP Tool Implementation

```python
@mcp.tool(description="Sync Substack posts for the user")
async def sync_substack_posts(substack_url: str, max_posts: int = 20) -> str:
    # Implementation that:
    # 1. Fetches posts
    # 2. Stores as documents
    # 3. Creates summary memories
    # 4. Returns success message
    
@mcp.tool(description="Query user's documents with Gemini long-context")
async def query_documents_gemini(query: str) -> str:
    # 1. Search memories for relevant document summaries
    # 2. Retrieve full documents from documents table
    # 3. Use Gemini 2.0 Flash with long context
    # 4. Return synthesized answer
```

### Phase 4: Migration Steps

1. **Create new models** in `models.py`
2. **Generate Alembic migration**
3. **Test with small dataset**
4. **Add MCP tools**
5. **Test end-to-end**

## Rollback Plan

If anything breaks:
1. `git reset --hard <checkpoint-commit>`
2. `alembic downgrade -1` (if migration was applied)
3. Restart services

## Testing Strategy

1. **Unit tests** for new document operations
2. **Integration tests** ensuring memories still work
3. **Manual testing** of Substack sync
4. **Performance testing** with large documents

## Future Considerations

- Document versioning (track updates)
- Document chunking strategies for very large files
- Search within documents
- Document collections/folders 