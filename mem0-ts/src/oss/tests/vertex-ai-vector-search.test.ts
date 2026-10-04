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
    const mockFindNeighbors = jest.fn().mockResolvedValue([
      {
        nearestNeighbors: [
          {
            neighbors: [
              {
                datapoint: {
                  datapointId: "id1",
                  restricts: [{ namespace: "key", allowList: ["value"] }],
                },
                distance: 0.1,
              },
            ],
          },
        ],
      },
    ]);
    (store as any).matchClient.findNeighbors = mockFindNeighbors;

    const results = await store.search([1, 2, 3], 5, { key: "value" });

    expect(mockFindNeighbors).toHaveBeenCalled();
    // It should map payload correctly and score should be 1.0 - distance
    expect(results).toEqual([
      {
        id: "id1",
        payload: { key: "value" },
        score: 0.9,
      },
    ]);
  });

  it("should get vector by id", async () => {
    const result = await store.get("id1");
    expect((store as any).matchClient.findNeighbors).toHaveBeenCalled();
    expect(result).toBeNull();
  });

  it("should build allowList/denyList restricts from include/exclude filters", async () => {
    const spy = jest.fn().mockResolvedValue([{ nearestNeighbors: [] }]);
    (store as any).matchClient.findNeighbors = spy;

    await store.search([1, 2, 3], 5, {
      key: { include: ["a"], exclude: ["b"] },
    });

    const request = spy.mock.calls[0][0];
    expect(request.queries[0].datapoint.restricts).toEqual([
      { namespace: "key", allowList: ["a"], denyList: ["b"] },
    ]);
  });

  it("should exclude the mem0-user-id-record sentinel from search results", async () => {
    (store as any).matchClient.findNeighbors = jest.fn().mockResolvedValue([
      {
        nearestNeighbors: [
          {
            neighbors: [
              {
                datapoint: { datapointId: "mem0-user-id-record" },
                distance: 0.0,
              },
              { datapoint: { datapointId: "id1" }, distance: 0.1 },
            ],
          },
        ],
      },
    ]);

    const results = await store.search([1, 2, 3], 5);
    expect(results.map((r) => r.id)).toEqual(["id1"]);
  });

  it("should update an existing vector", async () => {
    (store as any).matchClient.findNeighbors = jest.fn().mockResolvedValue([
      {
        nearestNeighbors: [
          {
            neighbors: [{ datapoint: { datapointId: "id1" }, distance: 0.1 }],
          },
        ],
      },
    ]);

    await store.update("id1", [4, 5, 6], { key: "new" });
    expect((store as any).indexClient.upsertDatapoints).toHaveBeenCalled();
  });

  it("should skip update when the vector does not exist", async () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});

    // default findNeighbors returns empty → get() resolves null
    await store.update("missing", [4, 5, 6], { key: "new" });

    expect((store as any).indexClient.upsertDatapoints).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
  });

  it("should delete a vector by id", async () => {
    await store.delete("id1");
    expect((store as any).indexClient.removeDatapoints).toHaveBeenCalledWith({
      index: expect.any(String),
      datapointIds: ["id1"],
    });
  });

  it("should ignore NOT_FOUND (gRPC code 5) on delete", async () => {
    (store as any).indexClient.removeDatapoints = jest
      .fn()
      .mockRejectedValue({ code: 5 });
    await expect(store.delete("missing")).resolves.toBeUndefined();
  });

  it("should rethrow non-NOT_FOUND errors on delete", async () => {
    (store as any).indexClient.removeDatapoints = jest
      .fn()
      .mockRejectedValue({ code: 13 });
    await expect(store.delete("id1")).rejects.toEqual({ code: 13 });
  });

  it("should list vectors via a zero-vector search", async () => {
    (store as any).matchClient.findNeighbors = jest.fn().mockResolvedValue([
      {
        nearestNeighbors: [
          {
            neighbors: [{ datapoint: { datapointId: "id1" }, distance: 0.2 }],
          },
        ],
      },
    ]);

    const [results, count] = await store.list();
    expect((store as any).matchClient.findNeighbors).toHaveBeenCalled();
    expect(count).toBe(1);
    expect(results[0].id).toBe("id1");
  });

  it("should return null for keywordSearch (unsupported)", async () => {
    await expect(store.keywordSearch("hello")).resolves.toBeNull();
  });

  it("should warn and no-op on deleteCol (unsupported)", async () => {
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    await store.deleteCol();
    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
  });

  it("should set a user id via the sentinel datapoint", async () => {
    await store.setUserId("user-123");

    expect((store as any).indexClient.upsertDatapoints).toHaveBeenCalled();
    const request = (store as any).indexClient.upsertDatapoints.mock
      .calls[0][0];
    expect(request.datapoints[0].datapointId).toBe("mem0-user-id-record");
  });

  it("should return an existing user id from the sentinel record", async () => {
    (store as any).matchClient.findNeighbors = jest.fn().mockResolvedValue([
      {
        nearestNeighbors: [
          {
            neighbors: [
              {
                datapoint: {
                  datapointId: "mem0-user-id-record",
                  restricts: [
                    { namespace: "user_id", allowList: ["existing-user"] },
                  ],
                },
                distance: 0.0,
              },
            ],
          },
        ],
      },
    ]);

    const userId = await store.getUserId();
    expect(userId).toBe("existing-user");
  });

  it("should generate and persist a new user id when none exists", async () => {
    // default findNeighbors empty → get() null → generate + setUserId
    const userId = await store.getUserId();

    expect(typeof userId).toBe("string");
    expect(userId.length).toBeGreaterThan(0);
    expect((store as any).indexClient.upsertDatapoints).toHaveBeenCalled();
  });
});
