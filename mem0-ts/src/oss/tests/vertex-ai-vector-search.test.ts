/// <reference types="jest" />
import { VertexAIVectorSearch } from "../src/vector_stores/vertex_ai_vector_search";

jest.mock("@google-cloud/aiplatform", () => {
  const MatchServiceClient = jest.fn().mockImplementation(() => ({
    findNeighbors: jest.fn().mockResolvedValue([{ nearestNeighbors: [] }]),
  }));
  const IndexServiceClient = jest.fn().mockImplementation(() => ({
    upsertDatapoints: jest.fn().mockResolvedValue([{}]),
    removeDatapoints: jest.fn().mockResolvedValue([{}]),
  }));
  return {
    v1: {
      MatchServiceClient,
      IndexServiceClient,
    },
  };
});

describe("VertexAIVectorSearch", () => {
  let store: VertexAIVectorSearch;

  beforeEach(() => {
    store = new VertexAIVectorSearch({
      projectId: "test-project",
      projectNumber: "123456789",
      region: "us-central1",
      endpointId: "test-endpoint",
      indexId: "test-index",
      deploymentIndexId: "test-deployment",
      vectorSearchApiEndpoint: "test-api-endpoint",
    });
  });

  it("should initialize with correct collection name", () => {
    expect((store as any).config.collectionName).toBe("test-index");
  });

  it("should insert vectors", async () => {
    await store.insert([[1, 2, 3]], ["id1"], [{ key: "value" }]);
    expect((store as any).indexClient.upsertDatapoints).toHaveBeenCalled();
  });

  it("should search vectors", async () => {
    const results = await store.search([1, 2, 3], 5);
    expect((store as any).matchClient.findNeighbors).toHaveBeenCalled();
    expect(results).toEqual([]);
  });

  it("should search vectors and return populated results", async () => {
    const mockFindNeighbors = jest.fn().mockResolvedValue([{
      nearestNeighbors: [{
        neighbors: [{
          datapoint: {
            datapointId: "id1",
            restricts: [{ namespace: "key", allowList: ["value"] }]
          },
          distance: 0.1
        }]
      }]
    }]);
    (store as any).matchClient.findNeighbors = mockFindNeighbors;
    
    const results = await store.search([1, 2, 3], 5, { key: "value" });
    
    expect(mockFindNeighbors).toHaveBeenCalled();
    // It should map payload correctly and score should be 1.0 - distance
    expect(results).toEqual([
      {
        id: "id1",
        payload: { key: "value" },
        score: 0.9,
      }
    ]);
  });

  it("should get vector by id", async () => {
    const result = await store.get("id1");
    expect((store as any).matchClient.findNeighbors).toHaveBeenCalled();
    expect(result).toBeNull();
  });
});
