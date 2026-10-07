# Memory Utilities Reference

Complete reference for standalone utility functions exported from `@mem0/vercel-ai-provider`. These functions give you manual control over memory retrieval and storage, independent of the wrapped model pattern.

Source: `integrations/vercel-ai-sdk/src/mem0-utils.ts`

## `addMemories(messages, config?)`

Stores messages to Mem0 as new memories.

```typescript
import { addMemories } from "@mem0/vercel-ai-provider";

await addMemories(
  [
    { role: "user", content: [{ type: "text", text: "I love Italian food" }] },
    { role: "assistant", content: [{ type: "text", text: "Noted! I'll remember that." }] },
  ],
  { user_id: "alice", mem0ApiKey: "m0-xxx" }
);
```

**Signature:**

```typescript
async function addMemories(
  messages: LanguageModelV3Prompt,
  config?: Mem0ConfigSettings
): Promise<any>;
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `messages` | `LanguageModelV3Prompt` | Messages to store. A plain string is also handled at runtime (wrapped as `[{ role: "user", content: string }]`) but is not part of the declared type |
| `config` | `Mem0ConfigSettings` | Optional. Must include entity scope (`user_id`, etc.) and API key |

**Behavior:**
1. If `messages` is a string, wraps it as a single user message
2. Otherwise, converts `LanguageModelV3Prompt` to Mem0 format via `convertToMem0Format` (maps multimodal parts, but the add endpoint rejects them with a 400)
3. Calls `POST {host}/v3/memories/add/` with body `{ messages, user_id?, app_id?, agent_id?, run_id?, metadata?, infer? }` (entity IDs are top-level on add)
4. Throws `HTTP error! status: <code>` on a non-2xx response

**Returns:** The parsed JSON response from Mem0. The v3 add endpoint queues extraction and responds with `{ status: "PENDING", event_id }` (the provider returns the raw REST JSON, so keys stay snake_case, unlike the `mem0ai` client). With `infer: false` messages are stored verbatim synchronously and the response also includes `results`.

---

## `retrieveMemories(prompt, config?)`

Retrieves memories and returns a **formatted system prompt string** ready to inject into a `system` parameter.

```typescript
import { retrieveMemories } from "@mem0/vercel-ai-provider";

const systemPrompt = await retrieveMemories("What restaurants do I like?", {
  user_id: "alice",
  mem0ApiKey: "m0-xxx",
});
// Returns: "System Message: These are the memories I have stored... Memory: User loves Italian food\n\n ..."
```

**Signature:**

```typescript
async function retrieveMemories(
  prompt: LanguageModelV3Prompt | string,
  config?: Mem0ConfigSettings
): Promise<string>;
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | `LanguageModelV3Prompt \| string` | The query to search memories for |
| `config` | `Mem0ConfigSettings` | Optional. Entity scope and API key |

**Behavior:**
1. Flattens the prompt to a plain string (extracts text from `LanguageModelV3Prompt` parts)
2. Calls `searchInternalMemories` (`POST /v3/memories/search/`)
3. Accepts either a flat array or a `{ results: [...] }` response and formats each memory as `"Memory: {memory.memory}\n\n"`
4. Wraps everything in a system prompt preamble

**Returns:** A **string** containing the formatted system prompt with embedded memories. Returns `""` (empty string) if no memories found.

**Output format:**
```
System Message: These are the memories I have stored. Give more weightage to the question by users and try to answer that first. You have to modify your answer based on the memories I have provided. If the memories are irrelevant you can ignore them. Also don't reply to this section of the prompt, or the memories, they are only for your reference. The System prompt starts after text System Message:

Memory: User loves Italian food

Memory: User is vegetarian
```

---

## `getMemories(prompt, config?)`

Retrieves memories and returns the **raw memory array**.

```typescript
import { getMemories } from "@mem0/vercel-ai-provider";

const memories = await getMemories("What are my preferences?", {
  user_id: "alice",
  mem0ApiKey: "m0-xxx",
});
// Returns: [{ memory: "User loves Italian food", id: "...", ... }, ...]
```

**Signature:**

```typescript
async function getMemories(
  prompt: LanguageModelV3Prompt | string,
  config?: Mem0ConfigSettings
): Promise<any>;
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | `LanguageModelV3Prompt \| string` | The query to search memories for |
| `config` | `Mem0ConfigSettings` | Optional. Entity scope and API key |

**Behavior:**
1. Flattens the prompt to a plain string
2. Calls `searchInternalMemories` (`POST /v3/memories/search/`)
3. Normalizes the response: returns the response itself if it is an array, otherwise `response.results` (or `[]`)

**Returns:** Flat memory object array.

---

## `searchMemories(prompt, config?)`

Retrieves the **raw search API response** including results, scores, and metadata.

```typescript
import { searchMemories } from "@mem0/vercel-ai-provider";

const response = await searchMemories("cooking preferences", {
  user_id: "alice",
  mem0ApiKey: "m0-xxx",
});
// Returns: { results: [{ memory: "...", score: 0.95, ... }] }
```

**Signature:**

```typescript
async function searchMemories(
  prompt: LanguageModelV3Prompt | string,
  config?: Mem0ConfigSettings
): Promise<any>;
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `prompt` | `LanguageModelV3Prompt \| string` | The query to search memories for |
| `config` | `Mem0ConfigSettings` | Optional. Entity scope and API key |

**Behavior:**
1. Flattens the prompt to a plain string
2. Calls `searchInternalMemories` (`POST /v3/memories/search/`)
3. Returns the response without any normalization

**Returns:** The API response as-is (an object with `results`, or a flat array if the API returns one). On error, logs and returns `[]` instead of throwing (unlike the other utilities, which rethrow).

**Note:** Unlike `getMemories`, this does not unwrap `results`.

---

## When to Use Which Function

| Function | Returns | Use when |
|----------|---------|----------|
| `retrieveMemories` | Formatted system prompt **string** | Injecting directly into a `system` parameter for `generateText`/`streamText` |
| `getMemories` | Memory **array** | Processing memories programmatically (filtering, transforming, counting) |
| `searchMemories` | Raw API **response** | Need similarity scores or complete metadata |
| `addMemories` | API response | Storing new conversation messages as memories |

## Internal: `searchInternalMemories(query, config?, top_k?)`

Not exported. Used by all retrieval functions.

```typescript
async function searchInternalMemories(
  query: string,
  config?: Mem0ConfigSettings,
  top_k: number = 10
): Promise<any>;
```

**Behavior:**
1. Builds a `filters` object from `config.filters`, then sets `user_id`, `app_id`, `agent_id`, `run_id` on it when present (entity IDs go inside `filters`, never top-level)
2. Loads the API key from `config.mem0ApiKey` or `MEM0_API_KEY` env var
3. Calls `POST {host}/v3/memories/search/` with:
   - `query`: the search string
   - `filters`: the filter object with entity identifiers
   - `top_k`: `config.top_k` or default 10 (an explicit `0` is respected)
   - `threshold`, `rerank`, `metadata`: only when set in config
   - No other config fields (`infer`, `page`, `page_size`, `host`, `mem0ApiKey`) are sent
4. Sends `Authorization: Token <key>` plus `X-Mem0-Source: VERCEL_AI_SDK` and `X-Mem0-Client: mem0-vercel-ai-provider/<version>` headers
5. Throws `HTTP error! status: <code>` on a non-2xx response

**Default host:** `https://api.mem0.ai`

## Internal: `convertToMem0Format(messages)`

Not exported. Used by `addMemories` to convert `LanguageModelV3Prompt` messages to Mem0's format.

**Multimodal content mapping:**

| Input type | Input format | Output type | Output format |
|-----------|-------------|-------------|---------------|
| Text | `{ type: "text", text: "..." }` | Plain string | `{ role, content: "..." }` |
| Image | `{ type: "image_url", image_url: { url } }` or `{ type: "image", ... }` | Image URL | `{ role, content: { type: "image_url", image_url: { url } } }` |
| PDF file | `{ type: "file", data: url, mediaType: "application/pdf" }` | PDF URL | `{ role, content: { type: "pdf_url", pdf_url: { url } } }` |
| Markdown file | `{ type: "file", data: url, mediaType: "text/markdown" }` or `"application/mdx"` | MDX URL | `{ role, content: { type: "mdx_url", mdx_url: { url } } }` |
| Image file | `{ type: "file", data: url, mediaType: "image/*" }` | Image URL | `{ role, content: { type: "image_url", image_url: { url } } }` |
| MDX content | `{ type: "mdx_url", mdx_url: { url } }` or `{ type: "mdx", ... }` | MDX URL | `{ role, content: { type: "mdx_url", mdx_url: { url } } }` |
| PDF content | `{ type: "pdf_url", pdf_url: { url } }` or `{ type: "pdf", ... }` | PDF URL | `{ role, content: { type: "pdf_url", pdf_url: { url } } }` |

`/v3/memories/add/` rejects structured (non-string) `content` with a 400 `Not a valid string.` (live-tested on the Python SDK with `infer` true and false), so a prompt containing these parts is expected to fail with `HTTP error! status: 400` (checked against the endpoint, not through the provider). Only text parts are storable.

The function handles three message content shapes:
1. **String content**: passed through directly
2. **Array content**: each element mapped individually, nulls filtered out
3. **Single object content**: mapped as a single element

## Internal: `flattenPrompt(prompt)`

Not exported. Extracts plain text from `LanguageModelV3Prompt` for use as a search query.

- Iterates over prompt parts, extracting text from `user` role messages
- For `text` type content: extracts `.text`
- For `file` type content: returns descriptive placeholders (`[PDF document]`, `[Markdown document]`, `[Image]`, `[File attachment]`)
- For other content types: returns `[multimodal content]`
- Joins all parts with spaces

## `Mem0ConfigSettings` Fields Reference

All fields are optional. Used across all utility functions.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `user_id` | `string` | -- | Scope memories to a user |
| `app_id` | `string` | -- | Scope memories to an application |
| `agent_id` | `string` | -- | Scope memories to an agent |
| `run_id` | `string` | -- | Scope memories to a session/run |
| `metadata` | `Record<string, any>` | -- | Custom metadata |
| `filters` | `Record<string, any>` | -- | Custom search filters (entity IDs above are merged in and win on conflicts) |
| `infer` | `boolean` | -- | Sent on add only. `false` stores messages verbatim without extraction |
| `page` | `number` | -- | Declared in the type, not sent by the provider |
| `page_size` | `number` | -- | Declared in the type, not sent by the provider |
| `mem0ApiKey` | `string` | `MEM0_API_KEY` env | Mem0 API key |
| `top_k` | `number` | `10` | Number of memories to retrieve |
| `threshold` | `number` | -- | Server-side relevance cutoff, not a floor on the returned score; sent only when set |
| `rerank` | `boolean` | -- (API default `false`) | Enable re-ranking, sent only when set |
| `host` | `string` | `https://api.mem0.ai` | Custom API host |
