/// <reference types="jest" />

const mockCreate = jest.fn().mockResolvedValue({
  content: [{ type: "text", text: '{"result": "ok"}' }],
  stop_reason: "end_turn",
});

jest.mock("@anthropic-ai/sdk", () => {
  return jest.fn().mockImplementation(() => ({
    messages: { create: mockCreate },
  }));
});

import Anthropic from "@anthropic-ai/sdk";
import { AnthropicLLM } from "../src/llms/anthropic";

describe("AnthropicLLM maxTokens", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    process.env.ANTHROPIC_API_KEY = "test-key";
  });

  afterEach(() => {
    delete process.env.ANTHROPIC_API_KEY;
  });

  it("should use default maxTokens of 16384 when not specified", async () => {
    const llm = new AnthropicLLM({ apiKey: "test-key" });

    await llm.generateResponse([{ role: "user", content: "Hello" }]);

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        max_tokens: 16384,
      }),
    );
  });

  it("should use custom maxTokens value when specified", async () => {
    const llm = new AnthropicLLM({ apiKey: "test-key", maxTokens: 8192 });

    await llm.generateResponse([{ role: "user", content: "Hello" }]);

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        max_tokens: 8192,
      }),
    );
  });
});
