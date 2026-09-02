# Mem0 TypeScript SDK

[![npm version](https://img.shields.io/npm/v/mem0ai.svg)](https://www.npmjs.com/package/mem0ai)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/mem0ai/mem0/blob/main/LICENSE)

Mem0 gives AI assistants and agents persistent memory. It extracts useful facts from conversations, scopes them to a user, agent, or run, and retrieves the relevant facts for later interactions. The `mem0ai` package includes `MemoryClient` for the hosted Mem0 Platform and `Memory` for open-source, in-process memory.

## Requirements

- Hosted `MemoryClient`: Node.js 18 or later and `MEM0_API_KEY` from the [Mem0 dashboard](https://app.mem0.ai/dashboard/api-keys)
- Open-source `Memory` with the default storage: Node.js 20 or later because `better-sqlite3` v12 requires Node 20+
- Open source with the default providers: `OPENAI_API_KEY`

## Install

```bash
npm install mem0ai
```

## Platform or open source

|                     | Platform (`MemoryClient`)               | Open source (`Memory`)                                                |
| ------------------- | --------------------------------------- | --------------------------------------------------------------------- |
| Import              | `import { MemoryClient } from "mem0ai"` | `import { Memory } from "mem0ai/oss"`                                 |
| Where memories live | Mem0's hosted API                       | Your configured vector store                                          |
| Required key        | `MEM0_API_KEY`                          | `OPENAI_API_KEY` with the defaults, or keys for your chosen providers |
| Extraction          | Managed and asynchronous                | Runs against your configured LLM                                      |
| Best for            | Zero-ops production use                 | Local development and custom infrastructure                           |

## Platform quickstart

Set `MEM0_API_KEY`, then add a conversation:

```ts
import { MemoryClient, type Message } from "mem0ai";

const client = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });

const messages: Message[] = [
  { role: "user", content: "I am vegetarian and allergic to nuts." },
  { role: "assistant", content: "I will remember that." },
];
await client.add(messages, { userId: "alex" });
```

Hosted `add()` queues extraction and usually returns an `eventId` with `status: "PENDING"`. Do not search immediately after `add()`. Wait for processing to finish in the dashboard, or use a [`memory_add` webhook](https://docs.mem0.ai/platform/features/webhooks), then search:

```ts
import { MemoryClient } from "mem0ai";

const client = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });
const results = await client.search("What does Alex eat?", {
  filters: { user_id: "alex" },
  topK: 5,
});
console.log(results.results);
```

`search()` and `getAll()` take entity IDs inside `filters` with snake_case keys. `add()` and `deleteAll()` take `userId`, `agentId`, or `runId` as top-level camelCase options.

## Open-source quickstart

Set `OPENAI_API_KEY` before using the default OpenAI LLM and embedder:

```ts
import { Memory } from "mem0ai/oss";

const memory = new Memory();

const messages = [
  { role: "user", content: "I am vegetarian and allergic to nuts." },
  { role: "assistant", content: "I will remember that." },
];
await memory.add(messages, { userId: "alex" });

const results = await memory.search("What does Alex eat?", {
  filters: { user_id: "alex" },
  topK: 5,
});
console.log(results.results);
```

The default `Memory` configuration uses OpenAI `gpt-5-mini`, OpenAI `text-embedding-3-small`, a SQLite-backed vector store at `~/.mem0/vector_store.db`, and a SQLite history database at `memory.db`.

## Configuration and features

Pass a config object to `Memory` to change providers or storage:

```ts
import { Memory } from "mem0ai/oss";

const memory = new Memory({
  llm: {
    provider: "anthropic",
    config: {
      apiKey: process.env.ANTHROPIC_API_KEY,
      model: "claude-sonnet-4-5",
    },
  },
  embedder: {
    provider: "openai",
    config: {
      apiKey: process.env.OPENAI_API_KEY,
      model: "text-embedding-3-small",
    },
  },
  vectorStore: {
    provider: "qdrant",
    config: {
      collectionName: "memories",
      host: "localhost",
      port: 6333,
      dimension: 1536,
    },
  },
});
```

Provider integrations use a mix of bundled dependencies and peer dependencies. OpenAI is bundled. Most provider peers are optional, but `package.json` also declares required peers such as `better-sqlite3`, `pg`, `compromise`, and `natural`. Install the SDK for any optional provider you configure.

### Memory operations

Both clients expose asynchronous memory operations. The open-source methods finish their work before resolving. Hosted `add()` only confirms that the extraction job was queued.

| Operation              | Platform                            | Open source                         |
| ---------------------- | ----------------------------------- | ----------------------------------- |
| Add                    | `client.add(messages, { userId })`  | `memory.add(messages, { userId })`  |
| Search                 | `client.search(query, { filters })` | `memory.search(query, { filters })` |
| List                   | `client.getAll({ filters })`        | `memory.getAll({ filters })`        |
| Get                    | `client.get(memoryId)`              | `memory.get(memoryId)`              |
| Update                 | `client.update(memoryId, { text })` | `memory.update(memoryId, { text })` |
| Delete                 | `client.delete(memoryId)`           | `memory.delete(memoryId)`           |
| Delete scoped memories | `client.deleteAll({ userId })`      | `memory.deleteAll({ userId })`      |
| History                | `client.history(memoryId)`          | `memory.history(memoryId)`          |

### Filters

Use snake_case keys inside `filters`. A flat object combines conditions with AND. Use `AND`, `OR`, or `NOT` for explicit grouping:

```ts
const filters = {
  AND: [{ user_id: "alex" }, { categories: { contains: "food" } }],
};
```

Pass this object as `filters` to `search()` or `getAll()`.

Comparison operators include `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `contains`, and `icontains`. Open-source `Memory` also supports `nin`. See [memory filters](https://docs.mem0.ai/platform/features/v2-memory-filters).

### Platform features

`MemoryClient` also supports users, batch operations, project settings, webhooks, feedback, and memory exports. See the [Platform API reference](https://docs.mem0.ai/api-reference).

### Open-source providers

The TypeScript SDK supports configurable LLMs, embedders, vector stores, history stores, and rerankers. See the [Node quickstart](https://docs.mem0.ai/open-source/node-quickstart) and [component documentation](https://docs.mem0.ai/components/llms/overview) for supported provider names and configuration.

### CLI and integrations

Use the Node CLI to manage hosted memories from your terminal:

```bash
npm install -g @mem0/cli
```

See the [CLI reference](https://docs.mem0.ai/platform/cli) and [Vercel AI SDK integration](https://docs.mem0.ai/integrations/vercel-ai-sdk).

## Documentation and help

- [Node quickstart](https://docs.mem0.ai/open-source/node-quickstart)
- [Platform quickstart](https://docs.mem0.ai/platform/quickstart)
- [API reference](https://docs.mem0.ai/api-reference)
- [Discord](https://mem0.dev/DiG)
- [GitHub issues](https://github.com/mem0ai/mem0/issues)
- Email: founders@mem0.ai

## Contributing

Read [CONTRIBUTING.md](../CONTRIBUTING.md) before opening an issue or pull request.

## License

Apache 2.0. See [LICENSE](../LICENSE).
