/**
 * Regression tests for graph_memory.ts response parsing (issue #4248).
 *
 * Exercises the three json_object call sites in MemoryGraph with a mocked LLM:
 *   1. _retrieveNodesFromData  → entity extraction
 *   2. _establishNodesRelationsFromData → relation extraction
 *   3. _getDeleteEntitiesFromSearchOutput → deletion identification
 *
 * Covers: malformed LLM responses, missing fields, bad JSON in toolCalls,
 * string-only responses, empty tool calls, and prompt construction.
 *
 * See: https://github.com/mem0ai/mem0/issues/4248
 */

import { MemoryGraph } from "../src/memory/graph_memory";
import {
  EXTRACT_RELATIONS_PROMPT,
  getDeleteMessages,
} from "../src/graphs/utils";

// ---------------------------------------------------------------------------
// Mocks – we replace heavy dependencies so tests run without Neo4j / OpenAI
// ---------------------------------------------------------------------------

// Mock neo4j-driver: provides a fake Driver with a no-op session
jest.mock("neo4j-driver", () => ({
  __esModule: true,
  default: {
    driver: jest.fn(() => ({
      session: () => ({
        run: jest.fn().mockResolvedValue({ records: [] }),
        close: jest.fn(),
      }),
    })),
    auth: { basic: jest.fn() },
  },
}));

// Mock factory so constructor doesn't try to instantiate real LLMs / embedders
const mockGenerateResponse = jest.fn();
const mockGenerateChat = jest.fn();
const mockEmbed = jest.fn().mockResolvedValue([0.1, 0.2, 0.3]);

jest.mock("../src/utils/factory", () => ({
  LLMFactory: {
    create: jest.fn(() => ({
      generateResponse: mockGenerateResponse,
      generateChat: mockGenerateChat,
    })),
  },
  EmbedderFactory: {
    create: jest.fn(() => ({
      embed: mockEmbed,
    })),
  },
}));

// Minimal config that satisfies the MemoryGraph constructor
function makeConfig(overrides: Record<string, any> = {}) {
  return {
    graphStore: {
      config: {
        url: "bolt://localhost:7687",
        username: "neo4j",
        password: "test",
      },
      ...overrides,
    },
    embedder: { provider: "openai", config: {} },
    llm: { provider: "openai", config: {} },
  } as any;
}

// Helper to access private methods via `any` cast
function graph(overrides: Record<string, any> = {}): any {
  return new MemoryGraph(makeConfig(overrides));
}

const FILTERS = { userId: "test-user" };

beforeEach(() => {
  jest.clearAllMocks();
});

// ═══════════════════════════════════════════════════════════════════════════
// 1. _retrieveNodesFromData – entity extraction
// ═══════════════════════════════════════════════════════════════════════════

describe("_retrieveNodesFromData", () => {
  it("parses a well-formed extract_entities tool call", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [
        {
          name: "extract_entities",
          arguments: JSON.stringify({
            entities: [
              { entity: "Alice", entity_type: "person" },
              { entity: "Pizza", entity_type: "food" },
            ],
          }),
        },
      ],
    });

    const mg = graph();
    const result = await mg._retrieveNodesFromData(
      "Alice likes pizza",
      FILTERS,
    );

    expect(result).toEqual({ alice: "person", pizza: "food" });
  });

  it("returns empty map when LLM returns a plain string", async () => {
    mockGenerateResponse.mockResolvedValueOnce("I am a string, not an object");

    const mg = graph();
    const result = await mg._retrieveNodesFromData("anything", FILTERS);

    expect(result).toEqual({});
  });

  it("returns empty map when toolCalls is undefined", async () => {
    mockGenerateResponse.mockResolvedValueOnce({});

    const mg = graph();
    const result = await mg._retrieveNodesFromData("anything", FILTERS);

    expect(result).toEqual({});
  });

  it("returns empty map when toolCalls is an empty array", async () => {
    mockGenerateResponse.mockResolvedValueOnce({ toolCalls: [] });

    const mg = graph();
    const result = await mg._retrieveNodesFromData("anything", FILTERS);

    expect(result).toEqual({});
  });

  it("handles malformed JSON in tool call arguments gracefully", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [
        { name: "extract_entities", arguments: "NOT VALID JSON {{{" },
      ],
    });

    const mg = graph();
    // Should not throw — the catch block in the source logs the error
    const result = await mg._retrieveNodesFromData("anything", FILTERS);
    expect(result).toEqual({});
  });

  it("handles missing entities array in arguments", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [
        {
          name: "extract_entities",
          arguments: JSON.stringify({ wrong_key: [] }),
        },
      ],
    });

    const mg = graph();
    // args.entities is undefined → for..of on undefined throws → caught
    const result = await mg._retrieveNodesFromData("anything", FILTERS);
    expect(result).toEqual({});
  });

  it("skips tool calls with unrelated names", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [
        {
          name: "some_other_tool",
          arguments: JSON.stringify({
            entities: [{ entity: "X", entity_type: "Y" }],
          }),
        },
      ],
    });

    const mg = graph();
    const result = await mg._retrieveNodesFromData("anything", FILTERS);
    expect(result).toEqual({});
  });

  it("normalises entity names to lowercase with underscores", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [
        {
          name: "extract_entities",
          arguments: JSON.stringify({
            entities: [{ entity: "New York City", entity_type: "City Name" }],
          }),
        },
      ],
    });

    const mg = graph();
    const result = await mg._retrieveNodesFromData("anything", FILTERS);
    expect(result).toEqual({ new_york_city: "city_name" });
  });

  it("passes json_object response format and the correct system prompt", async () => {
    mockGenerateResponse.mockResolvedValueOnce({ toolCalls: [] });

    const mg = graph();
    await mg._retrieveNodesFromData("test data", FILTERS);

    const [messages, responseFormat] = mockGenerateResponse.mock.calls[0];
    expect(responseFormat).toEqual({ type: "json_object" });

    const systemMsg = messages[0].content as string;
    expect(systemMsg.toLowerCase()).toContain("json");
    expect(systemMsg).toContain("test-user");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// 2. _establishNodesRelationsFromData – relation extraction
// ═══════════════════════════════════════════════════════════════════════════

describe("_establishNodesRelationsFromData", () => {
  it("parses a well-formed establish_relationships tool call", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [
        {
          name: "establish_relationships",
          arguments: JSON.stringify({
            entities: [
              { source: "Alice", relationship: "likes", destination: "Pizza" },
            ],
          }),
        },
      ],
    });

    const mg = graph();
    const result = await mg._establishNodesRelationsFromData(
      "Alice likes pizza",
      FILTERS,
      { alice: "person", pizza: "food" },
    );

    expect(result).toEqual([
      { source: "alice", relationship: "likes", destination: "pizza" },
    ]);
  });

  it("returns empty array when LLM returns a string", async () => {
    mockGenerateResponse.mockResolvedValueOnce("just a string");

    const mg = graph();
    const result = await mg._establishNodesRelationsFromData("x", FILTERS, {});
    expect(result).toEqual([]);
  });

  it("returns empty array when toolCalls is empty", async () => {
    mockGenerateResponse.mockResolvedValueOnce({ toolCalls: [] });

    const mg = graph();
    const result = await mg._establishNodesRelationsFromData("x", FILTERS, {});
    expect(result).toEqual([]);
  });

  it("returns empty array when entities key is missing from arguments", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [
        {
          name: "establish_relationships",
          arguments: JSON.stringify({ not_entities: [] }),
        },
      ],
    });

    const mg = graph();
    const result = await mg._establishNodesRelationsFromData("x", FILTERS, {});
    // args.entities is undefined → falls back to []
    expect(result).toEqual([]);
  });

  it("throws on malformed JSON in tool call arguments (no try/catch in source)", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [{ name: "establish_relationships", arguments: "<<BROKEN>>" }],
    });

    const mg = graph();
    // _establishNodesRelationsFromData does JSON.parse without try/catch
    await expect(
      mg._establishNodesRelationsFromData("x", FILTERS, {}),
    ).rejects.toThrow();
  });

  it("appends JSON format suffix to system prompt (no custom prompt)", async () => {
    mockGenerateResponse.mockResolvedValueOnce({ toolCalls: [] });

    const mg = graph();
    await mg._establishNodesRelationsFromData("data", FILTERS, { a: "b" });

    const [messages, responseFormat] = mockGenerateResponse.mock.calls[0];
    expect(responseFormat).toEqual({ type: "json_object" });

    const systemContent = messages[0].content as string;
    expect(systemContent.toLowerCase()).toContain("json");
    expect(systemContent).toContain("test-user");
    expect(systemContent).not.toContain("USER_ID");
    // CUSTOM_PROMPT placeholder stays when no custom prompt is configured
    // (only replaced when config.graphStore.customPrompt is set)
  });

  it("appends JSON format suffix and custom prompt when configured", async () => {
    mockGenerateResponse.mockResolvedValueOnce({ toolCalls: [] });

    const mg = graph({ customPrompt: "Focus on food relationships only." });
    await mg._establishNodesRelationsFromData("data", FILTERS, {});

    const [messages] = mockGenerateResponse.mock.calls[0];
    const systemContent = messages[0].content as string;
    expect(systemContent.toLowerCase()).toContain("json");
    expect(systemContent).toContain("Focus on food relationships only.");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// 3. _getDeleteEntitiesFromSearchOutput – deletion identification
// ═══════════════════════════════════════════════════════════════════════════

describe("_getDeleteEntitiesFromSearchOutput", () => {
  const SEARCH_OUTPUT = [
    {
      source: "alice",
      source_id: "1",
      relationship: "likes",
      relation_id: "r1",
      destination: "pizza",
      destination_id: "2",
      similarity: 0.95,
    },
  ];

  it("parses a well-formed delete_graph_memory tool call", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [
        {
          name: "delete_graph_memory",
          arguments: JSON.stringify({
            source: "Alice",
            relationship: "likes",
            destination: "Pizza",
          }),
        },
      ],
    });

    const mg = graph();
    const result = await mg._getDeleteEntitiesFromSearchOutput(
      SEARCH_OUTPUT,
      "Alice hates pizza",
      FILTERS,
    );

    expect(result).toEqual([
      { source: "alice", relationship: "likes", destination: "pizza" },
    ]);
  });

  it("returns empty array when LLM returns a string", async () => {
    mockGenerateResponse.mockResolvedValueOnce("string response");

    const mg = graph();
    const result = await mg._getDeleteEntitiesFromSearchOutput(
      SEARCH_OUTPUT,
      "x",
      FILTERS,
    );
    expect(result).toEqual([]);
  });

  it("returns empty array when no tool calls are present", async () => {
    mockGenerateResponse.mockResolvedValueOnce({ toolCalls: [] });

    const mg = graph();
    const result = await mg._getDeleteEntitiesFromSearchOutput(
      SEARCH_OUTPUT,
      "x",
      FILTERS,
    );
    expect(result).toEqual([]);
  });

  it("skips non-delete_graph_memory tool calls", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [
        {
          name: "noop",
          arguments: JSON.stringify({}),
        },
      ],
    });

    const mg = graph();
    const result = await mg._getDeleteEntitiesFromSearchOutput(
      SEARCH_OUTPUT,
      "x",
      FILTERS,
    );
    expect(result).toEqual([]);
  });

  it("collects multiple delete tool calls", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [
        {
          name: "delete_graph_memory",
          arguments: JSON.stringify({
            source: "A",
            relationship: "r1",
            destination: "B",
          }),
        },
        {
          name: "delete_graph_memory",
          arguments: JSON.stringify({
            source: "C",
            relationship: "r2",
            destination: "D",
          }),
        },
      ],
    });

    const mg = graph();
    const result = await mg._getDeleteEntitiesFromSearchOutput(
      SEARCH_OUTPUT,
      "x",
      FILTERS,
    );
    expect(result).toHaveLength(2);
    expect(result[0].source).toBe("a");
    expect(result[1].source).toBe("c");
  });

  it("passes json_object format and includes 'json' in system prompt", async () => {
    mockGenerateResponse.mockResolvedValueOnce({ toolCalls: [] });

    const mg = graph();
    await mg._getDeleteEntitiesFromSearchOutput(SEARCH_OUTPUT, "data", FILTERS);

    const [messages, responseFormat] = mockGenerateResponse.mock.calls[0];
    expect(responseFormat).toEqual({ type: "json_object" });

    const systemContent = messages[0].content as string;
    expect(systemContent.toLowerCase()).toContain("json");
    expect(systemContent).toContain("test-user");
    expect(systemContent).not.toContain("USER_ID");
  });

  it("handles empty searchOutput array", async () => {
    mockGenerateResponse.mockResolvedValueOnce({ toolCalls: [] });

    const mg = graph();
    const result = await mg._getDeleteEntitiesFromSearchOutput(
      [],
      "data",
      FILTERS,
    );
    expect(result).toEqual([]);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// 4. Prompt construction — JSON keyword present in every json_object site
// ═══════════════════════════════════════════════════════════════════════════

describe("Prompt construction — all json_object sites include 'json'", () => {
  it("_retrieveNodesFromData system message includes 'json' for any userId", async () => {
    for (const userId of ["", "user-1", "special<>chars", "ユーザー"]) {
      mockGenerateResponse.mockResolvedValueOnce({ toolCalls: [] });
      const mg = graph();
      await mg._retrieveNodesFromData("test", { userId });

      const systemMsg = mockGenerateResponse.mock.calls.at(-1)![0][0].content;
      expect(systemMsg.toLowerCase()).toContain("json");
    }
  });

  it("_establishNodesRelationsFromData system message includes 'json' for any userId", async () => {
    for (const userId of ["", "user-1", "special<>chars"]) {
      mockGenerateResponse.mockResolvedValueOnce({ toolCalls: [] });
      const mg = graph();
      await mg._establishNodesRelationsFromData("test", { userId }, {});

      const systemMsg = mockGenerateResponse.mock.calls.at(-1)![0][0].content;
      expect(systemMsg.toLowerCase()).toContain("json");
    }
  });

  it("_getDeleteEntitiesFromSearchOutput system message includes 'json' for any userId", async () => {
    for (const userId of ["", "user-1", "special<>chars"]) {
      mockGenerateResponse.mockResolvedValueOnce({ toolCalls: [] });
      const mg = graph();
      await mg._getDeleteEntitiesFromSearchOutput([], "test", { userId });

      const systemMsg = mockGenerateResponse.mock.calls.at(-1)![0][0].content;
      expect(systemMsg.toLowerCase()).toContain("json");
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// 5. Edge cases – malformed entity fields in _removeSpacesFromEntities
// ═══════════════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════════════════
// 5a. LLM config propagation — graph store uses correct provider & config
//     Regression test for https://github.com/mem0ai/mem0/issues/3425
// ═══════════════════════════════════════════════════════════════════════════

describe("LLM config propagation to graph store (issue #3425)", () => {
  const { LLMFactory } = require("../src/utils/factory");

  beforeEach(() => {
    (LLMFactory.create as jest.Mock).mockClear();
  });

  it("uses root llm config when no graphStore.llm is provided", () => {
    const config = {
      graphStore: {
        config: {
          url: "bolt://localhost:7687",
          username: "neo4j",
          password: "test",
        },
      },
      embedder: { provider: "openai", config: {} },
      llm: {
        provider: "anthropic",
        config: { model: "claude-sonnet-4-20250514", apiKey: "sk-ant-test" },
      },
    } as any;

    new MemoryGraph(config);

    expect(LLMFactory.create).toHaveBeenCalledWith("anthropic", {
      model: "claude-sonnet-4-20250514",
      apiKey: "sk-ant-test",
    });
    // Both llm and structuredLlm should use the same config
    expect(LLMFactory.create).toHaveBeenCalledTimes(2);
    expect(LLMFactory.create).toHaveBeenNthCalledWith(1, "anthropic", {
      model: "claude-sonnet-4-20250514",
      apiKey: "sk-ant-test",
    });
    expect(LLMFactory.create).toHaveBeenNthCalledWith(2, "anthropic", {
      model: "claude-sonnet-4-20250514",
      apiKey: "sk-ant-test",
    });
  });

  it("uses graphStore.llm config when provided, overriding root llm", () => {
    const config = {
      graphStore: {
        config: {
          url: "bolt://localhost:7687",
          username: "neo4j",
          password: "test",
        },
        llm: {
          provider: "openai",
          config: { model: "gpt-4o", apiKey: "sk-openai-test" },
        },
      },
      embedder: { provider: "openai", config: {} },
      llm: {
        provider: "anthropic",
        config: { model: "claude-sonnet-4-20250514", apiKey: "sk-ant-test" },
      },
    } as any;

    new MemoryGraph(config);

    // Should use graphStore.llm, NOT root llm
    expect(LLMFactory.create).toHaveBeenNthCalledWith(1, "openai", {
      model: "gpt-4o",
      apiKey: "sk-openai-test",
    });
    expect(LLMFactory.create).toHaveBeenNthCalledWith(2, "openai", {
      model: "gpt-4o",
      apiKey: "sk-openai-test",
    });
  });

  it("falls back to root llm config when graphStore.llm.config is undefined", () => {
    // Note: in practice, Zod schema requires config when graphStore.llm is
    // present. This tests the defensive fallback in MemoryGraph itself.
    const config = {
      graphStore: {
        config: {
          url: "bolt://localhost:7687",
          username: "neo4j",
          password: "test",
        },
        llm: {
          provider: "openai",
          // config explicitly undefined
          config: undefined,
        },
      },
      embedder: { provider: "openai", config: {} },
      llm: {
        provider: "anthropic",
        config: { model: "claude-sonnet-4-20250514" },
      },
    } as any;

    new MemoryGraph(config);

    // Provider from graphStore.llm, but config falls back to root llm.config
    expect(LLMFactory.create).toHaveBeenNthCalledWith(1, "openai", {
      model: "claude-sonnet-4-20250514",
    });
  });

  it("defaults to openai when neither root nor graphStore llm provider is set", () => {
    const config = {
      graphStore: {
        config: {
          url: "bolt://localhost:7687",
          username: "neo4j",
          password: "test",
        },
      },
      embedder: { provider: "openai", config: {} },
      llm: { config: { model: "gpt-4" } },
    } as any;

    new MemoryGraph(config);

    expect(LLMFactory.create).toHaveBeenNthCalledWith(1, "openai", {
      model: "gpt-4",
    });
  });
});

describe("_removeSpacesFromEntities (via _establishNodesRelationsFromData)", () => {
  it("normalises spaces and case in entity source/relationship/destination", async () => {
    mockGenerateResponse.mockResolvedValueOnce({
      toolCalls: [
        {
          name: "establish_relationships",
          arguments: JSON.stringify({
            entities: [
              {
                source: "New York",
                relationship: "Capital Of",
                destination: "United States",
              },
            ],
          }),
        },
      ],
    });

    const mg = graph();
    const result = await mg._establishNodesRelationsFromData(
      "test",
      FILTERS,
      {},
    );

    expect(result).toEqual([
      {
        source: "new_york",
        relationship: "capital_of",
        destination: "united_states",
      },
    ]);
  });
});
