/// <reference types="jest" />
import { MemoryGraph } from "../src/memory/graph_memory";
import { MemoryConfig } from "../src/types";
import neo4j from "neo4j-driver";
import { EmbedderFactory, LLMFactory } from "../src/utils/factory";

jest.setTimeout(30000);

// Mock neo4j-driver
jest.mock("neo4j-driver", () => {
  const mockSession = {
    run: jest.fn(),
    close: jest.fn().mockResolvedValue(undefined),
  };

  const mockDriver = {
    session: jest.fn().mockReturnValue(mockSession),
    close: jest.fn().mockResolvedValue(undefined),
  };

  return {
    __esModule: true,
    default: {
      driver: jest.fn().mockReturnValue(mockDriver),
      auth: {
        basic: jest.fn().mockReturnValue({}),
      },
    },
    driver: jest.fn().mockReturnValue(mockDriver),
    auth: {
      basic: jest.fn().mockReturnValue({}),
    },
  };
});

// Mock factories
jest.mock("../src/utils/factory", () => ({
  EmbedderFactory: {
    create: jest.fn(),
  },
  LLMFactory: {
    create: jest.fn(),
  },
}));

describe("MemoryGraph - Entity Type Label Sanitization", () => {
  let mockDriver: any;
  let mockSession: any;
  let mockRun: jest.Mock;
  let memoryGraph: MemoryGraph;
  let mockEmbedder: any;
  let mockLLM: any;
  let mockStructuredLLM: any;

  beforeEach(() => {
    // Get the mocked driver instance
    mockDriver = (neo4j.driver as jest.Mock)();
    mockSession = mockDriver.session();
    mockRun = mockSession.run as jest.Mock;

    // Create mock embedder
    mockEmbedder = {
      embed: jest.fn().mockResolvedValue([0.1, 0.2, 0.3]),
    };

    // Create mock LLM
    mockLLM = {
      generateResponse: jest.fn().mockResolvedValue("{}"),
    };

    // Create mock structured LLM
    mockStructuredLLM = {
      generateResponse: jest.fn().mockResolvedValue({
        toolCalls: [
          {
            name: "extract_entities",
            arguments: JSON.stringify({
              entities: [
                { entity: "alice", entity_type: "Person-Name" },
                { entity: "bob", entity_type: "City/State" },
              ],
            }),
          },
        ],
      }),
    };

    // Setup factory mocks
    (EmbedderFactory.create as jest.Mock).mockReturnValue(mockEmbedder);
    (LLMFactory.create as jest.Mock).mockReturnValue(mockLLM);

    const config: MemoryConfig = {
      version: "v1.1",
      embedder: {
        provider: "openai",
        config: {
          apiKey: "test-key",
          model: "text-embedding-3-small",
        },
      },
      vectorStore: {
        provider: "memory",
        config: {
          collectionName: "test-memories",
          dimension: 1536,
        },
      },
      graphStore: {
        provider: "neo4j",
        config: {
          url: "bolt://localhost:7687",
          username: "neo4j",
          password: "password",
        },
      },
      llm: {
        provider: "openai",
        config: {
          apiKey: "test-key",
          model: "gpt-4",
        },
      },
    };

    memoryGraph = new MemoryGraph(config);
    // Replace the structured LLM with our mock
    (memoryGraph as any).structuredLlm = mockStructuredLLM;
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe("Label Sanitization", () => {
    it("should sanitize entity types with special characters in Cypher queries", async () => {
      // Mock the search methods to return empty results (new nodes will be created)
      jest.spyOn(memoryGraph as any, "_searchSourceNode").mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_searchDestinationNode")
        .mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_retrieveNodesFromData")
        .mockResolvedValue({
          alice: "Person-Name",
          bob: "City/State",
        });
      jest
        .spyOn(memoryGraph as any, "_establishNodesRelationsFromData")
        .mockResolvedValue([
          {
            source: "alice",
            destination: "bob",
            relationship: "lives_in",
          },
        ]);
      jest.spyOn(memoryGraph as any, "_searchGraphDb").mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_getDeleteEntitiesFromSearchOutput")
        .mockResolvedValue([]);
      jest.spyOn(memoryGraph as any, "_deleteEntities").mockResolvedValue([]);

      // Mock session.run to capture the Cypher query
      const capturedQueries: string[] = [];
      mockRun.mockImplementation((cypher: string) => {
        capturedQueries.push(cypher);
        return Promise.resolve({
          records: [
            {
              get: (key: string) => {
                if (key === "source") return "alice";
                if (key === "relationship") return "lives_in";
                if (key === "target") return "bob";
                return null;
              },
            },
          ],
        });
      });

      await memoryGraph.add("Alice lives in Bob", { userId: "test-user" });

      // Verify that at least one query was executed
      expect(mockRun).toHaveBeenCalled();

      // Check that the Cypher queries contain sanitized labels
      const allQueries = capturedQueries.join(" ");
      expect(allQueries).toContain("Person_Name"); // Person-Name should be sanitized to Person_Name
      expect(allQueries).toContain("City_State"); // City/State should be sanitized to City_State
      expect(allQueries).not.toContain("Person-Name"); // Original should not appear
      expect(allQueries).not.toContain("City/State"); // Original should not appear
    });

    it("should preserve normal entity types without special characters", async () => {
      // Mock the search methods to return empty results
      jest.spyOn(memoryGraph as any, "_searchSourceNode").mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_searchDestinationNode")
        .mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_retrieveNodesFromData")
        .mockResolvedValue({
          alice: "Person",
          bob: "City",
        });
      jest
        .spyOn(memoryGraph as any, "_establishNodesRelationsFromData")
        .mockResolvedValue([
          {
            source: "alice",
            destination: "bob",
            relationship: "lives_in",
          },
        ]);
      jest.spyOn(memoryGraph as any, "_searchGraphDb").mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_getDeleteEntitiesFromSearchOutput")
        .mockResolvedValue([]);
      jest.spyOn(memoryGraph as any, "_deleteEntities").mockResolvedValue([]);

      const capturedQueries: string[] = [];
      mockRun.mockImplementation((cypher: string) => {
        capturedQueries.push(cypher);
        return Promise.resolve({
          records: [
            {
              get: (key: string) => {
                if (key === "source") return "alice";
                if (key === "relationship") return "lives_in";
                if (key === "target") return "bob";
                return null;
              },
            },
          ],
        });
      });

      await memoryGraph.add("Alice lives in Bob", { userId: "test-user" });

      // Verify that normal labels are preserved
      const allQueries = capturedQueries.join(" ");
      expect(allQueries).toContain("Person");
      expect(allQueries).toContain("City");
    });

    it("should handle entity types with multiple special characters", async () => {
      jest.spyOn(memoryGraph as any, "_searchSourceNode").mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_searchDestinationNode")
        .mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_retrieveNodesFromData")
        .mockResolvedValue({
          alice: "Entity@Type#123",
          bob: "Node-Name/Value",
        });
      jest
        .spyOn(memoryGraph as any, "_establishNodesRelationsFromData")
        .mockResolvedValue([
          {
            source: "alice",
            destination: "bob",
            relationship: "related_to",
          },
        ]);
      jest.spyOn(memoryGraph as any, "_searchGraphDb").mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_getDeleteEntitiesFromSearchOutput")
        .mockResolvedValue([]);
      jest.spyOn(memoryGraph as any, "_deleteEntities").mockResolvedValue([]);

      const capturedQueries: string[] = [];
      mockRun.mockImplementation((cypher: string) => {
        capturedQueries.push(cypher);
        return Promise.resolve({
          records: [
            {
              get: (key: string) => {
                if (key === "source") return "alice";
                if (key === "relationship") return "related_to";
                if (key === "target") return "bob";
                return null;
              },
            },
          ],
        });
      });

      await memoryGraph.add("Alice is related to Bob", { userId: "test-user" });

      const allQueries = capturedQueries.join(" ");
      // All special characters should be replaced with underscores
      expect(allQueries).toContain("Entity_Type_123");
      expect(allQueries).toContain("Node_Name_Value");
      expect(allQueries).not.toContain("Entity@Type#123");
      expect(allQueries).not.toContain("Node-Name/Value");
    });

    it("should handle edge case: entity type with only special characters", async () => {
      jest.spyOn(memoryGraph as any, "_searchSourceNode").mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_searchDestinationNode")
        .mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_retrieveNodesFromData")
        .mockResolvedValue({
          alice: "---",
          bob: "unknown",
        });
      jest
        .spyOn(memoryGraph as any, "_establishNodesRelationsFromData")
        .mockResolvedValue([
          {
            source: "alice",
            destination: "bob",
            relationship: "related_to",
          },
        ]);
      jest.spyOn(memoryGraph as any, "_searchGraphDb").mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_getDeleteEntitiesFromSearchOutput")
        .mockResolvedValue([]);
      jest.spyOn(memoryGraph as any, "_deleteEntities").mockResolvedValue([]);

      const capturedQueries: string[] = [];
      mockRun.mockImplementation((cypher: string) => {
        capturedQueries.push(cypher);
        return Promise.resolve({
          records: [
            {
              get: (key: string) => {
                if (key === "source") return "alice";
                if (key === "relationship") return "related_to";
                if (key === "target") return "bob";
                return null;
              },
            },
          ],
        });
      });

      await memoryGraph.add("Alice is related to Bob", { userId: "test-user" });

      const allQueries = capturedQueries.join(" ");
      // All special characters should be replaced with underscores
      expect(allQueries).toContain("___");
      expect(allQueries).toContain("unknown");
    });

    it("should handle unknown entity types correctly", async () => {
      jest.spyOn(memoryGraph as any, "_searchSourceNode").mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_searchDestinationNode")
        .mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_retrieveNodesFromData")
        .mockResolvedValue({
          alice: "Person",
          // bob is not in entityTypeMap, should default to "unknown"
        });
      jest
        .spyOn(memoryGraph as any, "_establishNodesRelationsFromData")
        .mockResolvedValue([
          {
            source: "alice",
            destination: "bob",
            relationship: "knows",
          },
        ]);
      jest.spyOn(memoryGraph as any, "_searchGraphDb").mockResolvedValue([]);
      jest
        .spyOn(memoryGraph as any, "_getDeleteEntitiesFromSearchOutput")
        .mockResolvedValue([]);
      jest.spyOn(memoryGraph as any, "_deleteEntities").mockResolvedValue([]);

      const capturedQueries: string[] = [];
      mockRun.mockImplementation((cypher: string) => {
        capturedQueries.push(cypher);
        return Promise.resolve({
          records: [
            {
              get: (key: string) => {
                if (key === "source") return "alice";
                if (key === "relationship") return "knows";
                if (key === "target") return "bob";
                return null;
              },
            },
          ],
        });
      });

      await memoryGraph.add("Alice knows Bob", { userId: "test-user" });

      const allQueries = capturedQueries.join(" ");
      // "unknown" should appear in the query (it's already a valid label)
      expect(allQueries).toContain("unknown");
      expect(allQueries).toContain("Person");
    });
  });
});
