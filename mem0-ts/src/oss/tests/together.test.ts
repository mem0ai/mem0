/// <reference types="jest" />
/**
 * Together LLM - unit tests (mocked OpenAI).
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

import { TogetherLLM } from "../src/llms/together";

describe("TogetherLLM (unit)", () => {
  beforeEach(() => {
    capturedConstructorArgs = undefined;
    mockCreate.mockClear();
    delete process.env.TOGETHER_API_KEY;
    delete process.env.TOGETHER_API_BASE;
  });

  it("throws when no API key is provided", () => {
    expect(() => new TogetherLLM({})).toThrow("Together API key is required");
  });

  it("uses Together defaults with an explicit API key", () => {
    new TogetherLLM({ apiKey: "test-key" });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "test-key",
      baseURL: "https://api.together.ai/v1",
    });
  });

  it("uses environment variables when config does not provide credentials", () => {
    process.env.TOGETHER_API_KEY = "env-key";
    process.env.TOGETHER_API_BASE = "https://example.together.test/v1";

    new TogetherLLM({});

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "env-key",
      baseURL: "https://example.together.test/v1",
    });
  });

  it("config values take precedence over environment variables", () => {
    process.env.TOGETHER_API_KEY = "env-key";
    process.env.TOGETHER_API_BASE = "https://env.together.test/v1";

    new TogetherLLM({
      apiKey: "config-key",
      baseURL: "https://config.together.test/v1",
      model: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    });

    expect(capturedConstructorArgs).toMatchObject({
      apiKey: "config-key",
      baseURL: "https://config.together.test/v1",
    });
  });

  it("generateResponse() returns a text response using the default Together model", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [
        {
          message: {
            content: "Hello from Together",
            role: "assistant",
            tool_calls: null,
          },
        },
      ],
    });

    const llm = new TogetherLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse([
      { role: "user", content: "Hi" },
    ]);

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        model: "MiniMaxAI/MiniMax-M3",
      }),
    );
    expect(result).toBe("Hello from Together");
  });

  it("generateResponse() wraps API errors with a clear message", async () => {
    mockCreate.mockRejectedValueOnce(new Error("Connection refused"));

    const llm = new TogetherLLM({ apiKey: "test-key" });

    await expect(
      llm.generateResponse([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("Together LLM failed: Connection refused");
  });

  it("generateChat() wraps API errors with a clear message", async () => {
    mockCreate.mockRejectedValueOnce(new Error("Timeout"));

    const llm = new TogetherLLM({ apiKey: "test-key" });

    await expect(
      llm.generateChat([{ role: "user", content: "Hi" }]),
    ).rejects.toThrow("Together LLM failed: Timeout");
  });
});
