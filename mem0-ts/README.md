# mem0ai

[![npm version](https://img.shields.io/npm/v/mem0ai.svg)](https://www.npmjs.com/package/mem0ai)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://github.com/mem0ai/mem0/blob/main/LICENSE)

Mem0 is a memory layer for AI agents: it extracts, stores, and retrieves facts from conversations so an LLM app can stay personalized across sessions instead of re-reading the full chat history on every call. This package gives you two clients: a hosted `MemoryClient` backed by the Mem0 Platform, and a self-hosted `Memory` you run in-process against your own LLM, embedder, and vector store.

Docs: [Node quickstart](https://docs.mem0.ai/open-source/node-quickstart) · [Platform quickstart](https://docs.mem0.ai/platform/quickstart) · [API reference](https://docs.mem0.ai/api-reference)

## Install

```bash
npm install mem0ai
```

Requires Node 18 or later.

## Platform or open source

|                     | Platform (`MemoryClient`)                                                                    | Open source (`Memory`)                                                                         |
| ------------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Import              | `import { MemoryClient } from "mem0ai"`                                                      | `import { Memory } from "mem0ai/oss"`                                                          |
| Where memories live | Mem0's hosted API                                                                            | Your own vector store, in-process                                                              |
| Setup               | `MEM0_API_KEY` from [app.mem0.ai/dashboard/api-keys](https://app.mem0.ai/dashboard/api-keys) | `OPENAI_API_KEY` (default LLM and embedder), or any [supported provider](#supported-providers) |
| Extraction          | Managed, asynchronous, includes graph memory                                                 | Runs against the LLM you configure, no graph memory                                            |

## Platform quickstart

```ts
import { MemoryClient, type Message } from "mem0ai";

const client = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });

const messages: Message[] = [
  { role: "user", content: "I'm a vegetarian and I'm allergic to nuts." },
  { role: "assistant", content: "Got it, I'll remember that." },
];

await client.add(messages, { userId: "alex" });
```

`add()` queues extraction and returns `{ eventId, status: "PENDING" }` right away. The extracted memories become searchable a few seconds later:

```ts
const found = await client.search("What does Alex eat?", {
  filters: { user_id: "alex" },
  topK: 5,
});

const page = await client.getAll({
  filters: { user_id: "alex" },
  pageSize: 20,
});

const memory = await client.get(found.results[0].id);
const history = await client.history(memory.id);

await client.update(memory.id, {
  text: "Alex is a vegetarian, allergic to nuts and shellfish.",
});
await client.delete(memory.id);
await client.deleteAll({ userId: "alex" });
```

Note that `search` and `getAll` reject top-level `userId`/`agentId`/`appId`/`runId`: those go inside `filters`, and `filters` keys are always snake_case (`user_id`, not `userId`). `add` and `deleteAll` are the opposite: they take entity ids as top-level camelCase options.

### More platform operations

```ts
import { MemoryClient, Feedback, WebhookEvent } from "mem0ai";

const client = new MemoryClient({ apiKey: process.env.MEM0_API_KEY! });

const users = await client.users();
await client.deleteUsers({ userId: "alex" });

await client.batchUpdate([{ memoryId: "mem-1", text: "Updated text" }]);
await client.batchDelete(["mem-1", "mem-2"]);

const project = await client.getProject({
  fields: ["customInstructions", "customCategories"],
});
await client.updateProject({ customInstructions: "Always answer in French." });

const webhook = await client.createWebhook({
  name: "memory-events",
  url: "https://example.com/webhooks/mem0",
  eventTypes: [WebhookEvent.MEMORY_ADDED, WebhookEvent.MEMORY_UPDATED],
});
await client.deleteWebhook({ webhookId: webhook.webhookId! });

await client.feedback({ memoryId: "mem-1", feedback: Feedback.POSITIVE });

const { id: exportId } = await client.createMemoryExport({
  schema: { name: "string", preferences: "string[]" },
  filters: { user_id: "alex" },
});
const exportResult = await client.getMemoryExport({ memoryExportId: exportId });

await client.ping();
```

`getProject`/`updateProject` need an API key scoped to a single organization and project. `getWebhooks`/`createWebhook` resolve the project from the client automatically; there is no `projectId` field on the create payload.

## Open source quickstart

```ts
import { Memory } from "mem0ai/oss";

const memory = new Memory();

const messages = [
  { role: "user", content: "I'm a vegetarian and I'm allergic to nuts." },
  { role: "assistant", content: "Got it, I'll remember that." },
];

await memory.add(messages, { userId: "alex" });

const found = await memory.search("What does Alex eat?", {
  filters: { user_id: "alex" },
});
const all = await memory.getAll({ filters: { user_id: "alex" } });

await memory.update(
  found.results[0].id,
  "Alex is a vegetarian, allergic to nuts and shellfish.",
);
const history = await memory.history(found.results[0].id);
await memory.delete(found.results[0].id);
await memory.reset();
```

With no config, `Memory` uses OpenAI `gpt-5-mini` for extraction, OpenAI `text-embedding-3-small` for embeddings, an in-memory (non-persistent) vector store, and a SQLite history log at `memory.db`. `add`, `search`, and `getAll` all require at least one of `userId`/`agentId`/`runId` (top-level for `add`, inside `filters` as `user_id`/`agent_id`/`run_id` for `search` and `getAll`).

### Chat loop example

```ts
import OpenAI from "openai";
import { Memory } from "mem0ai/oss";

const openai = new OpenAI();
const memory = new Memory();

async function chatWithMemories(
  message: string,
  userId = "default_user",
): Promise<string> {
  const relevant = await memory.search(message, {
    filters: { user_id: userId },
    topK: 3,
  });
  const memoriesStr = relevant.results
    .map((entry) => `- ${entry.memory}`)
    .join("\n");

  const systemPrompt = `You are a helpful AI. Answer the question based on query and memories.\nUser Memories:\n${memoriesStr}`;
  const messages = [
    { role: "system" as const, content: systemPrompt },
    { role: "user" as const, content: message },
  ];

  const response = await openai.chat.completions.create({
    model: "gpt-5-mini",
    messages,
  });
  const assistantResponse = response.choices[0].message.content ?? "";

  await memory.add(
    [...messages, { role: "assistant" as const, content: assistantResponse }],
    { userId },
  );

  return assistantResponse;
}
```

Requires `npm install openai` alongside `mem0ai`.

### Configuration

Pass a config object to `new Memory()` to swap the LLM, embedder, vector store, history store, or reranker:

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
  reranker: {
    provider: "cohere",
    config: {
      apiKey: process.env.COHERE_API_KEY,
      model: "rerank-english-v3.0",
    },
  },
  historyDbPath: "memory.db",
});
```

Set `rerank: true` on `search()` to use the configured reranker. There is no `graphStore` option: graph memory is a Platform-only feature, not part of the OSS TypeScript SDK.

### Supported providers

Provider SDKs are optional peer dependencies. Install the package for the provider you use (for example `npm install @qdrant/js-client-rest` for Qdrant); the rest stay out of your bundle.

| Kind          | Provider strings                                                                                                                                                                                                                                                                                                                                               |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LLMs          | `openai`, `openai_structured`, `anthropic`, `groq`, `mistral`, `google` (`gemini`), `azure_openai`, `ollama`, `lmstudio`, `together`, `deepseek`, `xai`, `sarvam`, `aws_bedrock`, `litellm`, `minimax`, `vllm`, `langchain`                                                                                                                                    |
| Embedders     | `openai`, `azure_openai`, `google` (`gemini`), `aws_bedrock`, `vertexai`, `huggingface`, `fastembed`, `ollama`, `lmstudio`, `together`, `langchain`                                                                                                                                                                                                            |
| Vector stores | `memory`, `qdrant`, `chroma`, `pgvector`, `pinecone`, `milvus`, `mongodb`, `weaviate`, `redis`, `valkey`, `supabase`, `cassandra`, `elasticsearch`, `opensearch`, `turbopuffer`, `upstash_vector`, `vectorize`, `s3_vectors`, `baidu`, `databricks`, `oracledb`, `azure-ai-search`, `azure_mysql`, `neptune-analytics`, `vertex_ai_vector_search`, `langchain` |
| Rerankers     | `cohere`, `zero_entropy`, `llm_reranker`, `sentence_transformer`, `huggingface`                                                                                                                                                                                                                                                                                |

## Filters

`filters` selects which memories a search, `getAll`, or export applies to. Keys are snake_case. A flat object ANDs its keys together; wrap conditions in `AND`/`OR` for explicit grouping:

```ts
{ filters: { user_id: "alex", categories: { contains: "food" } } }

{
  filters: {
    OR: [{ agent_id: "assistant-1" }, { run_id: "session-42" }],
  },
}
```

Comparison operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `contains`, `icontains`. The open-source `Memory` also supports `nin`; the Platform client does not. See [Memory filters](https://docs.mem0.ai/platform/features/v2-memory-filters) for the full grammar.

## CLI and integrations

```bash
npm install -g @mem0/cli
```

The CLI wraps both clients from your shell. See [CLI reference](https://docs.mem0.ai/platform/cli).

Using the Vercel AI SDK? See the [Vercel AI SDK integration](https://docs.mem0.ai/integrations/vercel-ai-sdk).

## License

Apache-2.0

## Getting Help

If you have any questions or need assistance, please reach out to us:

- Email: founders@mem0.ai
- [Join our discord community](https://mem0.ai/discord)
- GitHub Issues: [Report bugs or request features](https://github.com/mem0ai/mem0/issues)
