/// <reference types="jest" />
/**
 * LiteLLM — unit tests (mocked OpenAI).
 */

import { LiteLLM } from "../src/llms/litellm";

const mockCreate = jest.fn();

jest.mock("openai", () => {
  return jest.fn().mockImplementation(() => ({
    chat: { completions: { create: mockCreate } },
  }));
});

describe("LiteLLM (unit)", () => {
  beforeEach(() => mockCreate.mockClear());

  it("uses default baseURL when none is provided", () => {
    const llm = new LiteLLM({});
    expect(llm).toBeDefined();
  });

  it("generateResponse() returns a text response", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: {
            content: "Hello, world!",
            role: "assistant",
            tool_calls: null,
          },
        },
      ],
    });

    const llm = new LiteLLM({ baseURL: "http://localhost:4000" });
    const result = await llm.generateResponse([
      { role: "user", content: "Hi" },
    ]);

    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(result).toBe("Hello, world!");
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
                  name: "get_weather",
                  arguments: '{"city": "London"}',
                },
              },
            ],
          },
        },
      ],
    });

    const llm = new LiteLLM({});
    const result = await llm.generateResponse(
      [{ role: "user", content: "What is the weather?" }],
      undefined,
      [{ type: "function", function: { name: "get_weather" } }],
    );

    expect(result).toEqual({
      content: "",
      role: "assistant",
      toolCalls: [{ name: "get_weather", arguments: '{"city": "London"}' }],
    });
  });

  it("generateResponse() wraps API errors with a clear message", async () => {
    mockCreate.mockRejectedValueOnce(new Error("Connection refused"));

    const llm = new LiteLLM({});

    await expect(
      llm.generateResponse([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("LiteLLM failed: Connection refused");
  });

  it("generateChat() returns LLMResponse shape", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: { content: "I can help with that.", role: "assistant" },
        },
      ],
    });

    const llm = new LiteLLM({});
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

    const llm = new LiteLLM({});

    await expect(
      llm.generateChat([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("LiteLLM failed: Timeout");
  });

  it("respects LITELLM_API_BASE env var", () => {
    const original = process.env.LITELLM_API_BASE;
    process.env.LITELLM_API_BASE = "http://custom-proxy:8080";
    try {
      const llm = new LiteLLM({});
      expect(llm).toBeDefined();
    } finally {
      if (original !== undefined) process.env.LITELLM_API_BASE = original;
      else delete process.env.LITELLM_API_BASE;
    }
  });
});
