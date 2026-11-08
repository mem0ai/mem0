/// <reference types="jest" />
/**
 * Google LLM — unit tests (mocked @google/genai).
 *
 * Regression tests for #4380: tools parameter was ignored, causing graph
 * memory operations to silently fail with Gemini models.
 */

const mockGenerateContent = jest.fn();

jest.mock("@google/genai", () => ({
  GoogleGenAI: jest.fn().mockImplementation(() => ({
    models: { generateContent: mockGenerateContent },
  })),
}));

import { GoogleLLM } from "../src/llms/google";

describe("GoogleLLM (unit)", () => {
  beforeEach(() => mockGenerateContent.mockClear());

  it("returns text response when no tools are provided", async () => {
    mockGenerateContent.mockResolvedValueOnce({
      text: '{"facts": ["fact1"]}',
      functionCalls: null,
    });

    const llm = new GoogleLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse([
      { role: "user", content: "Hello" },
    ]);

    expect(mockGenerateContent).toHaveBeenCalledTimes(1);
    expect(result).toBe('{"facts": ["fact1"]}');

    // Verify tools are not in config
    const callArgs = mockGenerateContent.mock.calls[0][0];
    expect(callArgs.config.tools).toBeUndefined();
  });

  it("forwards tools as functionDeclarations to Gemini API", async () => {
    mockGenerateContent.mockResolvedValueOnce({
      text: "",
      functionCalls: [
        {
          name: "extract_entities",
          args: { entities: [{ entity: "Alice", entity_type: "person" }] },
        },
      ],
    });

    const tools = [
      {
        type: "function",
        function: {
          name: "extract_entities",
          description: "Extract entities from text",
          parameters: {
            type: "object",
            properties: {
              entities: {
                type: "array",
                items: {
                  type: "object",
                  properties: {
                    entity: { type: "string" },
                    entity_type: { type: "string" },
                  },
                },
              },
            },
            required: ["entities"],
          },
        },
      },
    ];

    const llm = new GoogleLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [{ role: "user", content: "Alice is a person" }],
      undefined,
      tools,
    );

    // Verify functionDeclarations were passed in config
    const callArgs = mockGenerateContent.mock.calls[0][0];
    expect(callArgs.config.tools).toBeDefined();
    expect(callArgs.config.tools[0].functionDeclarations).toHaveLength(1);
    expect(callArgs.config.tools[0].functionDeclarations[0].name).toBe(
      "extract_entities",
    );

    // Verify toolCalls in response
    expect(result).toHaveProperty("toolCalls");
    const response = result as { toolCalls: any[] };
    expect(response.toolCalls).toHaveLength(1);
    expect(response.toolCalls[0].name).toBe("extract_entities");
    expect(JSON.parse(response.toolCalls[0].arguments)).toEqual({
      entities: [{ entity: "Alice", entity_type: "person" }],
    });
  });

  it("returns text when tools are provided but model returns text", async () => {
    mockGenerateContent.mockResolvedValueOnce({
      text: "Just a text response",
      functionCalls: null,
    });

    const tools = [
      {
        type: "function",
        function: {
          name: "noop",
          description: "No operation",
          parameters: { type: "object", properties: {} },
        },
      },
    ];

    const llm = new GoogleLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [{ role: "user", content: "Hello" }],
      undefined,
      tools,
    );

    // Should return text, not toolCalls
    expect(result).toBe("Just a text response");
  });

  it("strips markdown code fences from text responses", async () => {
    mockGenerateContent.mockResolvedValueOnce({
      text: '```json\n{"facts": ["fact1"]}\n```',
      functionCalls: null,
    });

    const llm = new GoogleLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse([
      { role: "user", content: "Extract facts" },
    ]);

    expect(result).toBe('{"facts": ["fact1"]}');
  });

  it("handles multiple function calls in response", async () => {
    mockGenerateContent.mockResolvedValueOnce({
      text: "",
      functionCalls: [
        {
          name: "add_graph_memory",
          args: { source: "Alice", destination: "Bob", relationship: "knows" },
        },
        {
          name: "add_graph_memory",
          args: {
            source: "Bob",
            destination: "Charlie",
            relationship: "works_with",
          },
        },
      ],
    });

    const tools = [
      {
        type: "function",
        function: {
          name: "add_graph_memory",
          description: "Add a graph memory",
          parameters: { type: "object", properties: {} },
        },
      },
    ];

    const llm = new GoogleLLM({ apiKey: "test-key" });
    const result = await llm.generateResponse(
      [{ role: "user", content: "Alice knows Bob, Bob works with Charlie" }],
      undefined,
      tools,
    );

    const response = result as { toolCalls: any[] };
    expect(response.toolCalls).toHaveLength(2);
    expect(response.toolCalls[0].name).toBe("add_graph_memory");
    expect(response.toolCalls[1].name).toBe("add_graph_memory");
  });

  // Regression: generateResponse accepted a responseFormat argument but never
  // forwarded it, so Gemini was never told to emit JSON (parity with the Python
  // SDK's mem0/llms/gemini.py, which sets response_mime_type/response_schema).
  it("forwards json_object responseFormat as responseMimeType", async () => {
    mockGenerateContent.mockResolvedValueOnce({
      text: '{"facts": ["fact1"]}',
      functionCalls: null,
    });

    const llm = new GoogleLLM({ apiKey: "test-key" });
    await llm.generateResponse([{ role: "user", content: "Extract facts" }], {
      type: "json_object",
    });

    const callArgs = mockGenerateContent.mock.calls[0][0];
    expect(callArgs.config.responseMimeType).toBe("application/json");
  });

  it("does not set responseMimeType when no responseFormat is given", async () => {
    mockGenerateContent.mockResolvedValueOnce({
      text: "plain text",
      functionCalls: null,
    });

    const llm = new GoogleLLM({ apiKey: "test-key" });
    await llm.generateResponse([{ role: "user", content: "Hello" }]);

    const callArgs = mockGenerateContent.mock.calls[0][0];
    expect(callArgs.config.responseMimeType).toBeUndefined();
  });

  it("formats generateChat messages and joins Gemini response parts", async () => {
    mockGenerateContent.mockResolvedValueOnce({
      candidates: [
        {
          content: {
            role: "model",
            parts: [{ text: "Hello" }, { text: ", world" }],
          },
        },
      ],
    });

    const llm = new GoogleLLM({ apiKey: "test-key" });
    const result = await llm.generateChat([
      { role: "system", content: "Be concise" },
      { role: "user", content: "Say hello" },
    ]);

    // The system message goes to systemInstruction (not a "model" content
    // turn), leaving only the user turn in contents.
    expect(mockGenerateContent).toHaveBeenCalledWith(
      expect.objectContaining({
        contents: [{ role: "user", parts: [{ text: "Say hello" }] }],
        config: expect.objectContaining({ systemInstruction: "Be concise" }),
      }),
    );
    expect(result).toEqual({ content: "Hello, world", role: "model" });
  });

  // Regression: the system prompt (which carries the extraction instructions)
  // must be sent via systemInstruction, not as a "model" content turn. Parity
  // with the Python SDK's _reformat_messages (mem0/llms/gemini.py).
  it("extracts the system prompt into config.systemInstruction", async () => {
    mockGenerateContent.mockResolvedValueOnce({
      text: "ok",
      functionCalls: null,
    });

    const llm = new GoogleLLM({ apiKey: "test-key" });
    await llm.generateResponse([
      { role: "system", content: "You extract facts." },
      { role: "user", content: "I like coffee." },
    ]);

    const callArgs = mockGenerateContent.mock.calls[0][0];
    expect(callArgs.config.systemInstruction).toBe("You extract facts.");
    // The system message must not leak into contents.
    expect(callArgs.contents).toEqual([
      { role: "user", parts: [{ text: "I like coffee." }] },
    ]);
  });

  // Regression: assistant turns map to Gemini's "model" role, not "user".
  it("maps assistant turns to the model role in contents", async () => {
    mockGenerateContent.mockResolvedValueOnce({
      text: "ok",
      functionCalls: null,
    });

    const llm = new GoogleLLM({ apiKey: "test-key" });
    await llm.generateResponse([
      { role: "user", content: "Hi" },
      { role: "assistant", content: "Hello there" },
      { role: "user", content: "How are you?" },
    ]);

    const callArgs = mockGenerateContent.mock.calls[0][0];
    expect(callArgs.contents).toEqual([
      { role: "user", parts: [{ text: "Hi" }] },
      { role: "model", parts: [{ text: "Hello there" }] },
      { role: "user", parts: [{ text: "How are you?" }] },
    ]);
  });

  it("returns an empty assistant response when generateChat has no candidates", async () => {
    mockGenerateContent.mockResolvedValueOnce({
      candidates: [],
      text: "",
    });

    const llm = new GoogleLLM({ apiKey: "test-key" });
    const result = await llm.generateChat([{ role: "user", content: "Hi" }]);

    expect(result).toEqual({ content: "", role: "assistant" });
  });
});
