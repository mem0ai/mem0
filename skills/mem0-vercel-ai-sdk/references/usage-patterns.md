# Usage Patterns and Examples

Working examples for `@mem0/vercel-ai-provider`. All examples assume environment variables `MEM0_API_KEY` and the relevant LLM provider API key are set.

## 1. Wrapped Model with generateText (Basic)

The simplest way to add memory to any LLM call.

```typescript
import { generateText } from "ai";
import { createMem0 } from "@mem0/vercel-ai-provider";

const mem0 = createMem0();

const { text } = await generateText({
  model: mem0("gpt-5-mini", { user_id: "alice" }),
  prompt: "Recommend a restaurant based on my preferences",
});

console.log(text);
```

The prompt is stored to Mem0 and relevant memories are retrieved before the LLM call (see section 8).

## 2. Wrapped Model with streamText (Streaming)

Stream responses with automatic memory augmentation.

```typescript
import { streamText } from "ai";
import { createMem0 } from "@mem0/vercel-ai-provider";

const mem0 = createMem0();

const result = streamText({
  model: mem0("gpt-5-mini", { user_id: "alice" }),
  prompt: "What should I cook for dinner tonight?",
});

for await (const chunk of result.textStream) {
  process.stdout.write(chunk);
}
```

The add request and the memory search both finish before streaming begins (extraction itself is async). The Mem0 source (`sources`) is only attached by `generateText`, not by streaming.

## 3. Standalone Utilities with OpenAI

Full control over the memory lifecycle using standalone functions with OpenAI.

```typescript
import { openai } from "@ai-sdk/openai";
import { generateText } from "ai";
import { retrieveMemories, addMemories } from "@mem0/vercel-ai-provider";

const user_id = "alice";
const prompt = "Suggest a weekend trip";

// Step 1: Retrieve memories as a formatted system prompt
const memories = await retrieveMemories(prompt, {
  user_id: user_id,
});

// Step 2: Generate with the memories injected as system context
const { text } = await generateText({
  model: openai("gpt-5-mini"),
  prompt,
  system: memories,
});

console.log(text);

// Step 3: Store the conversation as new memories
await addMemories(
  [
    { role: "user", content: [{ type: "text", text: prompt }] },
    { role: "assistant", content: [{ type: "text", text }] },
  ],
  { user_id: user_id }
);
```

## 4. Standalone Utilities with Anthropic

Same pattern, different LLM provider.

```typescript
import { anthropic } from "@ai-sdk/anthropic";
import { generateText } from "ai";
import { retrieveMemories, addMemories } from "@mem0/vercel-ai-provider";

const prompt = "Help me plan my exercise routine";
const config = { user_id: "bob" };

const memories = await retrieveMemories(prompt, config);

const { text } = await generateText({
  model: anthropic("claude-sonnet-4-20250514"),
  prompt,
  system: memories,
});

await addMemories(
  [
    { role: "user", content: [{ type: "text", text: prompt }] },
    { role: "assistant", content: [{ type: "text", text }] },
  ],
  config
);
```

## 5. Structured Output with generateObject

Use with `generateObject` for typed, structured responses enriched with memory.

```typescript
import { generateObject } from "ai";
import { createMem0 } from "@mem0/vercel-ai-provider";
import { z } from "zod";

const mem0 = createMem0();

const { object } = await generateObject({
  model: mem0("gpt-5-mini", { user_id: "alice" }),
  prompt: "Suggest a meal plan for today",
  schema: z.object({
    breakfast: z.string(),
    lunch: z.string(),
    dinner: z.string(),
    snacks: z.array(z.string()),
    notes: z.string().describe("Personalization notes based on known preferences"),
  }),
});

console.log(object);
// { breakfast: "Avocado toast (you mentioned loving it)", lunch: "...", ... }
```

The wrapped model forwards all call options (including the response format) to the underlying provider, so structured output works out of the box. `generateObject` is deprecated in AI SDK v6 in favor of `generateText` with `output: Output.object({ schema })`; both go through the same wrapped model.

## 6. Multi-Provider Setup

Configure different LLM providers with the wrapped model.

### OpenAI (default)

```typescript
import { createMem0 } from "@mem0/vercel-ai-provider";

const mem0 = createMem0(); // defaults to "openai"
const model = mem0("gpt-5-mini", { user_id: "alice" });
```

### Anthropic

```typescript
const mem0 = createMem0({ provider: "anthropic" });
const model = mem0("claude-sonnet-4-20250514", { user_id: "alice" });
```

### Google

```typescript
const mem0 = createMem0({ provider: "google" });
const model = mem0("gemini-2.0-flash", { user_id: "alice" });
```

### Groq

```typescript
const mem0 = createMem0({ provider: "groq" });
const model = mem0("llama-3.3-70b-versatile", { user_id: "alice" });
```

### Cohere

```typescript
const mem0 = createMem0({ provider: "cohere" });
const model = mem0("command-r-plus", { user_id: "alice" });
```

### With explicit API keys (no env vars)

```typescript
const mem0 = createMem0({
  provider: "openai",
  apiKey: "sk-xxx",       // OpenAI API key
  mem0ApiKey: "m0-xxx",   // Mem0 API key
});
```

## 7. Next.js API Route Integration

A POST handler that uses the wrapped model in a Next.js App Router API route.

```typescript
// app/api/chat/route.ts
import { convertToModelMessages, streamText, UIMessage } from "ai";
import { createMem0 } from "@mem0/vercel-ai-provider";

const mem0 = createMem0();

export async function POST(req: Request) {
  const { messages, user_id }: { messages: UIMessage[]; user_id: string } = await req.json();

  const result = streamText({
    model: mem0("gpt-5-mini", { user_id }),
    messages: await convertToModelMessages(messages),
  });

  return result.toUIMessageStreamResponse();
}
```

### With standalone utilities for more control

```typescript
// app/api/chat/route.ts
import { openai } from "@ai-sdk/openai";
import { convertToModelMessages, streamText, UIMessage } from "ai";
import { retrieveMemories, addMemories } from "@mem0/vercel-ai-provider";

export async function POST(req: Request) {
  const { messages, user_id }: { messages: UIMessage[]; user_id: string } = await req.json();
  const lastMessage = messages[messages.length - 1];
  const lastText = lastMessage.parts
    .flatMap((part) => (part.type === "text" ? [part.text] : []))
    .join(" ");

  // Retrieve relevant memories
  const memories = await retrieveMemories(lastText, {
    user_id,
  });

  // Stream the response
  const result = streamText({
    model: openai("gpt-5-mini"),
    messages: await convertToModelMessages(messages),
    system: memories,
  });

  // Store conversation in the background (fire-and-forget)
  result.text.then(async (text) => {
    await addMemories(
      [
        { role: "user", content: [{ type: "text", text: lastText }] },
        { role: "assistant", content: [{ type: "text", text }] },
      ],
      { user_id }
    );
  });

  return result.toUIMessageStreamResponse();
}
```

## 8. How Memory Processing Works Internally

### Wrapped model flow (doGenerate / doStream)

```
1. doGenerate(options) or doStream(options) is called
2. processMemories(messagesPrompts, mem0Config):
   a. await addMemories(messagesPrompts, mem0Config)
      --> POST /v3/memories/add/ with converted messages
      --> errors are caught and logged
   b. await getMemories(messagesPrompts, mem0Config)
      --> POST /v3/memories/search/ with flattened prompt
      --> returns memory array
   c. Format memories into system message string
   d. If memories were found, prepend the system message to a copy of messagesPrompts
   e. Return { memories, messagesPrompts }
3. Create underlying LLM via Mem0ClassSelector.createProvider()
4. Call model.doGenerate(updatedOptions) or model.doStream(updatedOptions)
5. doGenerate appends the "Mem0 Memories" source when memories were found
6. Return result
```

**Critical detail:** The `addMemories` call in step 2a is **awaited**, meaning:
- The add request is sent (and awaited) before the search and the LLM call, but extraction is async (`/v3/memories/add/` only queues the work and returns `PENDING`), so facts from the current prompt are usually not searchable until a later call
- Each wrapped call adds one Mem0 write and one Mem0 search of latency before the LLM starts
- If the memory write fails, it logs an error and the call continues
- `messagesPrompts` is the full prompt (all roles, including earlier turns), so every call sends the entire conversation to the add endpoint

### Memory injection format

The memories are injected as a system message at position 0 of the prompt array:

```typescript
{
  role: "system",
  content: "System Message: These are the memories I have stored. Give more weightage to the question by users and try to answer that first. You have to modify your answer based on the memories I have provided. If the memories are irrelevant you can ignore them. Also don't reply to this section of the prompt, or the memories, they are only for your reference. The System prompt starts after text System Message: \n\n Memory: ... \n\n Memory: ... \n\n"
}
```

## 9. Custom Configuration

### Custom Mem0 API host

```typescript
const mem0 = createMem0({
  mem0Config: {
    host: "https://my-mem0-instance.example.com",
  },
});
```

Or with standalone utilities:

```typescript
const memories = await retrieveMemories(prompt, {
  user_id: "alice",
  host: "https://my-mem0-instance.example.com",
});
```

### Memory filtering and ranking

```typescript
const mem0 = createMem0();
const model = mem0("gpt-5-mini", {
  user_id: "alice",
  top_k: 20,          // retrieve up to 20 memories (default: 10)
  threshold: 0.8,     // server-side cutoff applied before score blending
  rerank: true,       // enable re-ranking of results
});
```

### Provider-specific configuration

Pass SDK-specific settings via the `config` field:

```typescript
const mem0 = createMem0({
  provider: "openai",
  config: {
    organization: "org-xxx",
    project: "proj-xxx",
  },
});
```

### Default Mem0 config for all calls

Set defaults at the provider level that apply to every model created:

```typescript
const mem0 = createMem0({
  mem0Config: {
    user_id: "alice",
    top_k: 10,
  },
});

// These calls inherit user_id and top_k from mem0Config
const { text } = await generateText({
  model: mem0("gpt-5-mini"),
  prompt: "Hello",
});
```

Per-call settings (passed as the second argument to `mem0()`) are merged on top of `mem0Config`, so you can override specific fields:

```typescript
// Override user_id for this specific call
const model = mem0("gpt-5-mini", { user_id: "bob" });
```

The merge order is: `config.mem0Config` (provider defaults) < `settings` (per-call overrides).
