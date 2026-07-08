/// <reference types="jest" />
/**
 * Sarvam LLM — unit tests (mocked OpenAI).
 */

import { SarvamLLM } from "../src/llms/sarvam";

const mockCreate = jest.fn();
const mockOpenAICtor = jest.fn();

jest.mock("openai", () => {
  return jest.fn().mockImplementation((config) => {
    mockOpenAICtor(config);
    return { chat: { completions: { create: mockCreate } } };
  });
});

describe("SarvamLLM (unit)", () => {
  const ORIGINAL_ENV = process.env;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env = { ...ORIGINAL_ENV };
    delete process.env.SARVAM_API_KEY;
    delete process.env.SARVAM_API_BASE;
    mockCreate.mockResolvedValue({
      choices: [{ message: { content: "hi", role: "assistant" } }],
    });
  });

  afterAll(() => {
    process.env = ORIGINAL_ENV;
  });

  it("defaults to sarvam-m and the Sarvam base URL (matching the Python provider)", async () => {
    const llm = new SarvamLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse([
      { role: "user", content: "hello" },
    ]);

    expect(mockOpenAICtor).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "test-key",
        baseURL: "https://api.sarvam.ai/v1",
      }),
    );
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ model: "sarvam-m" }),
    );
    expect(result).toBe("hi");
  });

  it("resolves SARVAM_API_KEY / SARVAM_API_BASE from the environment", () => {
    process.env.SARVAM_API_KEY = "env-key";
    process.env.SARVAM_API_BASE = "https://custom.sarvam.ai/v1";

    new SarvamLLM({});

    expect(mockOpenAICtor).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "env-key",
        baseURL: "https://custom.sarvam.ai/v1",
      }),
    );
  });

  it("prefers explicit config over defaults and the environment", async () => {
    process.env.SARVAM_API_KEY = "env-key";

    const llm = new SarvamLLM({
      apiKey: "explicit-key",
      baseURL: "https://proxy.example.com/v1",
      model: "sarvam-2b",
    });
    await llm.generateResponse([{ role: "user", content: "hello" }]);

    expect(mockOpenAICtor).toHaveBeenCalledWith(
      expect.objectContaining({
        apiKey: "explicit-key",
        baseURL: "https://proxy.example.com/v1",
      }),
    );
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ model: "sarvam-2b" }),
    );
  });

  it("throws when no API key is provided", () => {
    expect(() => new SarvamLLM({})).toThrow("Sarvam API key is required");
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

    const llm = new SarvamLLM({ apiKey: "test-key" });
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

  it("generateResponse() wraps downstream errors with a Sarvam-specific message", async () => {
    mockCreate.mockRejectedValueOnce(new Error("Connection refused"));
    const llm = new SarvamLLM({ apiKey: "test-key" });

    await expect(
      llm.generateResponse([{ role: "user", content: "hi" }]),
    ).rejects.toThrow("Sarvam LLM failed: Connection refused");
  });

  it("generateChat() returns the LLMResponse shape", async () => {
    mockCreate.mockResolvedValueOnce({
      choices: [{ message: { content: "I can help.", role: "assistant" } }],
    });

    const llm = new SarvamLLM({ apiKey: "test-key" });
    const result = await llm.generateChat([
      { role: "user", content: "help me" },
    ]);

    expect(result).toEqual({ content: "I can help.", role: "assistant" });
  });

  it("generateChat() wraps downstream errors with a Sarvam-specific message", async () => {
    mockCreate.mockRejectedValueOnce(new Error("Timeout"));
    const llm = new SarvamLLM({ apiKey: "test-key" });

    await expect(
      llm.generateChat([{ role: "user", content: "hi" }]),
    ).rejects.toThrow("Sarvam LLM failed: Timeout");
  });
});
