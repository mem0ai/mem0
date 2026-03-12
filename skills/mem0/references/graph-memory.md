# Graph Memory -- Mem0 Platform

Entity-level knowledge graph that creates relationships between memories.

## Table of Contents
- [How It Works](#how-it-works)
- [Enabling Graph Memory](#enabling-graph-memory)
- [Add with Graph](#add-with-graph)
- [Search with Graph](#search-with-graph)
- [Get All with Graph](#get-all-with-graph)
- [Relation Structure](#relation-structure)
- [Technical Notes](#technical-notes)

## How It Works

1. **Extraction**: LLM analyzes conversation and identifies entities and relationships
2. **Storage**: Embeddings go to vector store; entity nodes and edges go to graph store
3. **Retrieval**: Vector search returns semantic matches; graph relations are appended to results

Graph relations **augment** vector results without reordering them. Vector similarity always determines hit sequence.

## Enabling Graph Memory

### Per request
```python
client.add(messages, user_id="alice", enable_graph=True)
client.search("query", user_id="alice", enable_graph=True)
client.get_all(filters={"AND": [{"user_id": "alice"}]}, enable_graph=True)
```

### Project-level (default for all operations)
```python
client.project.update(enable_graph=True)
```
```javascript
await client.updateProject({ enable_graph: true });
```

## Add with Graph

**Python:**
```python
messages = [
    {"role": "user", "content": "My name is Joseph"},
    {"role": "assistant", "content": "Hello Joseph!"},
    {"role": "user", "content": "I'm from Seattle and I work as a software engineer"}
]
client.add(messages, user_id="joseph", enable_graph=True)
```

**JavaScript:**
```javascript
await client.add(messages, { user_id: "joseph", enable_graph: true });
```

**Response:** Returns standard memory events (`ADD`, `UPDATE`, `DELETE`). Graph metadata is processed **asynchronously** -- use `get_all()` for complete graph data.

## Search with Graph

**Python:**
```python
results = client.search("what is my name?", user_id="joseph", enable_graph=True)
```

**JavaScript:**
```javascript
const results = await client.search("what is my name?", {
    user_id: "joseph",
    enable_graph: true
});
```

**Response includes:**
- `results` array -- vector-ordered results (with optional reranking)
- `relations` array -- entity relationships from graph

## Get All with Graph

**Python:**
```python
memories = client.get_all(
    filters={"AND": [{"user_id": "joseph"}]},
    enable_graph=True
)
```

**JavaScript:**
```javascript
const memories = await client.getAll({
    filters: {"AND": [{"user_id": "joseph"}]},
    enable_graph: true
});
```

**Response includes:** `results` array (each memory may contain `entities`) and top-level `relations` array.

**Note:** `filters` parameter is mandatory for `get_all()`.

## Relation Structure

Each relation in the response contains:

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Source entity name |
| `source_type` | string | Source entity type (e.g., "Person") |
| `relationship` | string | Relationship label (e.g., "lives_in") |
| `target` | string | Target entity name |
| `target_type` | string | Target entity type (e.g., "City") |
| `score` | number | Confidence score |

**Example:**
```json
{
  "relations": [
    {
      "source": "Joseph",
      "source_type": "Person",
      "relationship": "lives_in",
      "target": "Seattle",
      "target_type": "City",
      "score": 0.92
    },
    {
      "source": "Joseph",
      "source_type": "Person",
      "relationship": "works_as",
      "target": "Software Engineer",
      "target_type": "Profession",
      "score": 0.88
    }
  ]
}
```

## Technical Notes

- Graph Memory adds processing time; see docs for current plan availability
- Works optimally with rich conversation histories containing entity relationships
- Best suited for long-running assistants tracking evolving information
- Graph writes and reads toggle independently per request
- Performance impact is minimal for typical use cases
- Multi-agent context supported via `user_id`, `agent_id`, `run_id` scoping
- Add operations are asynchronous; graph metadata may not be immediately available

CLI tools: `python scripts/add_memory.py --enable_graph --help` and `python scripts/search_memory.py --help`
