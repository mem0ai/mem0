/// <reference types="jest" />
/**
 * DeepSeek LLM — unit tests (mocked OpenAI).
 */

import { DeepSeekLLM } from "../src/llms/deepseek";

const mockCreate = jest.fn();

jest.mock("openai", () => {
  return jest.fn().mockImplementation(() => ({
    chat: { completions: { create: mockCreate } },
  }));
});

describe("DeepSeekLLM (unit)", () => {
  beforeEach(() => mockCreate.mockClear());

  it("throws when no API key is provided", () => {
    const original = process.env.DEEPSEEK_API_KEY;
    delete process.env.DEEPSEEK_API_KEY;
    try {
      expect(() => new DeepSeekLLM({})).toThrow("DeepSeek API key is required");
    } finally {
      if (original !== undefined) process.env.DEEPSEEK_API_KEY = original;
    }
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

    const llm = new DeepSeekLLM({ apiKey: "test-key" });
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

    const llm = new DeepSeekLLM({ apiKey: "test-key" });
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

    const llm = new DeepSeekLLM({ apiKey: "test-key" });

    await expect(
      llm.generateResponse([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("DeepSeek LLM failed: Connection refused");
  });

  it("generateChat() returns LLMResponse shape", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: { content: "I can help with that.", role: "assistant" },
        },
      ],
    });

    const llm = new DeepSeekLLM({ apiKey: "test-key" });
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

    const llm = new DeepSeekLLM({ apiKey: "test-key" });

    await expect(
      llm.generateChat([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("DeepSeek LLM failed: Timeout");
  });
});
