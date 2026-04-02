# @mem0/openclaw-mem0

Long-term memory plugin for [OpenClaw](https://github.com/openclaw/openclaw) agents, powered by [Mem0](https://mem0.ai).

Your agent forgets everything between sessions. This plugin fixes that. It watches conversations, extracts what matters, and brings it back when relevant — automatically.

## How it works

The plugin registers two lifecycle hooks:

- **`before_agent_start`** — Searches Mem0 for memories matching the current message and injects them into context (auto-recall).
- **`agent_end`** — Filters the conversation through a noise-removal pipeline, then sends the cleaned exchange to Mem0 for extraction. New facts are stored, stale ones updated, duplicates merged (auto-capture).

Both run automatically. No manual calls, no prompting needed.

![Architecture](https://raw.githubusercontent.com/mem0ai/mem0/main/docs/images/openclaw-architecture.png)

## Installation

```bash
openclaw plugins install @mem0/openclaw-mem0
```

## Configuration

### Platform (Mem0 Cloud)

Get an API key from [app.mem0.ai](https://app.mem0.ai), then add to your `openclaw.json`:

```json5
// plugins.entries
"openclaw-mem0": {
  "enabled": true,
  "config": {
    "apiKey": "${MEM0_API_KEY}",
    "userId": "alice"  // any unique identifier you choose for this user
  }
}
```

### Open-Source (Self-hosted)

No Mem0 key needed. Requires `OPENAI_API_KEY` for default embeddings/LLM.

```json5
"openclaw-mem0": {
  "enabled": true,
  "config": {
    "mode": "open-source",
    "userId": "alice"
  }
}
```

Customize providers with the optional `oss` block:

```json5
"config": {
  "mode": "open-source",
  "userId": "alice",
  "oss": {
    "embedder": { "provider": "openai", "config": { "model": "text-embedding-3-small" } },
    "vectorStore": { "provider": "qdrant", "config": { "host": "localhost", "port": 6333 } },
    "llm": { "provider": "openai", "config": { "model": "gpt-4o" } }
  }
}
```

All `oss` fields are optional. See [Mem0 OSS docs](https://docs.mem0.ai/open-source/node-quickstart) for supported providers.

## Memory scopes

| Scope | Persistence | Description |
| ----- | ----------- | ----------- |
| **Long-term** | Across all sessions | User-scoped facts and preferences. Default for `memory_store`. |
| **Session** | Current conversation | Short-term context via `run_id`. Auto-recalled alongside long-term memories. |

## Registered tools

| Tool | Description |
| ---- | ----------- |
| `memory_search` | Search memories by natural language. Optional `agentId` to scope to a specific agent, `scope` to filter by session/long-term. |
| `memory_store` | Save a fact. Optional `agentId` to store under a specific agent's namespace, `longTerm` to choose scope (default: `true`). |
| `memory_list` | List all stored memories. Optional `agentId` and `scope` to filter. |
| `memory_get` | Retrieve a memory by ID. |
| `memory_forget` | Delete by ID or by query. Optional `agentId` to scope deletion. |

## Multi-agent support

In multi-agent setups, each agent automatically gets its own memory namespace. Session keys matching `agent:<name>:<uuid>` are namespaced under `userId:agent:<name>`. Single-agent deployments are unaffected.

Query another agent's memories:

```javascript
memory_search({ query: "user's tech stack", agentId: "researcher" })
```

## CLI

```bash
openclaw mem0 search "what languages does the user know"
openclaw mem0 search "preferences" --scope long-term
openclaw mem0 search "preferences" --agent researcher
openclaw mem0 stats
```

## Configuration reference

### General

| Key | Type | Default | Description |
| --- | ---- | ------- | ----------- |
| `mode` | `"platform"` \| `"open-source"` | `"platform"` | Backend to use |
| `userId` | `string` | `"default"` | Unique user identifier. All memories are scoped to this value. |
| `autoRecall` | `boolean` | `true` | Inject memories before each turn |
| `autoCapture` | `boolean` | `true` | Extract and store facts after each turn |
| `topK` | `number` | `5` | Max memories to recall per turn |
| `searchThreshold` | `number` | `0.5` | Minimum similarity score (0-1) |

### Platform mode

| Key | Type | Default | Description |
| --- | ---- | ------- | ----------- |
| `apiKey` | `string` | — | **Required.** Mem0 API key (supports `${MEM0_API_KEY}`) |
| `orgId` | `string` | — | Organization ID |
| `projectId` | `string` | — | Project ID |
| `enableGraph` | `boolean` | `false` | Entity graph for relationship tracking |
| `customInstructions` | `string` | *(built-in)* | Custom extraction rules |
| `customCategories` | `object` | *(12 defaults)* | Category name-to-description map for tagging |

### Open-source mode

All fields optional. Defaults: OpenAI embeddings, in-memory vector store, OpenAI LLM.

| Key | Type | Default | Description |
| --- | ---- | ------- | ----------- |
| `customPrompt` | `string` | *(built-in)* | Custom extraction prompt |
| `oss.embedder.provider` | `string` | `"openai"` | `"openai"`, `"ollama"`, `"lmstudio"`, etc. |
| `oss.embedder.config` | `object` | — | Provider config: `apiKey`, `model`, `baseURL` |
| `oss.vectorStore.provider` | `string` | `"memory"` | `"memory"`, `"qdrant"`, `"chroma"`, etc. |
| `oss.vectorStore.config` | `object` | — | Provider config: `host`, `port`, `collectionName` |
| `oss.llm.provider` | `string` | `"openai"` | `"openai"`, `"anthropic"`, `"ollama"`, etc. |
| `oss.llm.config` | `object` | — | Provider config: `apiKey`, `model`, `baseURL` |
| `oss.historyDbPath` | `string` | — | SQLite path for memory edit history |

## License

Apache 2.0
