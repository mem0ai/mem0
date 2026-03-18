/// <reference types="jest" />

jest.mock("@anthropic-ai/sdk", () => {
  return jest.fn().mockImplementation(() => ({
    messages: { create: jest.fn() },
  }));
});

import { AnthropicLLM } from "../src/llms/anthropic";

describe("AnthropicLLM", () => {
  describe("maxTokens configuration", () => {
    it("should use provided maxTokens value", () => {
      const llm = new AnthropicLLM({
        apiKey: "sk-ant-test",
        model: "claude-sonnet-4-20250514",
        maxTokens: 8192,
      });

      expect((llm as any).maxTokens).toBe(8192);
    });

    it("should default to 4096 when maxTokens is not provided", () => {
      const llm = new AnthropicLLM({
        apiKey: "sk-ant-test",
      });

      expect((llm as any).maxTokens).toBe(4096);
    });

    it("should default to 4096 when maxTokens is undefined", () => {
      const llm = new AnthropicLLM({
        apiKey: "sk-ant-test",
        maxTokens: undefined,
      });

      expect((llm as any).maxTokens).toBe(4096);
    });
  });
});
