/// <reference types="jest" />
/**
 * NVIDIA LLM - unit tests (mocked OpenAI).
 */

let capturedConstructorArgs: any;
const mockCreate = jest.fn();

jest.mock("openai", () => {
  return jest.fn().mockImplementation((args: any) => {
    capturedConstructorArgs = args;
    return {
      chat: { completions: { create: mockCreate } },
    };
  });
});

import { NvidiaLLM } from "../src/llms/nvidia";

describe("NvidiaLLM (unit)", () => {
  beforeEach(() => {
    capturedConstructorArgs = undefined;
    mockCreate.mockClear();
    delete process.env.NVIDIA_API_KEY;
    delete process.env.NVIDIA_API_BASE;
  });

  it("throws when no API key is provided", () => {
    expect(() => new NvidiaLLM({})).toThrow("NVIDIA API key is required");
  });

  it("uses NVIDIA defaults with an explicit API key", () => {
    new NvidiaLLM({ apiKey: "test-key" });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "test-key",
      baseURL: "https://integrate.api.nvidia.com/v1",
    });
  });

  it("uses environment variables when config does not provide credentials", () => {
    process.env.NVIDIA_API_KEY = "env-key";
    process.env.NVIDIA_API_BASE = "https://example.nvidia.test/v1";

    new NvidiaLLM({});

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "env-key",
      baseURL: "https://example.nvidia.test/v1",
    });
  });

  it("config values take precedence over environment variables", () => {
    process.env.NVIDIA_API_KEY = "env-key";
    process.env.NVIDIA_API_BASE = "https://env.nvidia.test/v1";

    new NvidiaLLM({
      apiKey: "config-key",
      baseURL: "https://config.nvidia.test/v1",
      model: "meta/llama-3.3-70b-instruct",
    });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "config-key",
      baseURL: "https://config.nvidia.test/v1",
    });
  });

  it("generateResponse() returns a text response", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: {
            content: "Hello from NVIDIA",
            role: "assistant",
            tool_calls: null,
          },
        },
      ],
    });

    const llm = new NvidiaLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse([
      { role: "user", content: "Hi" },
    ]);

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ model: "meta/llama-3.1-8b-instruct" }),
    );
    expect(result).toBe("Hello from NVIDIA");
  });

  it("generateResponse() handles tool calls", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: {
            content: "",
            role: "assistant",
            tool_calls: [
              {
                function: {
                  name: "search_memory",
                  arguments: '{"query": "alice"}',
                },
              },
            ],
          },
        },
      ],
    });

    const llm = new NvidiaLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [{ role: "user", content: "Find Alice" }],
      undefined,
      [{ type: "function", function: { name: "search_memory" } }],
    );

    expect(result).toEqual({
      content: "",
      role: "assistant",
      toolCalls: [{ name: "search_memory", arguments: '{"query": "alice"}' }],
    });
  });

  it("generateResponse() wraps API errors with a clear message", async () => {
    mockCreate.mockRejectedValueOnce(new Error("Connection refused"));

    const llm = new NvidiaLLM({ apiKey: "test-key" });

    await expect(
      llm.generateResponse([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("NVIDIA LLM failed: Connection refused");
  });

  it("generateChat() returns LLMResponse shape", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: { content: "I can help with that.", role: "assistant" },
        },
      ],
    });

    const llm = new NvidiaLLM({ apiKey: "test-key" });
    const result = await llm.generateChat([
      { role: "user", content: "Help me" },
    ]);

    expect(result).toEqual({
      content: "I can help with that.",
      role: "assistant",
    });
  });

  it("generateChat() wraps API errors with a clear message", async () => {
    mockCreate.mockRejectedValueOnce(new Error("Timeout"));

    const llm = new NvidiaLLM({ apiKey: "test-key" });

    await expect(
      llm.generateChat([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("NVIDIA LLM failed: Timeout");
  });
});
