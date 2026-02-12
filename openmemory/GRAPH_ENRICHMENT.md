# Graph Enrichment Solution

## Problem

When LLMs query memories via `/api/v1/memories/filter`, they get flat data without semantic context:

```json
{
  "id": "123",
  "content": "Josephine's birthday is on 20th March",
  "categories": ["personal", "dates"],
  "metadata": {}
}
```

**The LLM doesn't know:**
- What is "Josephine"? (Person? Place? Organization?)
- What is "20th March"? (Date? Event?)
- How are they related? (HAS_BIRTHDAY relationship)

## Solution

New endpoints that enrich memories with graph data from Neo4j:

### 1. Enriched Filter Endpoint

**Endpoint:** `POST /api/v1/memories/filter/enriched`

**Response:**
```json
{
  "items": [
    {
      "id": "123",
      "memory": "Josephine's birthday is on 20th March",
      "content": "Josephine's birthday is on 20th March",
      "created_at": 1704067200,
      "state": "active",
      "categories": ["personal", "dates"],
      "entities": [
        {
          "name": "Josephine",
          "type": "PERSON",
          "label": "Person",
          "properties": {
            "name": "Josephine",
            "user_id": "user123"
          }
        },
        {
          "name": "20th March",
          "type": "DATE",
          "label": "Date",
          "properties": {
            "date": "20th March",
            "month": "March",
            "day": "20"
          }
        }
      ],
      "relationships": [
        {
          "source": "Josephine",
          "relation": "HAS_BIRTHDAY",
          "target": "20th March",
          "source_type": "PERSON",
          "target_type": "DATE",
          "properties": {}
        }
      ],
      "graph_enriched": true
    }
  ],
  "total": 1,
  "page": 1,
  "size": 10
}
```

### 2. Entity Lookup Endpoint

**Endpoint:** `GET /api/v1/memories/entity/{entity_name}?user_id=user123`

**Example:** `GET /api/v1/memories/entity/Josephine?user_id=user123`

**Response:**
```json
{
  "name": "Josephine",
  "type": "PERSON",
  "labels": ["PERSON", "Entity"],
  "properties": {
    "name": "Josephine",
    "user_id": "user123"
  },
  "relationships": [
    {
      "relation": "HAS_BIRTHDAY",
      "related_entity": "20th March",
      "related_type": "DATE",
      "direction": "outgoing"
    },
    {
      "relation": "WORKS_AT",
      "related_entity": "Acme Corp",
      "related_type": "ORGANIZATION",
      "direction": "outgoing"
    },
    {
      "relation": "LIVES_IN",
      "related_entity": "San Francisco",
      "related_type": "PLACE",
      "direction": "outgoing"
    }
  ]
}
```

### 3. Updated MCP Search (Automatic)

The MCP `search_memory` tool now automatically enriches all results with graph data.

**Before:**
```json
{
  "results": [
    {
      "id": "123",
      "memory": "Josephine's birthday is on 20th March",
      "score": 0.95
    }
  ]
}
```

**After:**
```json
{
  "results": [
    {
      "id": "123",
      "memory": "Josephine's birthday is on 20th March",
      "score": 0.95,
      "entities": [...],
      "relationships": [...],
      "graph_enriched": true
    }
  ]
}
```

## Use Cases

### Use Case 1: Entity Type Resolution

**Query:** "When is Josephine's birthday?"

**Without enrichment:**
- LLM sees: "Josephine" (string)
- Can't determine if Josephine is a person, place, or organization

**With enrichment:**
- LLM sees: "Josephine" (PERSON entity)
- Can confidently respond: "Josephine's birthday is on 20th March"

### Use Case 2: Relationship Discovery

**Query:** "Where does Josephine work?"

**Without enrichment:**
- LLM must scan all memories for text containing "Josephine" and "work"

**With enrichment:**
- LLM sees: Josephine -[WORKS_AT]-> Acme Corp
- Can directly answer: "Josephine works at Acme Corp"

### Use Case 3: Multi-hop Reasoning

**Query:** "What events are happening in March?"

**Without enrichment:**
- Limited to keyword search for "March"

**With enrichment:**
- Finds: 20th March -[IS_PART_OF]-> March (entity)
- Finds: Josephine -[HAS_BIRTHDAY]-> 20th March
- Finds: Company Event -[SCHEDULED_ON]-> 15th March
- Can answer: "In March: Josephine's birthday (20th), Company Event (15th)"

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        LLM Query                            │
│              "When is Josephine's birthday?"                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              POST /api/v1/memories/filter/enriched          │
│                  or search_memory (MCP)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Query Relational DB (SQLite/PostgreSQL)                 │
│     - Get matching memories by content/filters              │
│     - Returns: id, content, categories, metadata            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Enrich with Neo4j Graph Data                            │
│     - For each memory ID:                                   │
│       • Query entities: MATCH (m:Memory)-[:HAS_ENTITY]->(e) │
│       • Query relationships: MATCH (e1)-[r]->(e2)           │
│     - Add entity types and relationships to response        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Enriched Response to LLM                       │
│  {                                                          │
│    "memory": "Josephine's birthday is on 20th March",      │
│    "entities": [{name: "Josephine", type: "PERSON"}, ...], │
│    "relationships": [{source: "Josephine",                  │
│                       relation: "HAS_BIRTHDAY",             │
│                       target: "20th March"}]                │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

## Implementation

### Files Added

1. **`api/app/services/graph_enrichment.py`**
   - `GraphEnrichmentService` - Queries Neo4j for entity/relationship data
   - `enrich_memory()` - Enriches a single memory
   - `enrich_memories()` - Batch enrichment
   - `get_entity_context()` - Full entity lookup

2. **Updated `api/app/routers/memories.py`**
   - Added `POST /filter/enriched` endpoint
   - Added `GET /entity/{entity_name}` endpoint

3. **Updated `api/app/mcp_server.py`**
   - Modified `search_memory()` to auto-enrich results

## Usage Examples

### Python Client

```python
import requests

# Filter memories with graph enrichment
response = requests.post(
    "http://localhost:8765/api/v1/memories/filter/enriched",
    json={
        "user_id": "user123",
        "search_query": "Josephine",
        "page": 1,
        "size": 10
    }
)

enriched_memories = response.json()["items"]

for memory in enriched_memories:
    print(f"Memory: {memory['content']}")
    print(f"Entities: {memory['entities']}")
    print(f"Relationships: {memory['relationships']}")
    print()

# Look up a specific entity
response = requests.get(
    "http://localhost:8765/api/v1/memories/entity/Josephine",
    params={"user_id": "user123"}
)

josephine = response.json()
print(f"Josephine is a {josephine['type']}")
print(f"Relationships: {josephine['relationships']}")
```

### MCP Client (Automatic)

```python
# Using Claude Desktop with MCP
# The enrichment happens automatically!

user: "When is Josephine's birthday?"

# Claude receives enriched data:
# {
#   "memory": "Josephine's birthday is on 20th March",
#   "entities": [{"name": "Josephine", "type": "PERSON"}, ...],
#   "relationships": [{"source": "Josephine", "relation": "HAS_BIRTHDAY", ...}]
# }

claude: "Josephine's birthday is on 20th March."
```

## Performance Considerations

1. **Caching**: Consider adding Redis cache for frequently accessed entities
2. **Batch Queries**: The service queries Neo4j once per memory (parallelizable)
3. **Lazy Loading**: Original `/filter` endpoint still available (no graph data)
4. **Limit Relationships**: Currently limited to 20 relationships per memory

## Configuration

Requires Neo4j environment variables:

```bash
NEO4J_URL=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DB=neo4j
```

If Neo4j is not configured, endpoints gracefully degrade (no enrichment).

## Migration Path

1. **Phase 1** (Current): Both endpoints available
   - `/filter` - Original (fast, no graph data)
   - `/filter/enriched` - New (slower, with graph data)

2. **Phase 2**: Monitor usage and performance
   - Add caching if needed
   - Optimize Neo4j queries

3. **Phase 3**: Make enrichment default
   - Add `?enrich=false` parameter to skip enrichment
   - Update MCP to use enriched by default

## Testing

```bash
# Test enriched endpoint
curl -X POST http://localhost:8765/api/v1/memories/filter/enriched \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "page": 1,
    "size": 10
  }'

# Test entity lookup
curl http://localhost:8765/api/v1/memories/entity/Josephine?user_id=test_user
```

## Future Enhancements

1. **Graph Traversal Queries**
   - "Find all people who work at the same company as Josephine"
   - Multi-hop graph queries

2. **Temporal Queries**
   - "What events happened before Josephine's birthday?"
   - Time-based relationship filtering

3. **Relationship Strength**
   - Weight relationships by frequency/recency
   - Surface most important connections first

4. **Entity Disambiguation**
   - Handle multiple entities with same name
   - "Josephine (Friend)" vs "Josephine (Coworker)"

## Benefits Summary

✅ **LLMs get semantic context** - Know what entities are
✅ **Relationship-aware queries** - Understand how things connect
✅ **Better reasoning** - Multi-hop inference over knowledge graph
✅ **Backwards compatible** - Original endpoints still work
✅ **Graceful degradation** - Works even if Neo4j unavailable
✅ **Performance optimized** - Batch queries, limit relationships

**Sources:**
- [Get Memories - Mem0](https://docs.mem0.ai/api-reference/memory/get-memories)
- [Mem0 Tutorial: Persistent Memory Layer for AI Applications](https://www.datacamp.com/tutorial/mem0-tutorial)
