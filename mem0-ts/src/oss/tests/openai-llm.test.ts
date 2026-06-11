/// <reference types="jest" />
/**
 * OpenAI LLM — unit tests (mocked openai).
 *
 * Regression tests for #4707: timeout config was silently ignored,
 * causing add() to hang indefinitely on slow LLM responses.
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

import { OpenAILLM } from "../src/llms/openai";

describe("OpenAILLM (unit)", () => {
  beforeEach(() => {
    capturedConstructorArgs = undefined;
    mockCreate.mockClear();
  });

  it("forwards timeout to the OpenAI client constructor", () => {
    new OpenAILLM({
      apiKey: "test-key",
      baseURL: "http://localhost:8080/v1",
      timeout: 5000,
    });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "test-key",
      baseURL: "http://localhost:8080/v1",
      timeout: 5000,
    });
  });

  it("forwards timeout: 0 to the OpenAI client (explicit zero is valid)", () => {
    new OpenAILLM({
      apiKey: "test-key",
      baseURL: "http://localhost:8080/v1",
      timeout: 0,
    });

    expect(capturedConstructorArgs.timeout).toBe(0);
  });

  it("omits timeout from the OpenAI client when not configured", () => {
    new OpenAILLM({
      apiKey: "test-key",
      baseURL: "http://localhost:8080/v1",
    });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "test-key",
      baseURL: "http://localhost:8080/v1",
    });
    expect(capturedConstructorArgs).not.toHaveProperty("timeout");
  });

  it("generateResponse() returns text content", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: {
            content: '{"facts": ["hello"]}',
            role: "assistant",
            tool_calls: null,
          },
        },
      ],
    });

    const llm = new OpenAILLM({ apiKey: "test-key" });
    const result = await llm.generateResponse([
      { role: "user", content: "Hi" },
    ]);

    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(result).toBe('{"facts": ["hello"]}');
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

    const llm = new OpenAILLM({ apiKey: "test-key" });
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

  it("generateChat() returns LLMResponse shape", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: { content: "I can help.", role: "assistant" },
        },
      ],
    });

    const llm = new OpenAILLM({ apiKey: "test-key" });
    const result = await llm.generateChat([
      { role: "user", content: "Help me" },
    ]);

    expect(result).toEqual({
      content: "I can help.",
      role: "assistant",
    });
  });
});
