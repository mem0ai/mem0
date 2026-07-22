/// <reference types="jest" />
/**
 * xAI (Grok) LLM — unit tests (mocked OpenAI).
 */

import { XAILLM } from "../src/llms/xai";

const mockCreate = jest.fn();
const mockOpenAICtor = jest.fn();

jest.mock("openai", () => {
  return jest.fn().mockImplementation((config) => {
    mockOpenAICtor(config);
    return { chat: { completions: { create: mockCreate } } };
  });
});

describe("XAILLM (unit)", () => {
  const ORIGINAL_ENV = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = { ...ORIGINAL_ENV };
    delete process.env.XAI_API_KEY;
    delete process.env.XAI_API_BASE;
    mockCreate.mockResolvedValue({
      choices: [{ message: { content: "hi", role: "assistant" } }],
    });
  });

  afterAll(() => {
    process.env = ORIGINAL_ENV;
  });

  it("defaults to grok-4.3 and the xAI base URL (matching the Python provider)", async () => {
    const llm = new XAILLM({ apiKey: "test-key" });
    const result = await llm.generateResponse([
      { role: "user", content: "hello" },
    ]);

    expect(mockOpenAICtor).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "test-key",
        baseURL: "https://api.x.ai/v1",
      }),
    );
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ model: "grok-4.3" }),
    );
    expect(result).toBe("hi");
  });

  it("resolves XAI_API_KEY / XAI_API_BASE from the environment", () => {
    process.env.XAI_API_KEY = "env-key";
    process.env.XAI_API_BASE = "https://custom.x.ai/v1";

    new XAILLM({});

    expect(mockOpenAICtor).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "env-key",
        baseURL: "https://custom.x.ai/v1",
      }),
    );
  });

  it("prefers explicit config over defaults and the environment", async () => {
    process.env.XAI_API_KEY = "env-key";

    const llm = new XAILLM({
      apiKey: "explicit-key",
      baseURL: "https://proxy.example.com/v1",
      model: "grok-420-reasoning",
    });
    await llm.generateResponse([{ role: "user", content: "hello" }]);

    expect(mockOpenAICtor).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "explicit-key",
        baseURL: "https://proxy.example.com/v1",
      }),
    );
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ model: "grok-420-reasoning" }),
    );
  });

  it("throws when no API key is provided", () => {
    expect(() => new XAILLM({})).toThrow("xAI API key is required");
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
                function: { name: "get_weather", arguments: '{"city": "SF"}' },
              },
            ],
          },
        },
      ],
    });

    const llm = new XAILLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [{ role: "user", content: "weather?" }],
      undefined,
      [{ type: "function", function: { name: "get_weather" } }],
    );

    expect(result).toEqual({
      content: "",
      role: "assistant",
      toolCalls: [{ name: "get_weather", arguments: '{"city": "SF"}' }],
    });
  });

  it("generateResponse() wraps downstream errors with an xAI-specific message", async () => {
    mockCreate.mockRejectedValueOnce(new Error("Connection refused"));
    const llm = new XAILLM({ apiKey: "test-key" });

    await expect(
      llm.generateResponse([{ role: "user", content: "hi" }]),
    ).rejects.toThrow("xAI LLM failed: Connection refused");
  });

  it("generateChat() returns the LLMResponse shape", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [{ message: { content: "I can help.", role: "assistant" } }],
    });

    const llm = new XAILLM({ apiKey: "test-key" });
    const result = await llm.generateChat([
      { role: "user", content: "help me" },
    ]);

    expect(result).toEqual({ content: "I can help.", role: "assistant" });
  });

  it("generateChat() wraps downstream errors with an xAI-specific message", async () => {
    mockCreate.mockRejectedValueOnce(new Error("Timeout"));
    const llm = new XAILLM({ apiKey: "test-key" });

    await expect(
      llm.generateChat([{ role: "user", content: "hi" }]),
    ).rejects.toThrow("xAI LLM failed: Timeout");
  });
});
