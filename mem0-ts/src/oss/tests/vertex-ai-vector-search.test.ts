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

  it("should get vector by id", async () => {
    const result = await store.get("id1");
    expect((store as any).matchClient.findNeighbors).toHaveBeenCalled();
    expect(result).toBeNull();
  });
});
