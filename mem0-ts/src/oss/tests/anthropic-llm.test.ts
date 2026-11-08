/// <reference types="jest" />
/**
 * Anthropic LLM — unit tests (mocked @anthropic-ai/sdk).
 */

const mockCreate = jest.fn();
const mockConstructor = jest.fn();

jest.mock("@anthropic-ai/sdk", () => {
  return jest.fn().mockImplementation((args) => {
    mockConstructor(args);
    return { messages: { create: mockCreate } };
  });
});

import { AnthropicLLM } from "../src/llms/anthropic";

describe("AnthropicLLM (unit)", () => {
  beforeEach(() => {
    mockCreate.mockClear();
    mockConstructor.mockClear();
  });

  // Regression #5665: a configured baseURL must reach the Anthropic client so
  // proxy/gateway users are not silently bypassed (TS parity with #5626).
  // The client is constructed lazily on first use, so drive generateResponse.
  it("forwards baseURL to the Anthropic client when set", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "text", text: "ok" }],
    });
    const llm = new AnthropicLLM({
      apiKey: "test-key",
      baseURL: "https://proxy.example/v1",
    });
    await llm.generateResponse([{ role: "user", content: "Hi" }]);

    expect(mockConstructor).toHaveBeenCalledTimes(1);
    const ctorArgs = mockConstructor.mock.calls[0][0];
    expect(ctorArgs.apiKey).toBe("test-key");
    expect(ctorArgs.baseURL).toBe("https://proxy.example/v1");
  });

  // When no baseURL is configured the client must not receive a baseURL key
  // (so the SDK default endpoint is used).
  it("does NOT set baseURL when none is configured", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "text", text: "ok" }],
    });
    const llm = new AnthropicLLM({ apiKey: "test-key" });
    await llm.generateResponse([{ role: "user", content: "Hi" }]);

    expect(mockConstructor).toHaveBeenCalledTimes(1);
    const ctorArgs = mockConstructor.mock.calls[0][0];
    expect(ctorArgs.baseURL).toBeUndefined();
  });

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

  // Regression: thinking-enabled models emit a thinking block before the text
  // block. Indexing content[0] threw "Unexpected response type"; the text block
  // must be found by type instead (TS parity with #6481).
  it("returns the text block when a thinking block precedes it (no tools)", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [
        { type: "thinking", thinking: "Let me reason about this." },
        { type: "text", text: '{"facts": ["fact1"]}' },
      ],
    });

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse([
      { role: "user", content: "Hello" },
    ]);

    expect(result).toBe('{"facts": ["fact1"]}');
  });

  // A response carrying no text block at all must resolve to "" rather than throw.
  it("returns an empty string when no text block is present (no tools)", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "thinking", thinking: "Thinking only." }],
    });

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    await expect(
      llm.generateResponse([{ role: "user", content: "Hello" }]),
    ).resolves.toBe("");
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

  // #6203 (TS parity with #5820): Anthropic has no native response_format, so
  // json_object must be translated into an assistant "{" prefill + a JSON
  // system instruction, and the leading brace re-attached on the way out.
  it("prefills '{' and appends a JSON instruction for response_format json_object", async () => {
    // Model continues the object after the prefilled "{".
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "text", text: '"facts": ["a"]}' }],
    });

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [
        { role: "system", content: "sys" },
        { role: "user", content: "Hi" },
      ],
      { type: "json_object" },
    );

    const callArgs = mockCreate.mock.calls[0][0];
    // Assistant turn prefilled with "{"
    expect(callArgs.messages[callArgs.messages.length - 1]).toEqual({
      role: "assistant",
      content: "{",
    });
    // JSON-only instruction appended to system
    expect(callArgs.system).toContain("valid JSON only");
    // Leading brace re-attached → full, parseable JSON
    expect(JSON.parse(result as string)).toEqual({ facts: ["a"] });
  });

  // The prefill path must find the text block rather than index content[0],
  // otherwise thinking-enabled models break json_object mode (same defect
  // #6506 fixed for the plain-text path).
  it("finds the text block for json_object when a thinking block precedes it", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [
        { type: "thinking", thinking: "considering" },
        { type: "text", text: '"facts": ["a"]}' },
      ],
    });

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [{ role: "user", content: "Hi" }],
      { type: "json_object" },
    );

    expect(JSON.parse(result as string)).toEqual({ facts: ["a"] });
  });

  it("returns an empty string for json_object when no text block is present", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "thinking", thinking: "considering" }],
    });

    const llm = new AnthropicLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [{ role: "user", content: "Hi" }],
      { type: "json_object" },
    );

    // A bare "{" would be worse than nothing — no parser can use it.
    expect(result).toBe("");
  });

  // json_schema → the Anthropic structured-outputs output_config.format.
  it("maps response_format json_schema to output_config.format", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "text", text: '{"ok": true}' }],
    });

    const schema = {
      type: "object",
      properties: { ok: { type: "boolean" } },
    };
    const llm = new AnthropicLLM({ apiKey: "test-key" });
    await llm.generateResponse([{ role: "user", content: "Hi" }], {
      type: "json_schema",
      json_schema: { schema },
    });

    const callArgs = mockCreate.mock.calls[0][0];
    expect(callArgs.output_config).toEqual({
      format: { type: "json_schema", schema },
    });
    // json_schema must not use the prefill path
    expect(
      callArgs.messages.some(
        (m: { role: string; content: string }) =>
          m.role === "assistant" && m.content === "{",
      ),
    ).toBe(false);
  });

  // response_format is ignored when tools are active (tool_use blocks would be
  // dropped by the JSON prefill/extract path).
  it("ignores response_format when tools are provided", async () => {
    mockCreate.mockResolvedValueOnce({
      content: [{ type: "tool_use", id: "t1", name: "add", input: { a: 1 } }],
    });

    const tools = [
      {
        name: "add",
        description: "add",
        input_schema: { type: "object", properties: {} },
      },
    ];
    const llm = new AnthropicLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [{ role: "user", content: "Hi" }],
      { type: "json_object" },
      tools,
    );

    const callArgs = mockCreate.mock.calls[0][0];
    // No prefill injected, no JSON instruction, no output_config
    expect(
      callArgs.messages.some(
        (m: { role: string; content: string }) =>
          m.role === "assistant" && m.content === "{",
      ),
    ).toBe(false);
    expect(callArgs.system ?? "").not.toContain("valid JSON only");
    expect(callArgs.output_config).toBeUndefined();
    // Tools path still returns structured toolCalls
    expect(result).toHaveProperty("toolCalls");
  });
});
