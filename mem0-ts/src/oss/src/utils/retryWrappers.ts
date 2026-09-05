/**
 * Factory-level retry wrappers. When a provider config sets `maxRetries > 0`,
 * the created LLM/embedder is wrapped so its network-facing methods retry
 * transient failures (see ./retry). When retries are disabled the original
 * instance is returned untouched, so the default behavior is unchanged.
 */
import { LLM, LLMResponse } from "../llms/base";
import { Embedder } from "../embeddings/base";
import { Message } from "../types";
import { resolveRetryOptions, retryCall, RetryOptions } from "./retry";

interface RetryConfig {
  maxRetries?: number;
  retryInitialDelayMs?: number;
  retryMaxDelayMs?: number;
}

/**
 * Wrap `llm` so `generateResponse` / `generateChat` retry transient provider
 * errors, or return it unchanged when retries are disabled.
 */
export function withLLMRetry(llm: LLM, config: RetryConfig): LLM {
  const options = resolveRetryOptions(config);
  if (!options) return llm;
  return new RetryingLLM(llm, options);
}

/**
 * Wrap `embedder` so `embed` / `embedBatch` retry transient provider errors, or
 * return it unchanged when retries are disabled.
 */
export function withEmbedderRetry(
  embedder: Embedder,
  config: RetryConfig,
): Embedder {
  const options = resolveRetryOptions(config);
  if (!options) return embedder;
  return new RetryingEmbedder(embedder, options);
}

class RetryingLLM implements LLM {
  constructor(
    private readonly inner: LLM,
    private readonly options: RetryOptions,
  ) {}

  generateResponse(
    messages: Array<{ role: string; content: string }>,
    responseFormat?: { type: string },
    tools?: any[],
  ): Promise<any> {
    return retryCall(
      () => this.inner.generateResponse(messages, responseFormat, tools),
      this.options,
    );
  }

  generateChat(messages: Message[]): Promise<LLMResponse> {
    return retryCall(() => this.inner.generateChat(messages), this.options);
  }
}

class RetryingEmbedder implements Embedder {
  constructor(
    private readonly inner: Embedder,
    private readonly options: RetryOptions,
  ) {}

  embed(
    text: string,
    memoryAction?: "add" | "update" | "search",
  ): Promise<number[]> {
    return retryCall(() => this.inner.embed(text, memoryAction), this.options);
  }

  embedBatch(
    texts: string[],
    memoryAction?: "add" | "update" | "search",
  ): Promise<number[][]> {
    return retryCall(
      () => this.inner.embedBatch(texts, memoryAction),
      this.options,
    );
  }
}
