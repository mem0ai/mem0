# Mem0 Node.js / TypeScript SDK Reference

Complete reference for the `mem0ai` npm package. Covers both the Platform client (managed API) and the Open Source self-hosted variant.

---

## Platform Client

### Installation

```bash
npm install mem0ai
export MEM0_API_KEY="m0-your-api-key"
```

### MemoryClient

```typescript
import MemoryClient from 'mem0ai';

const client = new MemoryClient({ apiKey: 'm0-xxx' });
```

**Constructor:** `new MemoryClient({ apiKey })`. If `apiKey` is not provided, reads from `MEM0_API_KEY` environment variable.

- HTTP library: `axios`
- Timeout: 60 seconds
- Base URL: `https://api.mem0.ai`
- All methods are async (return `Promise`)

---

### Memory Methods

#### add(messages, options?)

Store new memories from messages.

```typescript
const messages = [
    { role: 'user', content: "I'm a vegetarian and allergic to nuts." },
    { role: 'assistant', content: "Got it! I'll remember that." },
];
await client.add(messages, { userId: 'alice' });
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `messages` | `Message[]` | Array of `{role, content}` objects |
| `options.userId` | string | User identifier |
| `options.agentId` | string | Agent identifier |
| `options.appId` | string | Application identifier |
| `options.runId` | string | Session identifier |
| `options.metadata` | object | Custom key-value pairs |
| `options.infer` | boolean | If false, store raw text (default: true) |

**Returns:** `Promise<any>` -- list of events

#### search(query, options?)

Search memories by semantic similarity.

```typescript
const results = await client.search('dietary preferences', { filters: { user_id: 'alice' }, topK: 20 });
for (const mem of results.results) {
    console.log(mem.memory, mem.score);
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Natural language search query |
| `options.filters` | object | Filter object with entity IDs (`user_id`, `agent_id`, etc.) and/or `AND`/`OR`/`NOT` conditions |
| `options.topK` | number | Number of results (default: 20) |
| `options.rerank` | boolean | Enable semantic reranking (default: false) |
| `options.threshold` | number | Minimum similarity (default: 0.1) |

**Returns:** `Promise<SearchResult>` -- `{results: [{id, memory, score, ...}]}`

#### get(memoryId)

```typescript
const memory = await client.get('ea925981-...');
```

#### getAll(options?)

Retrieve all memories. Requires at least one entity identifier in filters.

```typescript
const memories = await client.getAll({ filters: { user_id: 'alice' } });
// With filters
const filtered = await client.getAll({
    filters: { AND: [{ user_id: 'alice' }, { categories: { contains: 'health' } }] },
});
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `options.filters` | object | Filter object with entity IDs (`user_id`, `agent_id`, etc.) and/or `AND`/`OR`/`NOT` conditions |
| `options.page` | number | Page number |
| `options.pageSize` | number | Results per page |

#### update(memoryId, data)

```typescript
await client.update('ea925981-...', { text: 'Updated: vegan since 2024' });
await client.update('ea925981-...', { text: 'Updated', metadata: { verified: true } });
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `memoryId` | string | Memory ID |
| `data.text` | string | New content |
| `data.metadata` | object | New metadata |
| `data.timestamp` | string | New timestamp |

#### delete(memoryId)

```typescript
await client.delete('ea925981-...');
```

#### deleteAll(options?)

```typescript
await client.deleteAll({ userId: 'alice' });
```

#### history(memoryId)

```typescript
const history = await client.history('ea925981-...');
// Returns: [{previousValue, newValue, action, timestamps}]
```

---

### Batch Methods

#### batchUpdate(memories)

```typescript
await client.batchUpdate([
    { memoryId: 'uuid-1', text: 'Updated text' },
    { memoryId: 'uuid-2', text: 'Another update' },
]);
```

#### batchDelete(memories)

```typescript
await client.batchDelete(['uuid-1', 'uuid-2', 'uuid-3']);
```

---

### User/Entity Management

#### users()

```typescript
const users = await client.users();
// Returns: {results: [{type: "user", name: "alice"}, ...]}
```

#### deleteUser(data) / deleteUsers(data)

```typescript
await client.deleteUser({ userId: 'alice' });  // Single entity
await client.deleteUsers({ agentId: 'bot-1' }); // Flexible
```

---

### Project Management

```typescript
// Get project config
const config = await client.getProject({ fields: ['customCategories'] });

// Update project settings
await client.updateProject({
    customInstructions: 'Extract dietary preferences and health info',
    customCategories: [{ health: 'Medical and dietary info' }],
});
```

---

### Webhooks

```typescript
// List
const webhooks = await client.getWebhooks({ projectId: 'proj_123' });

// Create
const webhook = await client.createWebhook({
    url: 'https://your-app.com/webhook',
    name: 'Memory Logger',
    projectId: 'proj_123',
    eventTypes: ['memory_add', 'memory_update'],
});

// Update
await client.updateWebhook({
    webhookId: 'wh_123',
    name: 'Updated Logger',
    url: 'https://new-url.com',
});

// Delete
await client.deleteWebhook({ webhookId: 'wh_123' });
```

---

### Feedback

```typescript
await client.feedback({
    memoryId: 'mem-123',
    feedback: 'POSITIVE',
    feedbackReason: 'Accurately captured preference',
});
```

---

### Export

```typescript
const exportReq = await client.createMemoryExport({
    schema: JSON.stringify({ type: 'object', properties: { name: { type: 'string' } } }),
    filters: { user_id: 'alice' },
});

const result = await client.getMemoryExport({ memoryExportId: exportReq.id });
```

---

### TypeScript Types

Key interfaces from `mem0.types.ts`:

```typescript
interface Message { role: string; content: string; }
interface Memory { id: string; memory: string; userId: string; categories: string[]; score?: number; /* ... */ }
interface MemoryOptions { userId?: string; agentId?: string; appId?: string; runId?: string; metadata?: object; /* ... */ }
interface SearchOptions { filters?: object; topK?: number; rerank?: boolean; threshold?: number; /* ... */ }
interface MemoryHistory { id: string; memoryId: string; previousValue: string; newValue: string; action: string; /* ... */ }
interface FeedbackPayload { memoryId: string; feedback: string; feedbackReason?: string; }
interface WebhookCreatePayload { url: string; name: string; projectId: string; eventTypes: string[]; }
```

---

## Open Source / Self-Hosted

### Installation

```bash
npm install mem0ai
```

### Memory Class

```typescript
import { Memory } from 'mem0ai/oss';

const m = new Memory();  // Uses default config
```

**Import:** `from 'mem0ai/oss'` (NOT the default export -- that is `MemoryClient` for Platform)

### Configuration

```typescript
const config = {
    llm: {
        provider: 'openai',        // openai, groq, anthropic, google, ollama, lmstudio, mistral, azure
        config: {
            model: 'gpt-5-mini',
            apiKey: 'sk-xxx',
        },
    },
    embedder: {
        provider: 'openai',        // openai, ollama, lmstudio, google, azure, langchain, anthropic
        config: {
            model: 'text-embedding-3-small',
            apiKey: 'sk-xxx',
        },
    },
    vectorStore: {
        provider: 'qdrant',        // memory, qdrant, redis, supabase, langchain, azure_ai_search, pgvector
        config: {
            collectionName: 'my_memories',
            host: 'localhost',
            port: 6333,
        },
    },
    historyDbPath: 'history.db',
    customInstructions: '...',
    disableHistory: false,
};

const m = new Memory(config);
// Or from dict with validation:
const m2 = Memory.fromConfig(config);
```

### Methods

All methods are async (return `Promise`):

#### add(messages, config)

```typescript
await m.add('I prefer dark mode', { userId: 'alice' });
await m.add([
    { role: 'user', content: 'I like hiking' },
    { role: 'assistant', content: 'Great outdoor activity!' },
], { userId: 'alice' });
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `messages` | `string \| Message[]` | Content to store |
| `config.userId` | string | User identifier (at least one scope required) |
| `config.agentId` | string | Agent identifier |
| `config.runId` | string | Session identifier |
| `config.metadata` | object | Custom key-value pairs |
| `config.filters` | object | Additional filters |
| `config.infer` | boolean | LLM inference (default: true) |

**Returns:** `Promise<{results: [...], relations?: [...]}>`

#### search(query, config)

```typescript
const results = await m.search('dietary preferences', { filters: { user_id: 'alice' }, topK: 5 });
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search query |
| `config.filters` | object | Filter object with entity IDs (`user_id`, `agent_id`, `run_id`, etc.) |
| `config.topK` | number | Max results (default: 20) |

#### get(memoryId) / getAll(config) / update(memoryId, data) / delete(memoryId) / deleteAll(config) / history(memoryId)

Same interface patterns. Note: OSS `update` takes a string for data, not an object.

```typescript
await m.update('mem-id', 'new content');
```

#### reset()

Clear the entire vector store and history.

```typescript
await m.reset();
```

---

## Key Differences: Platform vs OSS

| Aspect | Platform (`MemoryClient`) | OSS (`Memory`) |
|--------|--------------------------|----------------|
| **Import** | `import MemoryClient from 'mem0ai'` | `import { Memory } from 'mem0ai/oss'` |
| **Auth** | API key required (`MEM0_API_KEY`) | No API key -- config-based |
| **Execution** | API calls to `api.mem0.ai` | Local execution |
| **Infrastructure** | Fully managed | Self-managed vector DB, embedder, LLM |
| **Param style** | Top-level: `camelCase` (`userId`, `topK`), filter keys: `snake_case` (`user_id`) | Top-level: `camelCase` (`userId`, `topK`), filter keys: `snake_case` (`user_id`) |
| **Batch ops** | `batchUpdate`, `batchDelete` | Not available |
| **Webhooks** | Full CRUD | Not available |
| **Export** | `createMemoryExport` | Not available |
| **Feedback** | `feedback()` | Not available |
| **Project mgmt** | `getProject`, `updateProject` | Not available |
| **User listing** | `users()`, `deleteUser()` | Not available |
| **History** | Platform-managed | SQLite (configurable) |

---

## v2 Compatibility

If you're using SDK v2.x:

**Naming Changes:**
- Top-level params now use camelCase: `topK`, `rerank` (not `top_k`)
- Filter keys use snake_case: `user_id`, `agent_id`
- OSS: `limit` renamed to `topK`

**API Changes:**
```typescript
// v2 - top-level entity IDs, snake_case
await client.search("query", { user_id: "alice", top_k: 20 });

// v3 - filters object with snake_case keys, camelCase top-level params
await client.search("query", { filters: { user_id: "alice" }, topK: 20 });
```

**Default Changes:**
| Param | v2 | v3 |
|-------|----|----|
| `topK` | 100 | 20 |
| `threshold` | none | 0.1 |
| `rerank` | true | false |

**Removed:**
- `OutputFormat` and `API_VERSION` enums
- `organizationId`, `projectId` from constructor
- `enableGraph`, `asyncMode`, `outputFormat`, `immutable`, `expirationDate`, `filterMemories`, `batchSize`, `forceAddOnly`, `includes`, `excludes`, `keywordSearch`

See the [v2 to v3 migration guide](https://docs.mem0.ai/migration/oss-v2-to-v3) for details.
