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
});
