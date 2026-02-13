/// <reference types="jest" />

jest.mock("@anthropic-ai/sdk", () => {
  const mockCreate = jest.fn().mockResolvedValue({
    content: [{ type: "text", text: '{"result": "ok"}' }],
    stop_reason: "end_turn",
  });
  return jest.fn().mockImplementation(() => ({
    messages: { create: mockCreate },
  }));
});

import Anthropic from "@anthropic-ai/sdk";
import { AnthropicLLM } from "../src/llms/anthropic";

describe("AnthropicLLM", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    process.env.ANTHROPIC_API_KEY = "test-key";
  });

  afterEach(() => {
    delete process.env.ANTHROPIC_API_KEY;
  });

  describe("default model", () => {
    it("should use claude-sonnet-4-5-20250929 when no model specified", () => {
      const llm = new AnthropicLLM({ apiKey: "test-key" });

      // Access private model field via type assertion
      expect((llm as any).model).toBe("claude-sonnet-4-5-20250929");
    });

    it("should use custom model when specified", () => {
      const llm = new AnthropicLLM({
        apiKey: "test-key",
        model: "claude-opus-4-6",
      });

      expect((llm as any).model).toBe("claude-opus-4-6");
    });
  });

  describe("generateResponse", () => {
    it("should pass model to SDK messages.create", async () => {
      const llm = new AnthropicLLM({ apiKey: "test-key" });

      await llm.generateResponse([{ role: "user", content: "Hello" }]);

      const mockInstance = (Anthropic as unknown as jest.Mock).mock.results[0]
        .value;
      expect(mockInstance.messages.create).toHaveBeenCalledWith(
        expect.objectContaining({
          model: "claude-sonnet-4-5-20250929",
        }),
      );
    });
  });
});
