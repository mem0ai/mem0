# Provider API Reference

Complete reference for the `@mem0/vercel-ai-provider` provider layer. Source: `vercel-ai-sdk/src/`.

## `createMem0(options?)`

Factory function that creates a `Mem0Provider` instance. This is the primary entry point for the wrapped model approach.

```typescript
import { createMem0 } from "@mem0/vercel-ai-provider";

const mem0 = createMem0();                           // defaults: provider "openai"
const mem0 = createMem0({ provider: "anthropic" });  // use Anthropic as LLM backend
```

**Signature:**

```typescript
function createMem0(options?: Mem0ProviderSettings): Mem0Provider;
```

When called with no arguments, defaults to `{ provider: "openai" }`.

**Returns:** `Mem0Provider` -- a callable function that also exposes `.chat()`, `.completion()`, and `.languageModel()` methods.

## `Mem0Provider` Interface

Implements `ProviderV2` from `@ai-sdk/provider`.

```typescript
interface Mem0Provider extends ProviderV2 {
  // Call directly as a function
  (modelId: Mem0ChatModelId, settings?: Mem0ChatSettings): LanguageModelV2;

  // Or use named methods
  chat(modelId: Mem0ChatModelId, settings?: Mem0ChatSettings): LanguageModelV2;
  completion(modelId: Mem0ChatModelId, settings?: Mem0ChatSettings): LanguageModelV2;
  languageModel(modelId: Mem0ChatModelId, settings?: Mem0ChatSettings): LanguageModelV2;
}
```

- **Direct call** (`mem0("gpt-5-mini", {...})`): creates a generic language model (neither chat nor completion mode forced).
- **`chat()`**: creates a model with `modelType: "chat"` (note: in the current source, the chat constructor sets `modelType: "completion"` -- this appears to be a bug; functionally equivalent to `completion()` at present).
- **`completion()`**: creates a model with `modelType: "completion"`.
- **`languageModel()`**: alias for the generic model (same as direct call).

All three return a `Mem0GenericLanguageModel` instance implementing `LanguageModelV2`.

## `Mem0ProviderSettings` Interface

Configuration passed to `createMem0()`.

```typescript
interface Mem0ProviderSettings {
  baseURL?: string;            // Base URL for the LLM provider (default: "http://api.openai.com")
  headers?: Record<string, string>;  // Custom headers for LLM requests
  provider?: string;           // LLM provider name (default: "openai")
  mem0ApiKey?: string;         // Mem0 Platform API key (or use MEM0_API_KEY env var)
  apiKey?: string;             // LLM provider API key (e.g., OpenAI key)
  mem0Config?: Mem0Config;     // Default Mem0 config (user_id, etc.) applied to all calls
  config?: LLMProviderSettings; // Provider-specific settings (OpenAI, Anthropic, etc.)
  fetch?: typeof fetch;        // Custom fetch implementation (for testing/middleware)
  generateId?: () => string;   // Custom ID generator (internal use)
  name?: string;               // Provider instance name
  modelType?: "completion" | "chat";  // Force model type
}
```

### Key fields explained

| Field | Purpose | Example |
|-------|---------|---------|
| `provider` | Which LLM backend to use | `"openai"`, `"anthropic"`, `"google"`, `"groq"`, `"cohere"` |
| `mem0ApiKey` | Mem0 Platform API key | `"m0-xxx"` |
| `apiKey` | LLM provider API key | `"sk-xxx"` (OpenAI), `"sk-ant-xxx"` (Anthropic) |
| `mem0Config` | Default Mem0 settings for all calls | `{ user_id: "alice" }` |
| `config` | Provider-specific SDK settings | `{ organization: "org-xxx" }` for OpenAI |
| `baseURL` | Override LLM provider base URL | `"https://my-proxy.example.com"` |

## `mem0` Singleton

A pre-configured instance using default settings (OpenAI provider, no API keys set -- relies on env vars).

```typescript
import { mem0 } from "@mem0/vercel-ai-provider";

const { text } = await generateText({
  model: mem0("gpt-5-mini", { user_id: "alice" }),
  prompt: "Hello",
});
```

Equivalent to `createMem0()` with no arguments.

## `Mem0ConfigSettings` Interface

Configuration for memory operations. Used as `Mem0ChatSettings` (per-call) or `Mem0Config` (provider-level default). All fields are optional.

```typescript
interface Mem0ConfigSettings {
  user_id?: string;              // Scope memories to a specific user
  app_id?: string;               // Scope memories to an application
  agent_id?: string;             // Scope memories to an agent
  run_id?: string;               // Scope memories to a specific run/session
  metadata?: Record<string, any>; // Custom metadata attached to memories
  filters?: Record<string, any>; // Custom filters for memory search
  infer?: boolean;               // Enable inference during memory operations
  page?: number;                 // Pagination: page number
  page_size?: number;            // Pagination: results per page
  mem0ApiKey?: string;           // Mem0 API key (overrides provider-level key)
  top_k?: number;                // Number of memories to retrieve (default: 5)
  threshold?: number;            // Minimum similarity score for retrieval (default: 0.1)
  rerank?: boolean;              // Enable re-ranking of search results (default: false)
  host?: string;                 // Custom Mem0 API host (default: "https://api.mem0.ai")
}
```

## `Mem0ChatConfig` Type

Combined type used internally by the language model. Merges memory config with provider config.

```typescript
interface Mem0ChatConfig extends Mem0ConfigSettings, Mem0ProviderSettings {}
```

This means a `Mem0ChatConfig` has all fields from both `Mem0ConfigSettings` and `Mem0ProviderSettings`.

## `Mem0ChatSettings` Type

Alias for `Mem0ConfigSettings`. Passed as the second argument when creating a model:

```typescript
mem0("gpt-5-mini", { user_id: "alice" })
//                   ^^^^^^^^^^^^^^^^^^
//                   This object is Mem0ChatSettings
```

## `LLMProviderSettings` Type

Union of provider-specific settings. Extends all supported provider setting interfaces:

```typescript
interface LLMProviderSettings extends
  OpenAIProviderSettings,
  AnthropicProviderSettings,
  CohereProviderSettings,
  GroqProviderSettings {}
```

Pass via the `config` field of `Mem0ProviderSettings` to forward settings to the underlying LLM provider SDK.

## Provider Selection: `Mem0ClassSelector`

Internal class that maps the `provider` string to the correct AI SDK provider.

```typescript
class Mem0ClassSelector {
  static supportedProviders = ["openai", "anthropic", "cohere", "groq", "google"];
  // ...
}
```

**Important:** The `"gemini"` alias exists in the provider switch statement (maps to `createGoogleGenerativeAI`) but is **NOT** in the `supportedProviders` list. The constructor validates against `supportedProviders`, so using `"gemini"` will throw `"Model not supported: gemini"`. Use `"google"` instead.

### Provider mapping

| Config value | SDK used | Factory function |
|-------------|----------|------------------|
| `"openai"` | `@ai-sdk/openai` | `createOpenAI` |
| `"anthropic"` | `@ai-sdk/anthropic` | `createAnthropic` |
| `"cohere"` | `@ai-sdk/cohere` | `createCohere` |
| `"groq"` | `@ai-sdk/groq` | `createGroq` |
| `"google"` | `@ai-sdk/google` | `createGoogleGenerativeAI` |

## `Mem0` Facade Class

An alternative exported class that creates models directly without the callable-function pattern.

```typescript
import { Mem0 } from "@mem0/vercel-ai-provider";

const mem0 = new Mem0({ provider: "openai" });
const chatModel = mem0.chat("gpt-5-mini", { user_id: "alice" });
const completionModel = mem0.completion("gpt-5-mini");
```

The facade defaults its base URL to `"http://127.0.0.1:11434/api"` (Ollama-style) rather than `"http://api.openai.com"`. It always uses `"openai"` as the provider for created models.

**Methods:**
- `chat(modelId, settings?)` -- creates a model with `modelType: "chat"`
- `completion(modelId, settings?)` -- creates a model with `modelType: "completion"`

## `Mem0GenericLanguageModel` Class

The core class implementing `LanguageModelV2`. Created by `createMem0` or the `Mem0` facade.

```typescript
class Mem0GenericLanguageModel implements LanguageModelV2 {
  readonly specificationVersion = "v2";
  readonly defaultObjectGenerationMode = "json";
  readonly supportsImageUrls = false;
  readonly supportedUrls: Record<string, RegExp[]> = { '*': [/.*/] };

  provider: string;   // e.g., "openai"
  modelId: string;    // e.g., "gpt-5-mini"
  settings: Mem0ChatSettings;
  config: Mem0ChatConfig;

  async doGenerate(options: LanguageModelV2CallOptions): Promise<...>;
  async doStream(options: LanguageModelV2CallOptions): Promise<...>;
}
```

Both `doGenerate` and `doStream` follow the same internal flow:

1. Build `Mem0ConfigSettings` from `config.mem0Config` merged with `settings`
2. Call `processMemories`:
   - Fire `addMemories` as fire-and-forget (no await, `.then().catch()`)
   - Await `getMemories` to retrieve relevant memories
   - Format memories as a system message and prepend to the prompt
3. Create the underlying LLM model via `Mem0ClassSelector`
4. Delegate to the underlying model's `doGenerate` or `doStream`
5. Return the result

**Note:** Entity identifier fields use snake_case (`user_id`, `app_id`, `agent_id`, `run_id`) to match the Mem0 API.

## Type: `Mem0ChatModelId`

```typescript
type Mem0ChatModelId = string & NonNullable<unknown>;
```

Any non-null string. The model ID is passed through to the underlying provider (e.g., `"gpt-5-mini"`, `"gemini-pro"`).
