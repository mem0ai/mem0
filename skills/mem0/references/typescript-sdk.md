# Mem0 TypeScript / JavaScript SDK Reference

Package: `mem0ai` v2.3.0 | Node.js 18+ required

## Installation

```bash
npm install mem0ai
# or
yarn add mem0ai
# or
pnpm add mem0ai
```

## Platform Client (Managed API)

### Initialization

```javascript
import MemoryClient from 'mem0ai';

const client = new MemoryClient({ apiKey: 'm0-your-api-key' });

// With org and project scope
const client = new MemoryClient({
    apiKey: 'm0-your-api-key',
    organizationId: 'your-org-id',
    projectId: 'your-project-id',
});
```

### Constructor Options

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `apiKey` | string | Yes | Mem0 Platform API key (starts with `m0-`) |
| `host` | string | No | API base URL (default: `https://api.mem0.ai`) |
| `organizationName` | string | No | Organization name |
| `projectName` | string | No | Project name |
| `organizationId` | string | No | Organization ID |
| `projectId` | string | No | Project ID |

---

## Methods

### `add(messages, options?)`

Add memories from conversation messages.

```javascript
// Simple add
await client.add(
    [{ role: "user", content: "I love hiking in the mountains." }],
    { user_id: "alice" }
);

// With metadata and graph memory
await client.add(
    [
        { role: "user", content: "I work at Acme Corp as a senior engineer." },
        { role: "assistant", content: "Got it! I'll remember your work details." }
    ],
    {
        user_id: "alice",
        agent_id: "assistant-v1",
        metadata: { source: "onboarding" },
        enable_graph: true,
    }
);

// Without inference (store raw text)
await client.add(
    [{ role: "user", content: "Meeting notes from 2025-01-15..." }],
    { user_id: "alice", infer: false }
);
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `messages` | `Array<Message>` | Array of `{role, content}` objects. Role: `"user"` or `"assistant"` |
| `options.user_id` | string | User identifier |
| `options.agent_id` | string | Agent identifier |
| `options.run_id` | string | Run/session identifier |
| `options.metadata` | object | Custom key-value pairs |
| `options.enable_graph` | boolean | Enable graph memory (Pro plan) |
| `options.infer` | boolean | If `false`, store raw text without LLM inference (default: `true`) |
| `options.immutable` | boolean | Make memory immutable |
| `options.expiration_date` | string | Auto-expiry date (YYYY-MM-DD) |

**Returns:** `Promise<Array<Memory>>`

---

### `search(query, options?)`

Search memories by semantic query.

```javascript
// Simple search
const results = await client.search("dietary preferences", { user_id: "alice" });

// With V2 filters
const results = await client.search("work experience", {
    filters: {
        AND: [
            { user_id: "alice" },
            { categories: { contains: "professional_details" } }
        ]
    },
    top_k: 5,
    rerank: true,
});

// With graph relations
const results = await client.search("colleagues", {
    user_id: "alice",
    enable_graph: true,
});
```

**Parameters:**

| Name | Type | Description |
|------|------|-------------|
| `query` | string | Natural language search query |
| `options.user_id` | string | Filter by user |
| `options.filters` | object | V2 filter object (AND/OR operators) |
| `options.top_k` | number | Number of results (default: 10) |
| `options.rerank` | boolean | Enable reranking for better relevance |
| `options.threshold` | number | Minimum similarity score |
| `options.keyword_search` | boolean | Use keyword search |
| `options.enable_graph` | boolean | Include graph relations |

**Returns:** `Promise<Array<Memory>>`

---

### `getAll(options?)`

Retrieve all memories with optional filtering.

```javascript
const memories = await client.getAll({ user_id: "alice" });

// With filters
const memories = await client.getAll({
    filters: { AND: [{ user_id: "alice" }] },
});
```

**Returns:** `Promise<Array<Memory>>`

---

### `get(memoryId)`

Get a single memory by ID.

```javascript
const memory = await client.get("memory-uuid-here");
```

**Returns:** `Promise<Memory>`

---

### `update(memoryId, data)`

Update an existing memory.

```javascript
await client.update("memory-uuid", {
    text: "Updated memory content",
    metadata: { updated: true },
});
```

**Returns:** `Promise<Array<Memory>>`

---

### `delete(memoryId)`

Delete a single memory.

```javascript
await client.delete("memory-uuid");
```

**Returns:** `Promise<{ message: string }>`

---

### `deleteAll(options?)`

Delete all memories for a user/agent/session.

```javascript
await client.deleteAll({ user_id: "alice" });
```

**Returns:** `Promise<{ message: string }>`

---

### `history(memoryId)`

Get audit history for a memory.

```javascript
const history = await client.history("memory-uuid");
// Returns array of changes: [{id, memory_id, old_memory, new_memory, event, ...}]
```

**Returns:** `Promise<Array<MemoryHistory>>`

---

### `users()`

Get all users, agents, and sessions that have memories.

```javascript
const allUsers = await client.users();
```

**Returns:** `Promise<AllUsers>`

---

### `batchUpdate(memories)` / `batchDelete(memories)`

Bulk operations.

```javascript
// Batch update (note: uses camelCase memoryId)
await client.batchUpdate([
    { memoryId: "uuid-1", text: "Updated text" },
    { memoryId: "uuid-2", metadata: { reviewed: true } },
]);

// Batch delete
await client.batchDelete(["uuid-1", "uuid-2", "uuid-3"]);
```

---

### `deleteUsers(params?)`

Delete users, agents, apps, or runs.

```javascript
await client.deleteUsers({ user_id: "alice" });
await client.deleteUsers({ agent_id: "bot-1" });
```

**Returns:** `Promise<{ message: string }>`

---

### `feedback(data)`

Submit feedback on a memory.

```javascript
await client.feedback({
    memory_id: "memory-uuid",
    feedback: "POSITIVE",          // "POSITIVE", "NEGATIVE", or "VERY_NEGATIVE"
    feedback_reason: "Accurate memory extraction",
});
```

**Returns:** `Promise<{ message: string }>`

---

### `createMemoryExport(data)` / `getMemoryExport(data)`

Export memories for backup or migration.

```javascript
// Create an export
const exportResult = await client.createMemoryExport({
    schema: "v1",
    user_id: "alice",
});

// Retrieve the export
const exportData = await client.getMemoryExport({
    id: exportResult.id,
});
```

---

### Webhook Management

```javascript
// Create webhook
const webhook = await client.createWebhook({
    url: "https://your-app.com/webhook",
    name: "Memory Logger",
    projectId: "proj_123",
    eventTypes: ["memory_add", "memory_update"],
});

// Get webhooks
const webhooks = await client.getWebhooks({ projectId: "proj_123" });

// Update webhook
await client.updateWebhook({
    webhookId: "wh_123",
    name: "Updated Logger",
    url: "https://your-app.com/new-webhook",
    eventTypes: ["memory_add"],
});

// Delete webhook
await client.deleteWebhook({ webhookId: "wh_123" });
```

---

### Project Settings

```javascript
// Get project settings
const project = await client.getProject({ fields: ["custom_categories", "custom_instructions"] });

// Update project settings
await client.updateProject({
    custom_instructions: "Extract user preferences and dietary restrictions.",
    custom_categories: [
        { dietary_preferences: "Food allergies, restrictions, and preferences" },
        { travel_preferences: "Destination types, budget ranges, travel style" },
    ],
});
```

---

## OSS Client (Self-Hosted)

For self-hosted Mem0 (not recommended for most users -- use Platform instead):

```javascript
import { Memory } from "mem0ai/oss";

const memory = new Memory();

// Same interface but runs locally
await memory.add(messages, { userId: "alice" });
const results = await memory.search("query", { userId: "alice" });
```

Note: OSS client uses `camelCase` parameters (`userId`) while Platform client uses `snake_case` (`user_id`).

---

## Memory Object Shape

```typescript
interface Memory {
    id: string;
    memory: string;
    user_id?: string;
    agent_id?: string;
    run_id?: string;
    metadata?: Record<string, any>;
    categories?: string[];
    created_at: string;
    updated_at: string;
    score?: number;  // Only in search results
}
```

## Vercel AI SDK Integration

For Next.js and Vercel AI SDK users, see [integration-patterns.md](integration-patterns.md#vercel-ai-sdk).
