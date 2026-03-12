# Platform Features -- Mem0 Platform

Additional platform capabilities beyond core CRUD operations.

## Table of Contents

- [Advanced Retrieval](#advanced-retrieval)
- [Graph Memory](#graph-memory)
- [Custom Categories](#custom-categories)
- [Custom Instructions](#custom-instructions)
- [Criteria Retrieval](#criteria-retrieval)
- [Feedback Mechanism](#feedback-mechanism)
- [Memory Export](#memory-export)
- [Group Chat](#group-chat)
- [MCP Integration](#mcp-integration)
- [Webhooks](#webhooks)
- [Multimodal Support](#multimodal-support)

## Advanced Retrieval

Three enhancement options for tuning search precision, recall, and latency.

### Keyword Search (`keyword_search=True`)

Expands results to include memories with specific terms, names, and technical keywords.

- Latency: +10ms
- Recall: Significantly increased
- Best for: entity-heavy queries, comprehensive coverage

### Reranking (`rerank=True`)

Deep semantic reordering of results — most relevant first.

- Latency: +150-200ms
- Accuracy: Significantly improved
- Best for: user-facing results, top-N precision

### Filter Memories (`filter_memories=True`)

Precision filtering — removes low-relevance results entirely.

- Latency: +200-300ms
- Precision: Maximized
- Best for: safety-critical applications, production systems

### Recommended Combinations

**Python:**
```python
# Fast & broad
results = client.search(query, keyword_search=True, user_id="user123")

# Balanced (recommended for most apps)
results = client.search(query, keyword_search=True, rerank=True, user_id="user123")

# High precision (critical apps)
results = client.search(query, rerank=True, filter_memories=True, user_id="user123")
```

**TypeScript:**
```typescript
const results = await client.search(query, {
    user_id: 'user123',
    keyword_search: true,
    rerank: true,
});
```

---

## Graph Memory

Entity-level knowledge graph that creates relationships between memories.

### How It Works

1. **Extraction**: LLM analyzes conversation and identifies entities and relationships
2. **Storage**: Embeddings go to vector store; entity nodes and edges go to graph store
3. **Retrieval**: Vector search returns semantic matches; graph relations are appended to results

Graph relations **augment** vector results without reordering them. Vector similarity always determines hit sequence.

### Enabling Graph Memory

**Per request:**
```python
client.add(messages, user_id="alice", enable_graph=True)
client.search("query", user_id="alice", enable_graph=True)
client.get_all(filters={"AND": [{"user_id": "alice"}]}, enable_graph=True)
```

**Project-level (default for all operations):**
```python
client.project.update(enable_graph=True)
```

```javascript
await client.updateProject({ enable_graph: true });
```

### Relation Structure

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
    }
  ]
}
```

### Technical Notes

- Graph Memory adds processing time; see docs for current plan availability
- Works optimally with rich conversation histories containing entity relationships
- Best suited for long-running assistants tracking evolving information
- Graph writes and reads toggle independently per request
- Multi-agent context supported via `user_id`, `agent_id`, `run_id` scoping
- Add operations are asynchronous; graph metadata may not be immediately available

---

## Custom Categories

Replace Mem0's default 15 labels with domain-specific categories. The system automatically tags memories to the closest matching category.

### Default Categories (15)

`personal_details`, `family`, `professional_details`, `sports`, `travel`, `food`, `music`, `health`, `technology`, `hobbies`, `fashion`, `entertainment`, `milestones`, `user_preferences`, `misc`

### Configuration

**Set project-level categories:**
```python
new_categories = [
    {"lifestyle_management": "Tracks daily routines, habits, wellness activities"},
    {"seeking_structure": "Documents goals around creating routines and systems"},
    {"personal_information": "Basic information about the user"}
]
client.project.update(custom_categories=new_categories)
```

```javascript
await client.updateProject({ custom_categories: new_categories });
```

**Retrieve active categories:**
```python
categories = client.project.get(fields=["custom_categories"])
```

### Key Constraint

Per-request overrides (`custom_categories=...` on `client.add`) are **not supported** on the managed API. Only project-level configuration works. Workaround: store ad-hoc labels in `metadata` field.

---

## Custom Instructions

Natural language filters that control what information Mem0 extracts when creating memories.

### Set Instructions

```python
client.project.update(custom_instructions="Your guidelines here...")
```

```javascript
await client.updateProject({ custom_instructions: "Your guidelines here..." });
```

### Template Structure

1. **Task Description** -- brief extraction overview
2. **Information Categories** -- numbered sections with specific details to capture
3. **Processing Guidelines** -- quality and handling rules
4. **Exclusion List** -- sensitive/irrelevant data to filter out

### Domain Examples

**E-commerce:** Capture product issues, preferences, service experience; exclude payment data.

**Education:** Extract learning progress, student preferences, performance patterns; exclude specific grades.

**Finance:** Track financial goals, life events, investment interests; exclude account numbers and SSNs.

### Best Practices

- Start simply, test with sample messages, iterate based on results
- Avoid overly lengthy instructions
- Be specific about what to include AND exclude

---

## Criteria Retrieval

Custom attribute-based memory ranking using LLM-evaluated criteria with weights. Goes beyond semantic similarity to prioritize memories based on domain-specific signals.

### Configuration

```python
# Define criteria at project level
retrieval_criteria = [
    {"name": "joy", "description": "Positive emotions like happiness and excitement", "weight": 3},
    {"name": "curiosity", "description": "Inquisitiveness and desire to learn", "weight": 2},
    {"name": "urgency", "description": "Time-sensitive or high-priority items", "weight": 4},
]
client.project.update(retrieval_criteria=retrieval_criteria)
```

```typescript
await client.updateProject({
    retrieval_criteria: [
        { name: 'joy', description: 'Positive emotions', weight: 3 },
        { name: 'urgency', description: 'Time-sensitive items', weight: 4 },
    ],
});
```

### Usage

Once configured, `client.search()` automatically applies criteria ranking:

```python
# Criteria-weighted results returned automatically
results = client.search("Why am I feeling happy?", filters={"user_id": "alice"})
```

**Best for:** Wellness assistants, tutoring platforms, productivity tools — any app needing intent-aware retrieval.

---

## Feedback Mechanism

Provide feedback on extracted memories to improve system quality over time.

### Feedback Types

| Type | Meaning |
|------|---------|
| `POSITIVE` | Memory is useful and accurate |
| `NEGATIVE` | Memory is not useful |
| `VERY_NEGATIVE` | Memory is harmful or completely wrong |
| `None` | Clear existing feedback |

### Usage

**Python:**
```python
client.feedback(
    memory_id="mem-123",
    feedback="POSITIVE",
    feedback_reason="Accurately captured dietary preference"
)

# Bulk feedback
for item in feedback_data:
    client.feedback(**item)
```

**TypeScript:**
```typescript
await client.feedback('mem-123', {
    feedback: 'POSITIVE',
    feedback_reason: 'Accurately captured dietary preference',
});
```

---

## Memory Export

Create structured exports of memories using customizable schemas with filters.

### Usage

```python
import json

# Define export schema
schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "preferences": {"type": "array", "items": {"type": "string"}},
        "health_info": {"type": "string"},
    }
}

# Create export
response = client.create_memory_export(
    schema=json.dumps(schema),
    filters={"user_id": "alice"},
    export_instructions="Create comprehensive profile based on all memories"
)

# Retrieve export (may take a moment to process)
result = client.get_memory_export(memory_export_id=response["id"])
```

**Best for:** Data analytics, user profile generation, compliance audits, CRM sync.

---

## Group Chat

Process multi-participant conversations and automatically attribute memories to individual speakers.

### Usage

```python
messages = [
    {"role": "user", "name": "Alice", "content": "I think we should use React for the frontend"},
    {"role": "user", "name": "Bob", "content": "I prefer Vue.js, it's simpler for our use case"},
    {"role": "assistant", "content": "Both are great choices. Let me note your preferences."},
]

# Mem0 automatically attributes memories to each speaker
response = client.add(messages, run_id="team_meeting_1")

# Retrieve Alice's memories from that session
alice_mems = client.get_all(
    filters={"AND": [{"user_id": "alice"}, {"run_id": "team_meeting_1"}]}
)
```

Use the `name` field in messages to identify speakers. Mem0 maps names to entity scopes automatically.

---

## MCP Integration

Model Context Protocol integration enables AI clients (Claude Desktop, Cursor, custom agents) to manage Mem0 memory autonomously.

### Configuration

```json
{
  "mcpServers": {
    "mem0": {
      "command": "uvx",
      "args": ["mem0-mcp-server"],
      "env": {
        "MEM0_API_KEY": "m0-your-api-key",
        "MEM0_DEFAULT_USER_ID": "your-user-id"
      }
    }
  }
}
```

### Available MCP Tools

The MCP server exposes 9 memory tools that AI agents can use autonomously:
- Add, search, get, update, delete memories
- Get history, list users, delete users
- Search Mem0 documentation

### How It Works

1. Configure the MCP server in your AI client
2. The agent autonomously decides when to store/retrieve memories
3. No manual API calls needed — the agent manages memory as part of its reasoning

**Best for:** Universal AI client integration — one protocol works everywhere.

---

## Webhooks

Real-time event notifications for memory operations.

### Supported Events

| Event | Trigger |
|-------|---------|
| `memory_add` | Memory created |
| `memory_update` | Memory modified |
| `memory_delete` | Memory removed |
| `memory_categorize` | Memory tagged |

### Create Webhook

Note: `project_id` here refers to the Mem0 dashboard project scope for webhooks — not the deprecated client init parameter.

```python
webhook = client.create_webhook(
    url="https://your-app.com/webhook",
    name="Memory Logger",
    project_id="proj_123",
    event_types=["memory_add", "memory_categorize"]
)
```

### Manage Webhooks

```python
# Retrieve
webhooks = client.get_webhooks(project_id="proj_123")

# Update
client.update_webhook(
    name="Updated Logger",
    url="https://your-app.com/new-webhook",
    event_types=["memory_update", "memory_add"],
    webhook_id="wh_123"
)

# Delete
client.delete_webhook(webhook_id="wh_123")
```

### Payload Structure

Memory events contain: ID, data object with memory content, event type (`ADD`/`UPDATE`/`DELETE`).
Categorization events contain: memory ID, event type (`CATEGORIZE`), assigned category labels.

---

## Multimodal Support

Mem0 can process images and documents alongside text.

### Supported Media Types

- Images: JPG, PNG
- Documents: MDX, TXT, PDF

### Image via URL

```python
image_message = {
    "role": "user",
    "content": {
        "type": "image_url",
        "image_url": {"url": "https://example.com/image.jpg"}
    }
}
client.add([image_message], user_id="alice")
```

### Image via Base64

```python
import base64
with open("photo.jpg", "rb") as f:
    base64_image = base64.b64encode(f.read()).decode("utf-8")

image_message = {
    "role": "user",
    "content": {
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
    }
}
client.add([image_message], user_id="alice")
```

### Document (MDX/TXT)

```python
doc_message = {
    "role": "user",
    "content": {"type": "mdx_url", "mdx_url": {"url": document_url}}
}
client.add([doc_message], user_id="alice")
```

### PDF Document

```python
pdf_message = {
    "role": "user",
    "content": {"type": "pdf_url", "pdf_url": {"url": pdf_url}}
}
client.add([pdf_message], user_id="alice")
```
