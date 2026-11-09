# Platform Features -- Mem0 Platform

Additional platform capabilities beyond core CRUD operations.

## Table of Contents

- [Advanced Retrieval](#advanced-retrieval)
- [Entity Linking](#entity-linking)
- [Custom Categories](#custom-categories)
- [Custom Instructions](#custom-instructions)
- [Feedback Mechanism](#feedback-mechanism)
- [Memory Export](#memory-export)
- [Group Chat](#group-chat)
- [MCP Integration](#mcp-integration)
- [Webhooks](#webhooks)
- [Multimodal Support](#multimodal-support)

## Advanced Retrieval

### Hybrid Search (v3 Default)

v3 uses multi-signal hybrid search combining:
- **Semantic search** (vector similarity)
- **BM25 keyword search** (normalized term matching)
- **Entity matching** (entity graph boost)
- **Temporal reasoning** (Platform only): memories whose event dates match time expressions in the query ("last week", "as of March 2025") get a boost

This is automatic — no configuration needed.

### Reranking (`rerank=True`)

Deep semantic reordering of results — most relevant first.

- Latency: +150-200ms
- Default: `False` (was `True` in v2)
- Best for: user-facing results, top-N precision

**Python:**
```python
results = client.search(query, filters={"user_id": "user123"}, rerank=True)
```

**TypeScript:**
```typescript
const results = await client.search(query, {
    filters: { user_id: 'user123' },
    rerank: true,
});
```

---

## Entity Linking

v3 replaces graph memory with built-in entity linking. Entities (proper nouns, quoted text, compound noun phrases) are automatically extracted and linked across memories.

### How It Works

1. **Extraction**: During `add()`, entities are automatically extracted from memory text
2. **Storage**: Entities are stored in a parallel collection (OSS: `{collection}_entities`; on Platform the entity store is managed for you)
3. **Retrieval**: During `search()`, query entities are matched and used to boost relevant memories

Entity linking is automatic, no configuration required. The boost is folded into the combined `score` on each result. On Platform this is Graph Memory: built in on all plans, no external graph store to provision, and the dashboard Graph view is Pro and Enterprise only.

### v2 Migration Note

If you were using `enable_graph=True` in v2:
- Remove `enable_graph` from all API calls
- Remove `graph_store` from OSS configuration
- Entity relationships are now consumed through retrieval ranking, not exposed as a separate `relations` array

See the [v2 to v3 migration guide](https://docs.mem0.ai/migration/oss-v2-to-v3) for details.

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
await client.updateProject({ customCategories: newCategories });
```

**Retrieve active categories:**
```python
categories = client.project.get(fields=["custom_categories"])
```

**Override categories for a single add call:**
```python
client.add(messages, user_id="alice", custom_categories=per_call_categories)
```

```javascript
await client.add(messages, { userId: "alice", customCategories: perCallCategories });
```

### Resolution Order

1. `custom_categories` passed on the `add` call
2. `custom_categories` set on the project
3. Built-in default catalog

### Key Constraints

- A per-call list **fully replaces** the project list for that call. The lists are not merged.
- Categories are applied at ingestion time. Changing the list later does not re-tag existing memories.

### Main Use Case

Per-call lists give different users or entities their own vocabulary inside a single project, without splitting them across projects.

---

## Custom Instructions

Natural language filters that control what information Mem0 extracts when creating memories.

### Set Instructions

```python
client.project.update(custom_instructions="Your guidelines here...")
```

```javascript
await client.updateProject({ customInstructions: "Your guidelines here..." });
```

### Agent Custom Instructions

`agent_custom_instructions` (Python SDK 2.0.17+, TypeScript SDK 3.1.5+) is a second set of extraction rules that applies only to agent-scoped memories. It is unset by default, and while unset `custom_instructions` applies to every memory.

```python
client.project.update(
    custom_instructions="Extract the user's preferences, goals, and constraints.",
    agent_custom_instructions="Extract tools that failed, and retry strategies that worked.",
)
```

```javascript
await client.updateProject({
    customInstructions: "Extract the user's preferences, goals, and constraints.",
    agentCustomInstructions: "Extract tools that failed, and retry strategies that worked.",
});
```

| The `add` call passes | Instructions applied |
|-----------------------|----------------------|
| `user_id` only | `custom_instructions` |
| `agent_id` only | `agent_custom_instructions` |
| `user_id` and `agent_id` | `agent_custom_instructions` for memories attributed to the assistant, `custom_instructions` for the rest |

Both fields can also be passed per `add` call to override the project setting for that call. Clear the project value with an empty string.

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
import { Feedback } from 'mem0ai';

await client.feedback({
    memoryId: 'mem-123',
    feedback: Feedback.POSITIVE,
    feedbackReason: 'Accurately captured dietary preference',
});
```

---

## Memory Export

Create structured exports of memories using customizable schemas with filters.

### Usage

```python
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
    schema=schema,
    filters={"AND": [{"user_id": "alice"}]},
    export_instructions="Create comprehensive profile based on all memories"
)

# Retrieve export (may take a moment to process)
result = client.get_memory_export(memory_export_id=response["id"])
```

**Best for:** Data analytics, user profile generation, compliance audits, CRM sync.

---

## Group Chat

Process multi-participant conversations and keep a separate memory profile per speaker. Scope comes only from the `user_id`, `agent_id`, and `run_id` you pass to `add()`: Mem0 does not infer it from the conversation.

### Usage

Call `add()` once per participant with their own `user_id`, and share a `run_id` for the session:

```python
client.add(
    [{"role": "user", "content": "I think we should use React for the frontend"}],
    user_id="alice", run_id="team_meeting_1",
)
client.add(
    [{"role": "user", "content": "I prefer Vue.js, it's simpler for our use case"}],
    user_id="bob", run_id="team_meeting_1",
)

# Retrieve Alice's memories from that session
alice_mems = client.get_all(
    filters={"AND": [{"user_id": "alice"}, {"run_id": "team_meeting_1"}]}
)

session_mems = client.get_all(
    filters={"AND": [{"user_id": "*"}, {"run_id": "team_meeting_1"}]}
)
```

A `name` field on a message is stored as extraction context only. Passing messages from two different `name`s in one `add()` call does not split the memories: they all land under the `user_id` you passed.

---

## MCP Integration

Model Context Protocol integration enables AI clients (Claude, Claude Code, Codex, Cursor, Windsurf, VS Code, OpenCode) to manage Mem0 memory autonomously.

### Setup

Add Mem0 MCP to your clients with a single command:

```bash
npx mcp-add \
  --name mem0-mcp \
  --type http \
  --url "https://mcp.mem0.ai/mcp" \
  --clients "claude code,cursor,windsurf,vscode,opencode"
```

Claude Desktop rejects `mcp-add`: add it under Settings > Connectors instead. Codex reads `~/.codex/config.toml` (TOML, server name `mem0`). The first tool call opens a browser sign-in, or send your API key as a bearer token for headless environments.

### Available MCP Tools

The MCP server exposes 11 memory tools that AI agents can use autonomously:
- `add_memory`, `search_memories`, `get_memories`, `get_memory`, `update_memory`
- `delete_memory`, `delete_all_memories`, `delete_entities`
- `list_entities`, `list_events`, `get_event_status`

### How It Works

1. Add Mem0 MCP to your AI client using the setup command above
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
| `ingest_job_completed` | Ingest job finished successfully |
| `ingest_job_partially_completed` | Ingest job finished with some items failed |
| `ingest_job_failed` | Ingest job failed entirely |
| `ingest_job_cancelled` | Ingest job cancelled |

The TypeScript `WebhookEvent` enum covers only the four `memory_*` events (`MEMORY_ADDED`, `MEMORY_UPDATED`, `MEMORY_DELETED`, `MEMORY_CATEGORIZED`).

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

```typescript
import { WebhookEvent } from 'mem0ai';

const webhook = await client.createWebhook({
    url: 'https://your-app.com/webhook',
    name: 'Memory Logger',
    eventTypes: [WebhookEvent.MEMORY_ADDED, WebhookEvent.MEMORY_CATEGORIZED],
});
```

TypeScript `createWebhook` takes no `projectId`: it uses the project resolved by the client. `getWebhooks({ projectId })` accepts one optionally.

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

The POST body wraps everything in `event_details`.
Memory events contain: ID, data object with memory content, event type (`ADD`/`UPDATE`/`DELETE`).
Categorization events contain: memory ID, event type (`CATEGORIZE`), assigned category labels.

---

## Multimodal Support

`POST /v3/memories/add/` (what `client.add()` calls) accepts only string `content`. Structured multimodal content (`image_url`, `pdf_url`, `txt_url`, `mdx_url`) is rejected with a 400 `Not a valid string.`, with `infer=True` and with `infer=False`. To remember what an image or document says, extract the text yourself and pass it as a plain string.
