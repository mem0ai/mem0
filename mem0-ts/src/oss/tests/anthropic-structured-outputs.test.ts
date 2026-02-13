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

const mockJsonSchemaOutputFormat = jest.fn((schema: any) => ({
  type: "json_schema",
  schema: { type: "object", source: "jsonSchema" },
}));

jest.mock("@anthropic-ai/sdk/helpers/json-schema", () => ({
  jsonSchemaOutputFormat: mockJsonSchemaOutputFormat,
}));

const mockZodOutputFormat = jest.fn((schema: any) => ({
  type: "json_schema",
  schema: { type: "object", source: "zod" },
}));

jest.mock("@anthropic-ai/sdk/helpers/zod", () => ({
  zodOutputFormat: mockZodOutputFormat,
}));

import { z } from "zod";
import { AnthropicLLM, supportsStructuredOutputs } from "../src/llms/anthropic";

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
  const TestJsonSchema = {
    type: "object" as const,
    properties: {
      facts: { type: "array" as const, items: { type: "string" as const } },
    },
    required: ["facts"] as const,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.ANTHROPIC_API_KEY = "test-key";
  });

  afterEach(() => {
    delete process.env.ANTHROPIC_API_KEY;
  });

  it("should use jsonSchemaOutputFormat as primary path when both schemas provided", async () => {
    const llm = new AnthropicLLM({
      apiKey: "test-key",
      model: "claude-sonnet-4-5-20250929",
    });

    await llm.generateResponse([{ role: "user", content: "Hello" }], {
      type: "json_object",
      schema: TestSchema,
      jsonSchema: TestJsonSchema,
    });

    expect(mockJsonSchemaOutputFormat).toHaveBeenCalledWith(TestJsonSchema);
    expect(mockZodOutputFormat).not.toHaveBeenCalled();
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        output_config: {
          format: {
            type: "json_schema",
            schema: { type: "object", source: "jsonSchema" },
          },
        },
      }),
    );
  });

  it("should fall back to zodOutputFormat when jsonSchema not provided", async () => {
    const llm = new AnthropicLLM({
      apiKey: "test-key",
      model: "claude-sonnet-4-5-20250929",
    });

    await llm.generateResponse([{ role: "user", content: "Hello" }], {
      type: "json_object",
      schema: TestSchema,
    });

    expect(mockJsonSchemaOutputFormat).not.toHaveBeenCalled();
    expect(mockZodOutputFormat).toHaveBeenCalledWith(TestSchema);
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        output_config: {
          format: {
            type: "json_schema",
            schema: { type: "object", source: "zod" },
          },
        },
      }),
    );
  });

  it("should fall back to zodOutputFormat when jsonSchemaOutputFormat throws", async () => {
    mockJsonSchemaOutputFormat.mockImplementationOnce(() => {
      throw new Error("jsonSchemaOutputFormat unavailable");
    });
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

    const llm = new AnthropicLLM({
      apiKey: "test-key",
      model: "claude-sonnet-4-5-20250929",
    });

    await llm.generateResponse([{ role: "user", content: "Hello" }], {
      type: "json_object",
      schema: TestSchema,
      jsonSchema: TestJsonSchema,
    });

    expect(mockJsonSchemaOutputFormat).toHaveBeenCalled();
    expect(mockZodOutputFormat).toHaveBeenCalledWith(TestSchema);
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("[mem0] jsonSchemaOutputFormat failed"),
      expect.any(String),
    );
    warnSpy.mockRestore();
  });

  it("should warn when both structured output methods fail", async () => {
    mockJsonSchemaOutputFormat.mockImplementationOnce(() => {
      throw new Error("jsonSchema failed");
    });
    mockZodOutputFormat.mockImplementationOnce(() => {
      throw new Error("zod failed");
    });
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

    const llm = new AnthropicLLM({
      apiKey: "test-key",
      model: "claude-sonnet-4-5-20250929",
    });

    await llm.generateResponse([{ role: "user", content: "Hello" }], {
      type: "json_object",
      schema: TestSchema,
      jsonSchema: TestJsonSchema,
    });

    expect(warnSpy).toHaveBeenCalledTimes(2);
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("[mem0] jsonSchemaOutputFormat failed"),
      expect.any(String),
    );
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("[mem0] Structured outputs unavailable"),
      expect.any(String),
    );
    const callArgs = mockCreate.mock.calls[0][0];
    expect(callArgs.output_config).toBeUndefined();
    warnSpy.mockRestore();
  });

  it("should not send output_config on unsupported model", async () => {
    const llm = new AnthropicLLM({
      apiKey: "test-key",
      model: "claude-3-5-sonnet-20241022",
    });

    await llm.generateResponse([{ role: "user", content: "Hello" }], {
      type: "json_object",
      schema: TestSchema,
      jsonSchema: TestJsonSchema,
    });

    expect(mockJsonSchemaOutputFormat).not.toHaveBeenCalled();
    expect(mockZodOutputFormat).not.toHaveBeenCalled();
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

    expect(mockJsonSchemaOutputFormat).not.toHaveBeenCalled();
    expect(mockZodOutputFormat).not.toHaveBeenCalled();
    const callArgs = mockCreate.mock.calls[0][0];
    expect(callArgs.output_config).toBeUndefined();
  });
});
