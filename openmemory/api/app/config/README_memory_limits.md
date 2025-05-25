# Memory Limits Configuration

This document explains the memory search and retrieval limits implemented in Jean Memory to prevent excessive context retrieval and improve performance.

## Configuration File

The memory limits are configured in `memory_limits.py` and can be easily adjusted based on your needs.

## Default Limits

### Regular Memory Search
- **Default**: 10 results
- **Maximum**: 50 results
- **Purpose**: Prevents overwhelming the AI with too much context during regular searches

### Memory Listing (get_all)
- **Default**: 20 results
- **Maximum**: 100 results
- **Purpose**: Provides a reasonable overview without loading entire memory banks

### Deep Memory Query
- **Memory Default**: 20 results
- **Memory Maximum**: 50 results
- **Chunk Default**: 10 document chunks
- **Chunk Maximum**: 20 document chunks
- **Purpose**: Balances comprehensive search with performance

### UI Pagination
- **Default Page Size**: 10 items
- **Available Options**: 5, 10, 20, 50 items per page

## Usage Examples

### MCP Tools

```python
# Search with default limit (10)
await search_memory("what do I know about AI")

# Search with custom limit
await search_memory("my recent projects", limit=25)

# List memories with default limit (20)
await list_memories()

# Deep query with custom limits
await deep_memory_query(
    "comprehensive analysis of my writing style",
    memory_limit=30,
    chunk_limit=15,
    include_full_docs=True
)
```

### HTTP API

```bash
# Search with default limit
curl -X POST /api/v1/mcp/search_memory \
  -d '{"query": "AI projects"}'

# Search with custom limit
curl -X POST /api/v1/mcp/search_memory \
  -d '{"query": "AI projects", "limit": 25}'
```

## Adjusting Limits

To adjust the limits, modify the values in `memory_limits.py`:

```python
class MemoryLimits(BaseModel):
    # Increase search results
    search_default: int = 15  # was 10
    search_max: int = 75      # was 50
    
    # Adjust deep query limits
    deep_memory_default: int = 30  # was 20
    deep_chunk_default: int = 15   # was 10
```

## Performance Considerations

1. **Latency**: More results = longer processing time
2. **Token Usage**: Each memory consumes tokens in the AI's context window
3. **Relevance**: More results may include less relevant memories
4. **Cost**: Higher limits increase API costs for embeddings and LLM calls

## Best Practices

1. **Start Small**: Use default limits and increase only if needed
2. **Use Deep Query Sparingly**: Reserve for comprehensive analysis
3. **Filter First**: Use specific queries rather than increasing limits
4. **Monitor Performance**: Track response times with different limits

## Score Thresholds

The configuration also includes a `min_relevance_score` (default: 0.7) which filters out memories with low relevance scores. This helps ensure quality over quantity. 