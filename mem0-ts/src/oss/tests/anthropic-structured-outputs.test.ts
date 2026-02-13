/// <reference types="jest" />

const mockCreate = jest.fn().mockResolvedValue({
  content: [{ type: "text", text: '{"facts": ["a"]}' }],
  stop_reason: "end_turn",
});

jest.mock("@anthropic-ai/sdk", () => {
  return jest.fn().mockImplementation(() => ({
    messages: { create: mockCreate },
  }));
});

jest.mock("@anthropic-ai/sdk/helpers/zod", () => ({
  zodOutputFormat: jest.fn((schema: any) => ({
    type: "json_schema",
    schema: { type: "object" },
  })),
}));

import { z } from "zod";
import { AnthropicLLM, supportsStructuredOutputs } from "../src/llms/anthropic";
import { zodOutputFormat } from "@anthropic-ai/sdk/helpers/zod";

describe("supportsStructuredOutputs", () => {
  it("should return true for Claude 4.x models", () => {
    expect(supportsStructuredOutputs("claude-opus-4-6")).toBe(true);
    expect(supportsStructuredOutputs("claude-sonnet-4-5-20250929")).toBe(true);
    expect(supportsStructuredOutputs("claude-haiku-4-5-20251001")).toBe(true);
  });

  it("should return false for Claude 3.x models", () => {
    expect(supportsStructuredOutputs("claude-3-5-sonnet-20241022")).toBe(false);
    expect(supportsStructuredOutputs("claude-3-sonnet-20240229")).toBe(false);
    expect(supportsStructuredOutputs("claude-3-haiku-20240307")).toBe(false);
  });
});

describe("AnthropicLLM structured outputs", () => {
  const TestSchema = z.object({ facts: z.array(z.string()) });

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.ANTHROPIC_API_KEY = "test-key";
  });

  afterEach(() => {
    delete process.env.ANTHROPIC_API_KEY;
  });

  it("should send output_config when schema provided on supported model", async () => {
    const llm = new AnthropicLLM({
      apiKey: "test-key",
      model: "claude-sonnet-4-5-20250929",
    });

    await llm.generateResponse([{ role: "user", content: "Hello" }], {
      type: "json_object",
      schema: TestSchema,
    });

    expect(zodOutputFormat).toHaveBeenCalledWith(TestSchema);
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        output_config: {
          format: { type: "json_schema", schema: { type: "object" } },
        },
      }),
    );
  });

  it("should not send output_config on unsupported model", async () => {
    const llm = new AnthropicLLM({
      apiKey: "test-key",
      model: "claude-3-5-sonnet-20241022",
    });

    await llm.generateResponse([{ role: "user", content: "Hello" }], {
      type: "json_object",
      schema: TestSchema,
    });

    expect(zodOutputFormat).not.toHaveBeenCalled();
    const callArgs = mockCreate.mock.calls[0][0];
    expect(callArgs.output_config).toBeUndefined();
  });

  it("should not send output_config when no schema provided", async () => {
    const llm = new AnthropicLLM({
      apiKey: "test-key",
      model: "claude-sonnet-4-5-20250929",
    });

    await llm.generateResponse([{ role: "user", content: "Hello" }], {
      type: "json_object",
    });

    expect(zodOutputFormat).not.toHaveBeenCalled();
    const callArgs = mockCreate.mock.calls[0][0];
    expect(callArgs.output_config).toBeUndefined();
  });
});
