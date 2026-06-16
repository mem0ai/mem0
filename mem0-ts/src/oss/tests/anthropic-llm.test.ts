/// <reference types="jest" />
/**
 * Anthropic LLM — unit tests (mocked @anthropic-ai/sdk).
 */

const mockCreate = jest.fn();

jest.mock("@anthropic-ai/sdk", () => {
  return jest.fn().mockImplementation(() => ({
    messages: { create: mockCreate },
  }));
});

import { AnthropicLLM } from "../src/llms/anthropic";

describe("AnthropicLLM (unit)", () => {
  beforeEach(() => mockCreate.mockClear());

  it("returns text when no tools are provided and model returns a text block", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "text", text: '{"facts": ["fact1"]}' }],
    });

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse([
      { role: "user", content: "Hello" },
    ]);

    expect(mockCreate).toHaveBeenCalledTimes(1);
    expect(result).toBe('{"facts": ["fact1"]}');

    // No tools → tool_choice must NOT be forwarded
    const callArgs = mockCreate.mock.calls[0][0];
    expect(callArgs.tool_choice).toBeUndefined();
  });

  // Bug #1 regression: bare string "auto" must NOT be sent; object form required
  it("forwards tool_choice as { type: 'auto' } (not bare string) when tools are provided", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [
        {
          type: "tool_use",
          id: "toolu_1",
          name: "add_graph_memory",
          input: { source: "Alice", destination: "Bob" },
        },
      ],
    });

    const tools = [
      {
        name: "add_graph_memory",
        description: "Add a graph memory",
        input_schema: { type: "object", properties: {} },
      },
    ];

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    await llm.generateResponse(
      [{ role: "user", content: "Alice knows Bob" }],
      undefined,
      tools,
    );

    const callArgs = mockCreate.mock.calls[0][0];
    // Must be object form, not a bare string
    expect(callArgs.tool_choice).toEqual({ type: "auto" });
    expect(callArgs.tool_choice).not.toBe("auto");
  });

  // Bug #2 regression: must NOT throw on a tool_use block
  it("does NOT throw when the model returns a tool_use block", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [
        {
          type: "tool_use",
          id: "toolu_1",
          name: "add_graph_memory",
          input: { source: "Alice", destination: "Bob" },
        },
      ],
    });

    const tools = [
      {
        name: "add_graph_memory",
        description: "Add a graph memory",
        input_schema: { type: "object", properties: {} },
      },
    ];

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    await expect(
      llm.generateResponse(
        [{ role: "user", content: "Alice knows Bob" }],
        undefined,
        tools,
      ),
    ).resolves.not.toThrow();
  });

  it("parses tool_use blocks into toolCalls with JSON-stringified arguments", async () => {
    const inputObj = { source: "Alice", destination: "Bob" };
    mockCreate.mockResolvedValueOnce({
      content: [
        {
          type: "tool_use",
          id: "toolu_1",
          name: "add_graph_memory",
          input: inputObj,
        },
      ],
    });

    const tools = [
      {
        name: "add_graph_memory",
        description: "Add a graph memory",
        input_schema: { type: "object", properties: {} },
      },
    ];

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [{ role: "user", content: "Alice knows Bob" }],
      undefined,
      tools,
    );

    expect(result).toHaveProperty("toolCalls");
    const response = result as {
      content: string;
      role: string;
      toolCalls: Array<{ name: string; arguments: string }>;
    };
    expect(response.toolCalls).toHaveLength(1);
    expect(response.toolCalls[0].name).toBe("add_graph_memory");
    expect(JSON.parse(response.toolCalls[0].arguments)).toEqual(inputObj);
  });

  it("handles a mixed text + tool_use response", async () => {
    const inputObj = { source: "Alice", destination: "Bob" };
    mockCreate.mockResolvedValueOnce({
      content: [
        { type: "text", text: "Calling the tool now." },
        {
          type: "tool_use",
          id: "toolu_2",
          name: "add_graph_memory",
          input: inputObj,
        },
      ],
    });

    const tools = [
      {
        name: "add_graph_memory",
        description: "Add a graph memory",
        input_schema: { type: "object", properties: {} },
      },
    ];

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [{ role: "user", content: "Alice knows Bob" }],
      undefined,
      tools,
    );

    expect(result).toHaveProperty("toolCalls");
    const response = result as {
      content: string;
      role: string;
      toolCalls: Array<{ name: string; arguments: string }>;
    };
    expect(response.content).toBe("Calling the tool now.");
    expect(response.role).toBe("assistant");
    expect(response.toolCalls).toHaveLength(1);
    expect(response.toolCalls[0].name).toBe("add_graph_memory");
    expect(JSON.parse(response.toolCalls[0].arguments)).toEqual(inputObj);
  });

  it("returns a structured response when tools are provided but the model returns only a text block", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "text", text: "Just a text response" }],
    });

    const tools = [
      {
        name: "noop",
        description: "No operation",
        input_schema: { type: "object", properties: {} },
      },
    ];

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [{ role: "user", content: "Hello" }],
      undefined,
      tools,
    );

    expect(result).toEqual({
      content: "Just a text response",
      role: "assistant",
      toolCalls: [],
    });
  });

  // Parity with the Python provider's AnthropicConfig defaults:
  // model claude-sonnet-4-6, max_tokens 2000, temperature 0.1, top_p omitted.
  it("sends Python-parity defaults (model, max_tokens, temperature)", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "text", text: "ok" }],
    });

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    await llm.generateResponse([{ role: "user", content: "Hi" }]);

    const callArgs = mockCreate.mock.calls[0][0];
    expect(callArgs.model).toBe("claude-sonnet-4-6");
    expect(callArgs.max_tokens).toBe(2000);
    expect(callArgs.temperature).toBe(0.1);
    expect(callArgs.top_p).toBeUndefined();
  });

  it("forwards maxTokens, temperature, and model from config", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "text", text: "ok" }],
    });

    const llm = new AnthropicLLM({
      apiKey: "test-key",
      model: "claude-opus-4-8",
      maxTokens: 1024,
      temperature: 0.7,
    });
    await llm.generateResponse([{ role: "user", content: "Hi" }]);

    const callArgs = mockCreate.mock.calls[0][0];
    expect(callArgs.model).toBe("claude-opus-4-8");
    expect(callArgs.max_tokens).toBe(1024);
    expect(callArgs.temperature).toBe(0.7);
  });

  // Anthropic rejects requests with both temperature and top_p set.
  it("never sends both temperature and top_p (prefers temperature)", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "text", text: "ok" }],
    });

    const llm = new AnthropicLLM({
      apiKey: "test-key",
      temperature: 0.5,
      topP: 0.9,
    });
    await llm.generateResponse([{ role: "user", content: "Hi" }]);

    const callArgs = mockCreate.mock.calls[0][0];
    expect(callArgs.temperature).toBe(0.5);
    expect(callArgs.top_p).toBeUndefined();
  });
});
