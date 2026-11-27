/// <reference types="jest" />
/**
 * Integration tests for the factory-level retry wrappers (utils/retryWrappers).
 * Verifies that an LLM/embedder created with maxRetries retries transient
 * provider errors, and that maxRetries:0 (or unset) returns the raw instance.
 */
import { withLLMRetry, withEmbedderRetry } from "../src/utils/retryWrappers";
import type { LLM } from "../src/llms/base";
import type { Embedder } from "../src/embeddings/base";

const transient = (status: number) =>
  Object.assign(new Error(`HTTP ${status}`), { status });

// Patch the module's sleep by using zero-delay real timers is flaky; instead we
// rely on retryCall's default sleep (setTimeout) with tiny backoff via config.
const fastRetry = {
  maxRetries: 3,
  retryInitialDelayMs: 1,
  retryMaxDelayMs: 2,
};

describe("withLLMRetry", () => {
  it("returns the same instance when retries are disabled", () => {
    const llm = { generateResponse: jest.fn(), generateChat: jest.fn() } as LLM;
    expect(withLLMRetry(llm, {})).toBe(llm);
    expect(withLLMRetry(llm, { maxRetries: 0 })).toBe(llm);
  });

  it("wraps and retries generateResponse on a transient error", async () => {
    const generateResponse = jest
      .fn()
      .mockRejectedValueOnce(transient(429))
      .mockResolvedValue("done");
    const llm = { generateResponse, generateChat: jest.fn() } as unknown as LLM;

    const wrapped = withLLMRetry(llm, fastRetry);
    await expect(
      wrapped.generateResponse([{ role: "user", content: "hi" }]),
    ).resolves.toBe("done");
    expect(generateResponse).toHaveBeenCalledTimes(2);
  });

  it("forwards all arguments to the wrapped generateResponse", async () => {
    const generateResponse = jest.fn().mockResolvedValue("ok");
    const llm = { generateResponse, generateChat: jest.fn() } as unknown as LLM;
    const wrapped = withLLMRetry(llm, fastRetry);

    const messages = [{ role: "user", content: "hi" }];
    const format = { type: "json_object" };
    const tools = [{ name: "t" }];
    await wrapped.generateResponse(messages, format, tools);

    expect(generateResponse).toHaveBeenCalledWith(messages, format, tools);
  });

  it("surfaces a non-transient error without retrying", async () => {
    const generateChat = jest.fn().mockRejectedValue(transient(401));
    const llm = {
      generateResponse: jest.fn(),
      generateChat,
    } as unknown as LLM;
    const wrapped = withLLMRetry(llm, fastRetry);

    await expect(wrapped.generateChat([])).rejects.toMatchObject({
      status: 401,
    });
    expect(generateChat).toHaveBeenCalledTimes(1);
  });
});

describe("withEmbedderRetry", () => {
  it("returns the same instance when retries are disabled", () => {
    const emb = { embed: jest.fn(), embedBatch: jest.fn() } as Embedder;
    expect(withEmbedderRetry(emb, {})).toBe(emb);
  });

  it("retries embed and embedBatch on transient errors", async () => {
    const embed = jest
      .fn()
      .mockRejectedValueOnce(transient(503))
      .mockResolvedValue([0.1, 0.2]);
    const embedBatch = jest
      .fn()
      .mockRejectedValueOnce(transient(500))
      .mockResolvedValue([[0.1]]);
    const emb = { embed, embedBatch } as unknown as Embedder;

    const wrapped = withEmbedderRetry(emb, fastRetry);
    await expect(wrapped.embed("x", "add")).resolves.toEqual([0.1, 0.2]);
    await expect(wrapped.embedBatch(["x"], "search")).resolves.toEqual([[0.1]]);
    expect(embed).toHaveBeenCalledTimes(2);
    expect(embed).toHaveBeenLastCalledWith("x", "add");
    expect(embedBatch).toHaveBeenCalledTimes(2);
    expect(embedBatch).toHaveBeenLastCalledWith(["x"], "search");
  });
});
