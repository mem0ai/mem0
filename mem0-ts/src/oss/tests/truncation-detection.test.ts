/// <reference types="jest" />

// --- Anthropic mock ---
const mockAnthropicCreate = jest.fn();
jest.mock("@anthropic-ai/sdk", () => {
  return jest.fn().mockImplementation(() => ({
    messages: { create: mockAnthropicCreate },
  }));
});

// --- OpenAI mock ---
const mockOpenAICreate = jest.fn();
jest.mock("openai", () => {
  return jest.fn().mockImplementation(() => ({
    chat: { completions: { create: mockOpenAICreate } },
  }));
});

import { AnthropicLLM } from "../src/llms/anthropic";
import { OpenAILLM } from "../src/llms/openai";

describe("Truncation Detection", () => {
  let warnSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    warnSpy = jest.spyOn(console, "warn").mockImplementation();
    process.env.ANTHROPIC_API_KEY = "test-key";
  });

  afterEach(() => {
    warnSpy.mockRestore();
    delete process.env.ANTHROPIC_API_KEY;
  });

  describe("Anthropic", () => {
    it('should warn when stop_reason is "max_tokens"', async () => {
      mockAnthropicCreate.mockResolvedValue({
        content: [{ type: "text", text: '{"partial": true' }],
        stop_reason: "max_tokens",
      });

      const llm = new AnthropicLLM({ apiKey: "test-key" });
      const result = await llm.generateResponse([
        { role: "user", content: "Hello" },
      ]);

      expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("[mem0]"));
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining("max_tokens"),
      );
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining("Consider increasing maxTokens"),
      );
      // Response should still be returned
      expect(result).toBe('{"partial": true');
    });

    it('should not warn when stop_reason is "end_turn"', async () => {
      mockAnthropicCreate.mockResolvedValue({
        content: [{ type: "text", text: '{"result": "ok"}' }],
        stop_reason: "end_turn",
      });

      const llm = new AnthropicLLM({ apiKey: "test-key" });
      await llm.generateResponse([{ role: "user", content: "Hello" }]);

      expect(warnSpy).not.toHaveBeenCalled();
    });
  });

  describe("OpenAI", () => {
    it('should warn when finish_reason is "length"', async () => {
      mockOpenAICreate.mockResolvedValue({
        choices: [
          {
            message: { content: '{"partial": true', role: "assistant" },
            finish_reason: "length",
          },
        ],
      });

      const llm = new OpenAILLM({ apiKey: "test-key" });
      const result = await llm.generateResponse([
        { role: "user", content: "Hello" },
      ]);

      expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining("[mem0]"));
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining("Consider increasing maxTokens"),
      );
      // Response should still be returned
      expect(result).toBe('{"partial": true');
    });

    it('should not warn when finish_reason is "stop"', async () => {
      mockOpenAICreate.mockResolvedValue({
        choices: [
          {
            message: { content: '{"result": "ok"}', role: "assistant" },
            finish_reason: "stop",
          },
        ],
      });

      const llm = new OpenAILLM({ apiKey: "test-key" });
      await llm.generateResponse([{ role: "user", content: "Hello" }]);

      expect(warnSpy).not.toHaveBeenCalled();
    });
  });
});
