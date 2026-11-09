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

**Constructor:** `new MemoryClient({ apiKey, host?, identityCacheMax? })`. `apiKey` is required: the constructor throws `Mem0 API key is required` when it is missing or empty. There is no `MEM0_API_KEY` environment fallback, so pass `apiKey: process.env.MEM0_API_KEY` yourself.

- Also a named export: `import { MemoryClient, Feedback, WebhookEvent } from 'mem0ai'`
- HTTP library: native `fetch` (the axios instance in `mem0.ts` is unused)
- Timeout: none set by the SDK
- Base URL: `https://api.mem0.ai` (override with `host`)
- All methods are async (return `Promise`)
- Top-level option names are camelCase and responses come back camelCased (`event_id` becomes `eventId`). Keys inside `filters` are sent as written, so keep them snake_case (`user_id`).
- `MEM0_SOURCE`, `MEM0_APPLICATION` and `MEM0_CLIENT_STACK` set the surface-identity headers for wrappers that cannot pass options.

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
| `options.infer` | boolean | If false, store messages as-is without extraction (default: true) |
| `options.customCategories` | `{[name]: description}[]` | Per-call category list |
| `options.customInstructions` | string | Per-call extraction instructions |
| `options.agentCustomInstructions` | string | Per-call extraction instructions for agent-scoped memories |
| `options.timestamp` | number | Unix timestamp (seconds) to record as the memory time |
| `options.expirationDate` | string | Date after which the memory is no longer returned |
| `options.structuredDataSchema` | object | Schema for structured extraction |

**Returns:** typed `Promise<Array<Memory>>`, but the v3 API queues extraction and responds with `{ status: 'PENDING', eventId }`. With `infer: false` the call is synchronous and the response carries `message`, `status` and `results`. The client has no event-polling method (REST `GET /v1/event/{event_id}/`, see `../references/api-reference.md`).

#### search(query, options?)

Search memories by semantic similarity.

```typescript
const results = await client.search('dietary preferences', { filters: { user_id: 'alice' }, topK: 10 });
for (const mem of results.results) {
    console.log(mem.memory, mem.score);
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Natural language search query |
| `options.filters` | object | Filter object with entity IDs (`user_id`, `agent_id`, etc.) and/or `AND`/`OR`/`NOT` conditions |
| `options.topK` | number | Number of results (default: 10) |
| `options.rerank` | boolean | Enable semantic reranking (default: false) |
| `options.threshold` | number | Server-side relevance cutoff (0 to 1), applied before score blending, so it is not a floor on the returned `score`. Omitting it and passing `0` returned the same results in live tests. Filter on `score` client-side for a precise cutoff |
| `options.latestOnly` | boolean | Return only current (non-superseded) memories |
| `options.fields` | string[] | Not applied in v3 |
| `options.categories` | string[] | Not applied in v3. Use `filters: { AND: [{ categories: { in: [...] } }] }` |
| `options.metadata` | object | Not applied in v3. Use `filters: { AND: [{ metadata: {...} }] }` |
| `options.showExpired` | boolean | Include memories past their expiration date |
| `options.referenceDate` | string \| number | Treat this as "now" for relative time queries |
| `options.keywordSearch` | boolean | Not applied in v3 (removed from the v3 search schema; keyword matching is part of v3 hybrid scoring) |

Entity IDs go inside `filters`. A top-level `userId`, `agentId`, `appId` or `runId` throws.

**Returns:** `Promise<{ results: Array<Memory> }>` -- `{results: [{id, memory, score, ...}]}`

#### get(memoryId)

```typescript
const memory = await client.get('ea925981-...');
```

#### getAll(options?)

Retrieve all memories. Requires non-empty `filters`; scope them with at least one entity identifier.

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
| `options.pageSize` | number | Results per page (default: 100, max: 200) |
| `options.startDate` / `options.endDate` / `options.categories` | - | Not applied in v3. Use `filters` with `created_at` or `categories` |
| `options.latestOnly` | boolean | Return only current (non-superseded) memories |
| `options.showExpired` | boolean | Include memories past their expiration date |

**Returns:** `Promise<{ count, next, previous, results: Array<Memory> }>`

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
| `data.timestamp` | number \| string | New timestamp |
| `data.expirationDate` | string \| null | New expiration date, `null` to clear |

At least one of `text`, `metadata`, `timestamp` or `expirationDate` is required, otherwise the call throws.

#### delete(memoryId, options?)

```typescript
await client.delete('ea925981-...');
await client.delete('ea925981-...', { deleteLinked: true });
```

`deleteLinked: true` also deletes the older memories this one superseded (default: false).

#### deleteAll(options?)

```typescript
await client.deleteAll({ userId: 'alice' });
```

Takes top-level `userId`, `agentId`, `appId`, `runId` (not `filters`).

#### history(memoryId)

```typescript
const history = await client.history('ea925981-...');
// Returns: [{id, memoryId, input, oldMemory, newMemory, event, userId, categories, metadata, createdAt, updatedAt}]
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

Each item must include `text`. `metadata` on a batch item is ignored and a metadata-only item returns a 400. Use `update(memoryId, { metadata })` to change metadata.

#### batchDelete(memories)

```typescript
await client.batchDelete(['uuid-1', 'uuid-2', 'uuid-3']);
```

---

### User/Entity Management

#### users()

```typescript
const users = await client.users({ page: 1, pageSize: 50 });
// Returns: {count, next, previous, totalUsers, totalAgents, totalApps, totalRuns, results: [{id, name, type, createdAt, updatedAt, owner, metadata, isPlayground}, ...]}
```

#### deleteUsers(params)

```typescript
await client.deleteUsers({ userId: 'alice' });
await client.deleteUsers({ agentId: 'bot-1' });
```

Takes one of `userId`, `agentId`, `appId`, `runId`. Calling it with no arguments deletes ALL users, agents, apps and runs, but only those on the first page returned by `users()`: with many entities, re-run it until it throws `No entities to delete`, or page with `users({ page, pageSize })` and delete per entity. `deleteUser({ entity_id, entity_type })` still exists but is deprecated.

---

### Project Management

```typescript
// Get project config
const config = await client.getProject({ fields: ['customCategories'] });

// Update project settings
await client.updateProject({
    customInstructions: 'Extract dietary preferences and health info',
    agentCustomInstructions: 'Extract operational lessons for the agent',
    customCategories: [{ health: 'Medical and dietary info' }],
    decay: true,
});
```

`getProject` requires its options argument (pass `{}` for no field filter). Other `updateProject` keys: `memoryDepth`, `usecaseSetting`, `multilingual`, `version`. Both methods wait for the org and project identity the client resolves at startup and throw if it cannot be resolved.

---

### Webhooks

```typescript
import { WebhookEvent } from 'mem0ai';

// List (projectId is optional, defaults to the project of your API key)
const webhooks = await client.getWebhooks({ projectId: 'proj_123' });

// Create (always uses the project resolved from your API key)
const webhook = await client.createWebhook({
    url: 'https://your-app.com/webhook',
    name: 'Memory Logger',
    eventTypes: [WebhookEvent.MEMORY_ADDED, WebhookEvent.MEMORY_UPDATED],
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
import { Feedback } from 'mem0ai';

await client.feedback({
    memoryId: 'mem-123',
    feedback: Feedback.POSITIVE,
    feedbackReason: 'Accurately captured preference',
});
```

`Feedback` values: `POSITIVE`, `NEGATIVE`, `VERY_NEGATIVE`. `feedback` and `feedbackReason` are optional, and `null` clears existing feedback.

---

### Export

```typescript
const exportReq = await client.createMemoryExport({
    schema: { type: 'object', properties: { name: { type: 'string' } } },
    filters: { AND: [{ user_id: 'alice' }] },
    exportInstructions: 'Build a profile from all memories',
});

const result = await client.getMemoryExport({ memoryExportId: exportReq.id });
```

`schema` is an object (not a JSON string) and `schema` and `filters` are both required. `getMemoryExport` needs `memoryExportId` or `filters`.

---

### User Profiles (beta)

```typescript
await client.updateProfileSettings({
    enabled: true,
    schema: { type: 'object', properties: { communication_style: { type: 'string', description: 'How the user prefers to be addressed' } } },
});

const job = await client.generateProfile({ entityId: 'alice' });
const result = await client.getProfile({ entityId: 'alice' });
if (result.status === 'succeeded') console.log(result.profile);
```

Other methods: `getProfileSettings()`, `sampleProfiles({ limit?, idempotencyKey? })`, `getProfileJob(jobIdOrStatusUrl)`. Generation is asynchronous, so branch on `status` (`succeeded`, `pending`, `failed`, `not_enabled`, `insufficient_data`) rather than on an empty `profile`. Every schema property needs a `description`.

---

### TypeScript Types

Key interfaces from `mem0.types.ts`:

```typescript
interface Message { role: 'user' | 'assistant'; content: string | { type: 'image_url'; image_url: { url: string } }; }
interface Memory { id: string; memory?: string; userId?: string; categories?: string[]; score?: number; expirationDate?: string | null; /* ... */ }
interface AddMemoryOptions { userId?: string; agentId?: string; appId?: string; runId?: string; metadata?: object; infer?: boolean; /* ... */ }
interface SearchMemoryOptions { filters?: object; topK?: number; rerank?: boolean; threshold?: number; /* ... */ }
interface GetAllMemoryOptions { filters?: object; page?: number; pageSize?: number; /* ... */ }
interface MemoryHistory { id: string; memoryId: string; oldMemory: string | null; newMemory: string | null; event: string; /* ... */ }
interface FeedbackPayload { memoryId: string; feedback?: Feedback | null; feedbackReason?: string | null; }
interface WebhookCreatePayload { name: string; url: string; eventTypes: WebhookEvent[]; }
```

`Message.content` is typed to allow an `image_url` object, but `/v3/memories/add/` rejects structured content with a 400 (`Not a valid string.`), so pass a plain string (see Multimodal Support in [features.md](../references/features.md)).

Also exported: `DeleteAllMemoryOptions`, `MemoryUpdateBody`, `PromptUpdatePayload`, `Webhook`, `WebhookUpdatePayload`, `User`, `AllUsers`, the profile types, and the error classes `MemoryError`, `AuthenticationError`, `RateLimitError`, `ValidationError`, `MemoryNotFoundError`, `NetworkError`, `ConfigurationError`, `MemoryQuotaExceededError`.

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
        provider: 'openai',        // openai, openai_structured, anthropic, groq, ollama, lmstudio, google (gemini), azure_openai, mistral, langchain, deepseek, xai, sarvam, aws_bedrock, litellm, minimax, together, vllm
        config: {
            model: 'gpt-5-mini',
            apiKey: 'sk-xxx',
        },
    },
    embedder: {
        provider: 'openai',        // openai, aws_bedrock, ollama, lmstudio, together, google (gemini), azure_openai, fastembed, langchain, vertexai, huggingface
        config: {
            model: 'text-embedding-3-small',
            apiKey: 'sk-xxx',
        },
    },
    vectorStore: {
        provider: 'qdrant',        // memory (default), qdrant, chroma, redis, valkey, supabase, langchain, vectorize, azure-ai-search, vertex_ai_vector_search, pgvector, databricks, neptune-analytics, elasticsearch, opensearch, upstash_vector, azure_mysql, cassandra, pinecone, s3-vectors, turbopuffer, milvus, mongodb, weaviate, oracledb, baidu
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

Defaults when omitted: LLM `openai` `gpt-5-mini`, embedder `openai` `text-embedding-3-small`, vector store `memory` (in-process), history `sqlite` at `memory.db`. `reranker` is also accepted (providers `cohere`, `zero_entropy`, `sentence_transformer`, `huggingface`, `llm_reranker`) and applies when `search` is called with `rerank: true`. There is no graph store in the TS OSS SDK.

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
| `config.userId` | string | User identifier (at least one of `userId`, `agentId`, `runId` is required) |
| `config.agentId` | string | Agent identifier |
| `config.runId` | string | Session identifier |
| `config.metadata` | object | Custom key-value pairs |
| `config.filters` | object | Additional filters |
| `config.infer` | boolean | LLM inference (default: true) |
| `config.expirationDate` | string | `YYYY-MM-DD`, expired memories are hidden from `search` and `getAll` |

`config` is a required argument. `config.timestamp` is not supported in OSS (it throws).

**Returns:** `Promise<{results: [...]}>`, each item `{ id, memory, metadata: { event: 'ADD' } }` (the event is under `metadata`, not top-level).

#### search(query, config)

```typescript
const results = await m.search('dietary preferences', { filters: { user_id: 'alice' }, topK: 5 });
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `query` | string | Search query |
| `config.filters` | object | Filter object with entity IDs (`user_id`, `agent_id`, `run_id`, etc.) |
| `config.topK` | number | Max results (default: 20) |
| `config.threshold` | number | Minimum similarity (default: 0.1) |
| `config.rerank` | boolean | Rerank with the configured `reranker` (no-op without one) |
| `config.showExpired` | boolean | Include expired memories (default: false) |

Top-level entity IDs throw. `config.referenceDate` is not supported in OSS (it throws).

#### get(memoryId) / getAll(config) / update(memoryId, data) / delete(memoryId) / deleteAll(config) / history(memoryId)

Same interface patterns, with these differences:
- `getAll({ filters, topK?, showExpired? })` needs an entity ID in `filters` and has no `page`/`pageSize` (`topK` defaults to 20).
- `deleteAll({ userId?, agentId?, runId? })` takes top-level IDs and requires at least one. Use `reset()` to wipe everything.
- `update` takes a string or `{ text?, metadata?, expirationDate? }` and returns `{ message }`.
- `history` returns raw rows `{ id, memory_id, previous_value, new_value, action, created_at, updated_at, is_deleted }` (snake_case, newest first), not the hosted client's `oldMemory` / `newMemory` / `event`.

```typescript
await m.update('mem-id', 'new content');
await m.update('mem-id', { text: 'new content', metadata: { verified: true } });
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
| **Auth** | API key required (`apiKey` option) | No Mem0 API key -- config-based |
| **Execution** | API calls to `api.mem0.ai` | Local execution |
| **Infrastructure** | Fully managed | Self-managed vector DB, embedder, LLM |
| **Param style** | Top-level: `camelCase` (`userId`, `topK`), filter keys: `snake_case` (`user_id`) | Top-level: `camelCase` (`userId`, `topK`), filter keys: `snake_case` (`user_id`) |
| **Batch ops** | `batchUpdate`, `batchDelete` | Not available |
| **Webhooks** | Full CRUD | Not available |
| **Export** | `createMemoryExport` | Not available |
| **Feedback** | `feedback()` | Not available |
| **Project mgmt** | `getProject`, `updateProject` | Not available |
| **User listing** | `users()`, `deleteUsers()` | Not available |
| **Profiles** | `getProfile`, `generateProfile`, profile settings | Not available |
| **History** | Platform-managed | SQLite (configurable) |

---

## v2 Compatibility

If you're migrating from TS SDK 2.x (the pre-V3 line):

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
| `topK` (OSS) | 100 | 20 |
| `threshold` | 0.3 (Platform), none (OSS) | server-side cutoff (Platform), 0.1 (OSS) |
| `rerank` | false (Platform), true (OSS) | false |

Platform `topK` defaults to 10 (max 1000).

**Removed:**
- `OutputFormat` and `API_VERSION` enums
- `organizationId`, `projectId`, `organizationName`, `projectName` from the constructor
- `add()`: `enableGraph`, `asyncMode`, `outputFormat`, `immutable`, `filterMemories`, `batchSize`, `forceAddOnly`, `includes`, `excludes`, `keywordSearch`
- `search()` and `getAll()`: `enableGraph`
- OSS config: `customPrompt` (now `customInstructions`), `enableGraph` and `graphStore`

See the [v2 to v3 migration guide](https://docs.mem0.ai/migration/oss-v2-to-v3) for details.
