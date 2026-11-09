/// <reference types="jest" />
/**
 * MiniMax LLM - unit tests (mocked OpenAI).
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

import { MiniMaxLLM } from "../src/llms/minimax";

describe("MiniMaxLLM (unit)", () => {
  beforeEach(() => {
    capturedConstructorArgs = undefined;
    mockCreate.mockClear();
    delete process.env.MINIMAX_API_KEY;
    delete process.env.MINIMAX_API_BASE;
  });

  it("throws when no API key is provided", () => {
    expect(() => new MiniMaxLLM({})).toThrow("MiniMax API key is required");
  });

  it("uses MiniMax defaults with an explicit API key", () => {
    new MiniMaxLLM({ apiKey: "test-key" });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "test-key",
      baseURL: "https://api.minimax.io/v1",
    });
  });

  it("uses environment variables when config does not provide credentials", () => {
    process.env.MINIMAX_API_KEY = "env-key";
    process.env.MINIMAX_API_BASE = "https://example.minimax.test/v1";

    new MiniMaxLLM({});

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "env-key",
      baseURL: "https://example.minimax.test/v1",
    });
  });

  it("config values take precedence over environment variables", () => {
    process.env.MINIMAX_API_KEY = "env-key";
    process.env.MINIMAX_API_BASE = "https://env.minimax.test/v1";

    new MiniMaxLLM({
      apiKey: "config-key",
      baseURL: "https://config.minimax.test/v1",
      model: "MiniMax-M1",
    });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "config-key",
      baseURL: "https://config.minimax.test/v1",
    });
  });

  it("generateResponse() returns a text response", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: {
            content: "Hello from MiniMax",
            role: "assistant",
            tool_calls: null,
          },
        },
      ],
    });

    const llm = new MiniMaxLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse([
      { role: "user", content: "Hi" },
    ]);

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ model: "MiniMax-M2.7" }),
    );
    expect(result).toBe("Hello from MiniMax");
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

    const llm = new MiniMaxLLM({ apiKey: "test-key" });
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

    const llm = new MiniMaxLLM({ apiKey: "test-key" });

    await expect(
      llm.generateResponse([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("MiniMax LLM failed: Connection refused");
  });

  it("generateChat() returns LLMResponse shape", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: { content: "I can help with that.", role: "assistant" },
        },
      ],
    });

    const llm = new MiniMaxLLM({ apiKey: "test-key" });
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

    const llm = new MiniMaxLLM({ apiKey: "test-key" });

    await expect(
      llm.generateChat([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("MiniMax LLM failed: Timeout");
  });
});
