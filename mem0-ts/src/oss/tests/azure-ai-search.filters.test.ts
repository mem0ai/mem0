import { AzureAISearch } from "../src/vector_stores/azure_ai_search";

const mockSearch = jest.fn();
const mockListIndexes = jest.fn();
const mockCreateOrUpdateIndex = jest.fn();

jest.mock("@azure/search-documents", () => ({
  SearchClient: jest.fn().mockImplementation(() => ({
    search: mockSearch,
    uploadDocuments: jest.fn().mockResolvedValue({ results: [] }),
    getDocument: jest.fn().mockResolvedValue(null),
    mergeOrUploadDocuments: jest.fn().mockResolvedValue({}),
    deleteDocuments: jest.fn().mockResolvedValue({}),
  })),
  SearchIndexClient: jest.fn().mockImplementation(() => ({
    listIndexes: mockListIndexes,
    createOrUpdateIndex: mockCreateOrUpdateIndex,
    deleteIndex: jest.fn().mockResolvedValue({}),
    getIndex: jest.fn().mockResolvedValue({ name: "test-index", fields: [] }),
  })),
  AzureKeyCredential: jest.fn().mockImplementation((key: string) => ({ key })),
}));

jest.mock("@azure/identity", () => ({
  DefaultAzureCredential: jest.fn(),
}));

function emptyAzureSearchResult() {
  return {
    results: {
      async *[Symbol.asyncIterator]() {
        // Empty result set.
      },
    },
  };
}

function createStore(): AzureAISearch {
  return new AzureAISearch({
    serviceName: "test-service",
    collectionName: "test-index",
    apiKey: "fake-key",
    embeddingModelDims: 4,
  });
}

describe("AzureAISearch filter expression handling", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockSearch.mockReturnValue(emptyAzureSearchResult());
    mockListIndexes.mockReturnValue({
      async *[Symbol.asyncIterator]() {
        // No existing indexes.
      },
    });
    mockCreateOrUpdateIndex.mockResolvedValue({});
  });

  test("search omits filter option for empty filters", async () => {
    const store = createStore();

    await store.search([0.1, 0.2, 0.3, 0.4], 5, {});

    const [, options] = mockSearch.mock.calls[0];
    expect(options).not.toHaveProperty("filter");
  });

  test("search rejects malformed filter containers instead of treating them as empty", async () => {
    const malformedFilters = [
      null,
      false,
      "",
      [],
      new Date("2026-01-01T00:00:00.000Z"),
    ];

    for (const filters of malformedFilters) {
      const store = createStore();
      mockSearch.mockClear();

      await expect(
        store.search([0.1, 0.2, 0.3, 0.4], 5, filters as any),
      ).rejects.toThrow("filters must be a plain object");

      expect(mockSearch).not.toHaveBeenCalled();
    }
  });

  test("search supports null-prototype filter dictionaries", async () => {
    const store = createStore();
    const filters = Object.create(null);
    filters.user_id = "user-1";

    await store.search([0.1, 0.2, 0.3, 0.4], 5, filters);

    const [, options] = mockSearch.mock.calls[0];
    expect(options).toEqual(
      expect.objectContaining({ filter: "user_id eq 'user-1'" }),
    );
  });

  test("hybrid search omits filter option for empty filters", async () => {
    const store = new AzureAISearch({
      serviceName: "test-service",
      collectionName: "test-index",
      apiKey: "fake-key",
      embeddingModelDims: 4,
      hybridSearch: true,
    });

    await store.search([0.1, 0.2, 0.3, 0.4], 5, {});

    const [, options] = mockSearch.mock.calls[0];
    expect(options).not.toHaveProperty("filter");
    expect(options).toEqual(
      expect.objectContaining({ top: 5, searchFields: ["payload"] }),
    );
  });

  test("keywordSearch omits filter option for empty filters", async () => {
    const store = createStore();

    await store.keywordSearch("coffee", 3, {});

    const [, options] = mockSearch.mock.calls[0];
    expect(options).not.toHaveProperty("filter");
    expect(options).toEqual(
      expect.objectContaining({ top: 3, searchFields: ["payload"] }),
    );
  });

  test("list omits filter option for empty filters", async () => {
    const store = createStore();

    await store.list({}, 10);

    const [, options] = mockSearch.mock.calls[0];
    expect(options).not.toHaveProperty("filter");
    expect(options).toEqual(expect.objectContaining({ top: 10 }));
  });

  test("search preserves valid filter expressions", async () => {
    const store = createStore();

    await store.search([0.1, 0.2, 0.3, 0.4], 5, {
      user_id: "o'hara",
      run_id: "run-1",
    });

    const [, options] = mockSearch.mock.calls[0];
    expect(options).toEqual(
      expect.objectContaining({
        filter: "user_id eq 'o''hara' and run_id eq 'run-1'",
        top: 5,
      }),
    );
  });

  test("list preserves valid filter expressions", async () => {
    const store = createStore();

    await store.list({ agent_id: "agent-1" }, 10);

    const [, options] = mockSearch.mock.calls[0];
    expect(options).toEqual(
      expect.objectContaining({
        filter: "agent_id eq 'agent-1'",
        top: 10,
      }),
    );
  });

  test("list rejects nullish filter values instead of broadening the read", async () => {
    const store = createStore();

    await expect(
      store.list({ user_id: null, agent_id: undefined } as any, 10),
    ).rejects.toThrow("must not be null or undefined");

    expect(mockSearch).not.toHaveBeenCalled();
  });

  test("keywordSearch rejects nullish filter values instead of returning null", async () => {
    const store = createStore();

    await expect(
      store.keywordSearch("coffee", 3, { run_id: null } as any),
    ).rejects.toThrow("must not be null or undefined");

    expect(mockSearch).not.toHaveBeenCalled();
  });

  test("keywordSearch preserves valid filter values and escapes strings", async () => {
    const store = createStore();

    await store.keywordSearch("coffee", 3, {
      user_id: "o'hara",
      agent_id: "agent-1",
    });

    expect(mockSearch).toHaveBeenCalledWith(
      "coffee",
      expect.objectContaining({
        filter: "user_id eq 'o''hara' and agent_id eq 'agent-1'",
        top: 3,
        searchFields: ["payload"],
      }),
    );
  });

  test("search rejects unsupported filter value shapes", async () => {
    const store = createStore();

    await expect(
      store.search([0.1, 0.2, 0.3, 0.4], 5, {
        user_id: { $ne: "u1" },
      } as any),
    ).rejects.toThrow("Unsupported Azure AI Search filter value");

    expect(mockSearch).not.toHaveBeenCalled();
  });

  test("search rejects non-string values for string filter fields", async () => {
    const store = createStore();

    await expect(
      store.search([0.1, 0.2, 0.3, 0.4], 5, {
        user_id: 123,
      } as any),
    ).rejects.toThrow("expected string");

    expect(mockSearch).not.toHaveBeenCalled();
  });

  test("search rejects unsupported filter keys", async () => {
    const store = createStore();

    await expect(
      store.search([0.1, 0.2, 0.3, 0.4], 5, {
        metadata: "private",
      } as any),
    ).rejects.toThrow("Unsupported Azure AI Search filter key");

    expect(mockSearch).not.toHaveBeenCalled();
  });

  test("search rejects id filters because id is not filterable in the Azure index", async () => {
    const store = createStore();

    await expect(
      store.search([0.1, 0.2, 0.3, 0.4], 5, {
        id: "memory-1",
      } as any),
    ).rejects.toThrow("Unsupported Azure AI Search filter key");

    expect(mockSearch).not.toHaveBeenCalled();
  });

  test("search rejects malformed keys instead of sanitizing them into supported fields", async () => {
    const store = createStore();

    await expect(
      store.search([0.1, 0.2, 0.3, 0.4], 5, {
        "user_id!": "u1",
      } as any),
    ).rejects.toThrow("Unsupported Azure AI Search filter key");

    expect(mockSearch).not.toHaveBeenCalled();
  });
});
