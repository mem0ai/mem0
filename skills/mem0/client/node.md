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
await client.add(messages, { user_id: 'alice' });
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `messages` | `Message[]` | Array of `{role, content}` objects |
| `options.user_id` | string | User identifier |
| `options.agent_id` | string | Agent identifier |
| `options.app_id` | string | Application identifier |
| `options.run_id` | string | Session identifier |
| `options.metadata` | object | Custom key-value pairs |
| `options.enable_graph` | boolean | Activate knowledge graph |
| `options.infer` | boolean | If false, store raw text (default: true) |
| `options.immutable` | boolean | Prevent future modification |
| `options.expiration_date` | string | Auto-expiry (`YYYY-MM-DD`) |
| `options.includes` | string | Preference filter for inclusion |
| `options.excludes` | string | Preference filter for exclusion |

**Returns:** `Promise<any>` -- list of events

#### search(query, options?)

Search memories by semantic similarity.

```typescript
const results = await client.search('dietary preferences', { user_id: 'alice' });
for (const mem of results.results) {
    console.log(mem.memory, mem.score);
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Natural language search query |
| `options.user_id` | string | Filter by user |
| `options.agent_id` | string | Filter by agent |
| `options.filters` | object | V2 filter object (`AND`/`OR`/`NOT`) |
| `options.top_k` | number | Number of results (default: 10) |
| `options.rerank` | boolean | Enable semantic reranking |
| `options.threshold` | number | Minimum similarity (default: 0.3) |
| `options.keyword_search` | boolean | Enable keyword search |
| `options.enable_graph` | boolean | Include graph relations |
| `options.filter_memories` | boolean | Precision filtering |

**Returns:** `Promise<SearchResult>` -- `{results: [{id, memory, score, ...}], relations: [...]}`

#### get(memoryId)

```typescript
const memory = await client.get('ea925981-...');
```

#### getAll(options?)

Retrieve all memories. Requires at least one entity identifier in filters.

```typescript
const memories = await client.getAll({ user_id: 'alice' });
// With filters
const filtered = await client.getAll({
    filters: { AND: [{ user_id: 'alice' }, { categories: { contains: 'health' } }] },
});
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `options.user_id` | string | Filter by user |
| `options.filters` | object | V2 filter object |
| `options.page` | number | Page number |
| `options.page_size` | number | Results per page |
| `options.enable_graph` | boolean | Include graph relations |

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
await client.deleteAll({ user_id: 'alice' });
```

#### history(memoryId)

```typescript
const history = await client.history('ea925981-...');
// Returns: [{previous_value, new_value, action, timestamps}]
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
await client.deleteUser({ user_id: 'alice' });  // Single entity
await client.deleteUsers({ agent_id: 'bot-1' }); // Flexible
```

---

### Project Management

```typescript
// Get project config
const config = await client.getProject({ fields: ['custom_categories'] });

// Update project settings
await client.updateProject({
    custom_instructions: 'Extract dietary preferences and health info',
    custom_categories: [{ health: 'Medical and dietary info' }],
    enable_graph: true,
});
```

---

### Webhooks

```typescript
// List
const webhooks = await client.getWebhooks({ project_id: 'proj_123' });

// Create
const webhook = await client.createWebhook({
    url: 'https://your-app.com/webhook',
    name: 'Memory Logger',
    project_id: 'proj_123',
    event_types: ['memory_add', 'memory_update'],
});

// Update
await client.updateWebhook({
    webhook_id: 'wh_123',
    name: 'Updated Logger',
    url: 'https://new-url.com',
});

// Delete
await client.deleteWebhook({ webhook_id: 'wh_123' });
```

---

### Feedback

```typescript
await client.feedback({
    memory_id: 'mem-123',
    feedback: 'POSITIVE',
    feedback_reason: 'Accurately captured preference',
});
```

---

### Export

```typescript
const exportReq = await client.createMemoryExport({
    schema: JSON.stringify({ type: 'object', properties: { name: { type: 'string' } } }),
    filters: { user_id: 'alice' },
});

const result = await client.getMemoryExport({ memory_export_id: exportReq.id });
```

---

### TypeScript Types

Key interfaces from `mem0.types.ts`:

```typescript
interface Message { role: string; content: string; }
interface Memory { id: string; memory: string; user_id: string; categories: string[]; score?: number; /* ... */ }
interface MemoryOptions { user_id?: string; agent_id?: string; app_id?: string; run_id?: string; metadata?: object; /* ... */ }
interface SearchOptions { user_id?: string; filters?: object; top_k?: number; rerank?: boolean; threshold?: number; /* ... */ }
interface MemoryHistory { id: string; memory_id: string; previous_value: string; new_value: string; action: string; /* ... */ }
interface FeedbackPayload { memory_id: string; feedback: string; feedback_reason?: string; }
interface WebhookCreatePayload { url: string; name: string; project_id: string; event_types: string[]; }
enum OutputFormat { v1_0 = 'v1.0', v1_1 = 'v1.1' }
enum API_VERSION { v1 = 'v1', v2 = 'v2' }
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
            model: 'gpt-4o-mini',
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
    graphStore: {                   // Optional
        provider: 'neo4j',
        config: {
            url: 'neo4j://localhost:7687',
            username: 'neo4j',
            password: 'password',
        },
    },
    historyDbPath: 'history.db',
    customPrompt: '...',
    enableGraph: false,
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
const results = await m.search('dietary preferences', { userId: 'alice', limit: 5 });
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search query |
| `config.userId` | string | Filter by user |
| `config.agentId` | string | Filter by agent |
| `config.runId` | string | Filter by run |
| `config.limit` | number | Max results (default: 100) |
| `config.filters` | object | Advanced filters |

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
| **Param style** | `snake_case` in options (`user_id`) | `camelCase` in config (`userId`) |
| **Batch ops** | `batchUpdate`, `batchDelete` | Not available |
| **Webhooks** | Full CRUD | Not available |
| **Export** | `createMemoryExport` | Not available |
| **Feedback** | `feedback()` | Not available |
| **Project mgmt** | `getProject`, `updateProject` | Not available |
| **User listing** | `users()`, `deleteUser()` | Not available |
| **Graph store** | Platform-managed | Self-managed (Neo4j) |
| **History** | Platform-managed | SQLite (configurable) |
