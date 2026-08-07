/// <reference types="jest" />
/**
 * LM Studio LLM — unit tests (mocked OpenAI).
 */

import OpenAI from "openai";
import { LMStudioLLM } from "../src/llms/lmstudio";

const mockCreate = jest.fn();
const MockOpenAI = OpenAI as unknown as jest.Mock;

jest.mock("openai", () => {
  return jest.fn().mockImplementation(() => ({
    chat: { completions: { create: mockCreate } },
  }));
});

describe("LMStudioLLM (unit)", () => {
  const originalEnv = process.env.LMSTUDIO_BASE_URL;

  beforeEach(() => {
    mockCreate.mockClear();
    MockOpenAI.mockClear();
    delete process.env.LMSTUDIO_BASE_URL;
  });

  afterAll(() => {
    if (originalEnv === undefined) {
      delete process.env.LMSTUDIO_BASE_URL;
    } else {
      process.env.LMSTUDIO_BASE_URL = originalEnv;
    }
  });

  it("honors LMSTUDIO_BASE_URL when config baseURL is unset", () => {
    process.env.LMSTUDIO_BASE_URL = "http://remote-lms:1234/v1";
    new LMStudioLLM({});
    expect(MockOpenAI).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: "http://remote-lms:1234/v1" }),
    );
  });

  it("prefers config baseURL over LMSTUDIO_BASE_URL", () => {
    process.env.LMSTUDIO_BASE_URL = "http://env-host:1234/v1";
    new LMStudioLLM({ baseURL: "http://cfg-host:1234/v1" });
    expect(MockOpenAI).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: "http://cfg-host:1234/v1" }),
    );
  });

  it("defaults to localhost when config and env are unset", () => {
    new LMStudioLLM({});
    expect(MockOpenAI).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: "http://localhost:1234/v1" }),
    );
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

    const llm = new LMStudioLLM({ baseURL: "http://localhost:1234/v1" });
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

    const llm = new LMStudioLLM({ baseURL: "http://localhost:1234/v1" });
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

    const llm = new LMStudioLLM({ baseURL: "http://localhost:1234/v1" });

    await expect(
      llm.generateResponse([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("LM Studio LLM failed: Connection refused");
  });

  it("generateChat() returns LLMResponse shape", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: { content: "I can help with that.", role: "assistant" },
        },
      ],
    });

    const llm = new LMStudioLLM({ baseURL: "http://localhost:1234/v1" });
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

    const llm = new LMStudioLLM({ baseURL: "http://localhost:1234/v1" });

    await expect(
      llm.generateChat([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("LM Studio LLM failed: Timeout");
  });
});
