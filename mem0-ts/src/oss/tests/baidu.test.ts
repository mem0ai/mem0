import { BaiduDB } from "../src/vector_stores/baidu";

type MockBaiduSdkState = {
  clientInstance: any;
  lastConfiguration: any;
  lastCredentials: any;
  lastClientConfig: any;
};

function getMockBaiduSdkState(): MockBaiduSdkState {
  const globalState = globalThis as typeof globalThis & {
    __mockBaiduSdkState?: MockBaiduSdkState;
  };

  if (!globalState.__mockBaiduSdkState) {
    globalState.__mockBaiduSdkState = {
      clientInstance: null,
      lastConfiguration: null,
      lastCredentials: null,
      lastClientConfig: null,
    };
  }

  return globalState.__mockBaiduSdkState;
}

jest.mock("@baiducloud/sdk", () => {
  const state = getMockBaiduSdkState();

  return {
    __esModule: true,
    configuration: jest.fn().mockImplementation(function Configuration(
      this: any,
      options: any,
    ) {
      state.lastConfiguration = options;
      this.options = options;
    }),
    bceCredentials: jest.fn().mockImplementation(function BceCredentials(
      this: any,
      account: string,
      apiKey: string,
    ) {
      state.lastCredentials = { account, apiKey };
      this.account = account;
      this.apiKey = apiKey;
    }),
    mochowClient: jest.fn().mockImplementation(function MochowClient(
      this: any,
      config: any,
    ) {
      state.lastClientConfig = config;
      return state.clientInstance;
    }),
  };
});

type MockClientOptions = {
  methodStyle?: "camelCase" | "snake_case";
  createDatabaseExists?: boolean;
  createTableExists?: boolean;
  keywordSearchFails?: boolean;
};

function createMockClient(options: MockClientOptions = {}): any {
  const methodStyle = options.methodStyle || "camelCase";
  const state = {
    databaseCreated: false,
    tableCreated: false,
  };

  const createAlreadyExistsError = () => {
    const err = new Error("Collection already exists") as Error & {
      code?: number;
      status?: number;
    };
    err.code = 409;
    err.status = 409;
    return err;
  };

  const createResultRow = (id: string, data: string, userId: string) => ({
    id,
    metadata: { data, user_id: userId },
  });

  const mockTable = {
    ...(methodStyle === "snake_case"
      ? {
          upsert: jest.fn().mockResolvedValue(undefined),
          query: jest.fn().mockResolvedValue({
            data: [createResultRow("id-1", "alpha", "u1")],
          }),
          vector_search: jest.fn().mockResolvedValue({
            points: [
              {
                row: createResultRow("id-1", "alpha", "u1"),
                score: 0.91,
              },
              {
                row: createResultRow("id-2", "beta", "u2"),
                score: 0.72,
              },
            ],
          }),
          bm25_search: options.keywordSearchFails
            ? jest.fn().mockRejectedValue(new Error("bm25 unavailable"))
            : jest.fn().mockResolvedValue({
                items: [
                  {
                    row: createResultRow("id-1", "alpha", "u1"),
                    score: 0.55,
                  },
                ],
              }),
          select: jest.fn().mockResolvedValue({
            data: [
              createResultRow("id-1", "alpha", "u1"),
              createResultRow("id-2", "beta", "u2"),
            ],
            total: 2,
          }),
          delete: jest.fn().mockResolvedValue(undefined),
          stats: jest.fn().mockReturnValue({ tableName: "memories" }),
        }
      : {
          upsert: jest.fn().mockResolvedValue(undefined),
          query: jest.fn().mockResolvedValue({
            row: createResultRow("id-1", "alpha", "u1"),
          }),
          vectorSearch: jest.fn().mockResolvedValue({
            rows: [
              {
                row: createResultRow("id-1", "alpha", "u1"),
                score: 0.91,
              },
              {
                row: createResultRow("id-2", "beta", "u2"),
                score: 0.72,
              },
            ],
          }),
          bm25Search: options.keywordSearchFails
            ? jest.fn().mockRejectedValue(new Error("bm25 unavailable"))
            : jest.fn().mockResolvedValue({
                rows: [
                  {
                    row: createResultRow("id-1", "alpha", "u1"),
                    score: 0.55,
                  },
                ],
              }),
          select: jest.fn().mockResolvedValue({
            rows: [
              createResultRow("id-1", "alpha", "u1"),
              createResultRow("id-2", "beta", "u2"),
            ],
            total: 2,
          }),
          delete: jest.fn().mockResolvedValue(undefined),
          stats: jest.fn().mockReturnValue({ tableName: "memories" }),
        }),
  };

  const mockDatabase = {
    ...(methodStyle === "snake_case"
      ? {
          create_table: jest.fn().mockImplementation(async () => {
            if (options.createTableExists && !state.tableCreated) {
              state.tableCreated = true;
              throw createAlreadyExistsError();
            }

            state.tableCreated = true;
            return mockTable;
          }),
          describe_table: jest.fn().mockResolvedValue(mockTable),
          table: jest.fn().mockReturnValue(mockTable),
          drop_table: jest.fn().mockResolvedValue(undefined),
        }
      : {
          createTable: jest.fn().mockImplementation(async () => {
            if (options.createTableExists && !state.tableCreated) {
              state.tableCreated = true;
              throw createAlreadyExistsError();
            }

            state.tableCreated = true;
            return mockTable;
          }),
          describeTable: jest.fn().mockResolvedValue(mockTable),
          table: jest.fn().mockReturnValue(mockTable),
          dropTable: jest.fn().mockResolvedValue(undefined),
        }),
  };

  const mockClient = {
    ...(methodStyle === "snake_case"
      ? {
          create_database: jest.fn().mockImplementation(async () => {
            if (options.createDatabaseExists && !state.databaseCreated) {
              state.databaseCreated = true;
              throw createAlreadyExistsError();
            }

            state.databaseCreated = true;
            return mockDatabase;
          }),
          database: jest.fn().mockReturnValue(mockDatabase),
        }
      : {
          createDatabase: jest.fn().mockImplementation(async () => {
            if (options.createDatabaseExists && !state.databaseCreated) {
              state.databaseCreated = true;
              throw createAlreadyExistsError();
            }

            state.databaseCreated = true;
            return mockDatabase;
          }),
          database: jest.fn().mockReturnValue(mockDatabase),
        }),
  };

  return { mockClient, mockDatabase, mockTable };
}

describe("BaiduDB", () => {
  const baseConfig = {
    endpoint: "http://localhost:8287",
    account: "root",
    apiKey: "test-key",
    databaseName: "mem0",
    tableName: "memories",
    embeddingModelDims: 4,
    metricType: "COSINE",
  };

  beforeEach(() => {
    const state = getMockBaiduSdkState();
    state.clientInstance = null;
    state.lastConfiguration = null;
    state.lastCredentials = null;
    state.lastClientConfig = null;
    jest.clearAllMocks();
  });

  test("implements the VectorStore contract and reset helper", () => {
    const { mockClient } = createMockClient();
    const store = new BaiduDB({ ...baseConfig, client: mockClient });

    expect(typeof store.insert).toBe("function");
    expect(typeof store.search).toBe("function");
    expect(typeof store.get).toBe("function");
    expect(typeof store.update).toBe("function");
    expect(typeof store.delete).toBe("function");
    expect(typeof store.deleteCol).toBe("function");
    expect(typeof store.list).toBe("function");
    expect(typeof store.getUserId).toBe("function");
    expect(typeof store.setUserId).toBe("function");
    expect(typeof store.initialize).toBe("function");
    expect(typeof store.reset).toBe("function");
  });

  test("still validates required config even when a client is injected", () => {
    const { mockClient } = createMockClient();

    expect(
      () =>
        new BaiduDB({
          ...baseConfig,
          tableName: "",
          client: mockClient,
        } as any),
    ).toThrow(
      "Baidu vector store requires a non-empty 'tableName' config value.",
    );
  });

  test("loads the SDK using lower-case export aliases when no client is injected", async () => {
    const state = getMockBaiduSdkState();
    state.clientInstance = createMockClient({
      methodStyle: "snake_case",
    }).mockClient;

    const store = new BaiduDB({
      ...baseConfig,
    });

    await store.initialize();

    expect(state.lastCredentials).toEqual({
      account: "root",
      apiKey: "test-key",
    });
    expect(state.lastConfiguration).toEqual(
      expect.objectContaining({
        endpoint: "http://localhost:8287",
        credentials: expect.objectContaining({
          account: "root",
          apiKey: "test-key",
        }),
      }),
    );
    expect(state.lastClientConfig).toEqual(expect.anything());
  });

  test("initialize() is idempotent and creates the database/table once", async () => {
    const { mockClient, mockDatabase, mockTable } = createMockClient();
    const store = new BaiduDB({ ...baseConfig, client: mockClient });

    await Promise.all([
      store.initialize(),
      store.initialize(),
      store.initialize(),
    ]);

    expect(mockClient.createDatabase).toHaveBeenCalledTimes(1);
    expect(mockDatabase.createTable).toHaveBeenCalledTimes(1);
    expect(mockDatabase.createTable).toHaveBeenCalledWith(
      expect.objectContaining({
        schema: expect.objectContaining({
          fields: expect.arrayContaining([
            expect.objectContaining({
              name: "vector",
              type: "FLOAT_VECTOR",
            }),
            expect.objectContaining({ name: "data", type: "TEXT" }),
            expect.objectContaining({
              name: "textLemmatized",
              type: "TEXT",
            }),
            expect.objectContaining({ name: "metadata", type: "JSON" }),
          ]),
          indexes: expect.arrayContaining([
            expect.objectContaining({
              indexName: "vector_idx",
              indexType: "HNSW",
              field: "vector",
              metricType: "COSINE",
            }),
            expect.objectContaining({
              indexName: "metadata_filtering_idx",
              fields: ["metadata"],
            }),
            expect.objectContaining({
              indexName: "data_bm25_idx",
              indexType: "INVERTED",
              fields: ["data", "textLemmatized"],
            }),
          ]),
        }),
      }),
    );
    expect(mockDatabase.describeTable).not.toHaveBeenCalled();
    expect(mockTable.stats).toHaveBeenCalledTimes(1);
  });

  test("falls back to existing database and table on already-exists errors", async () => {
    const { mockClient, mockDatabase, mockTable } = createMockClient({
      createDatabaseExists: true,
      createTableExists: true,
    });
    const store = new BaiduDB({ ...baseConfig, client: mockClient });

    await store.initialize();

    expect(mockClient.createDatabase).toHaveBeenCalledTimes(1);
    expect(mockClient.database).toHaveBeenCalledTimes(1);
    expect(mockDatabase.createTable).toHaveBeenCalledTimes(1);
    expect(mockDatabase.describeTable).toHaveBeenCalledTimes(1);
    expect(mockTable.stats).toHaveBeenCalledTimes(1);
  });

  test("supports the full CRUD lifecycle and reset", async () => {
    const { mockClient, mockDatabase, mockTable } = createMockClient();
    const store = new BaiduDB({ ...baseConfig, client: mockClient });
    await store.initialize();

    await store.insert(
      [
        [0.1, 0.2, 0.3, 0.4],
        [0.4, 0.3, 0.2, 0.1],
      ],
      ["id-1", "id-2"],
      [
        { data: "alpha", user_id: "u1" },
        { data: "beta", user_id: "u2" },
      ],
    );

    expect(mockTable.upsert).toHaveBeenCalledTimes(2);
    expect(mockTable.upsert).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({
        rows: [
          expect.objectContaining({
            id: "id-1",
            vector: [0.1, 0.2, 0.3, 0.4],
            data: "alpha",
            textLemmatized: "alpha",
            metadata: { data: "alpha", user_id: "u1" },
          }),
        ],
      }),
    );
    expect(mockTable.upsert).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        rows: [
          expect.objectContaining({
            id: "id-2",
            vector: [0.4, 0.3, 0.2, 0.1],
            data: "beta",
            textLemmatized: "beta",
            metadata: { data: "beta", user_id: "u2" },
          }),
        ],
      }),
    );

    const searchResults = await store.search([0.1, 0.2, 0.3, 0.4], 2, {
      user_id: 'alice\\path"beta',
      active: true,
      score: 7,
    });
    expect(mockTable.vectorSearch).toHaveBeenCalledWith(
      expect.objectContaining({
        filter:
          'metadata["user_id"] = "alice\\\\path\\"beta" AND metadata["active"] = true AND metadata["score"] = 7',
      }),
    );
    expect(searchResults).toEqual([
      { id: "id-1", payload: { data: "alpha", user_id: "u1" }, score: 0.91 },
      { id: "id-2", payload: { data: "beta", user_id: "u2" }, score: 0.72 },
    ]);

    const keywordResults = await store.keywordSearch("alpha", 1, {
      user_id: "u1",
    });
    expect(keywordResults).toEqual([
      { id: "id-1", payload: { data: "alpha", user_id: "u1" }, score: 0.55 },
    ]);

    const item = await store.get("id-1");
    expect(item).toEqual({
      id: "id-1",
      payload: { data: "alpha", user_id: "u1" },
    });

    await store.update("id-1", [1, 1, 1, 1], { data: "updated" });
    expect(mockTable.upsert).toHaveBeenCalledTimes(3);
    expect(mockTable.upsert).toHaveBeenNthCalledWith(
      3,
      expect.objectContaining({
        rows: [
          expect.objectContaining({
            id: "id-1",
            vector: [1, 1, 1, 1],
            data: "updated",
            textLemmatized: "updated",
            metadata: { data: "updated" },
          }),
        ],
      }),
    );

    const [listed, count] = await store.list({ user_id: "u1" }, 10);
    expect(mockTable.select).toHaveBeenCalledWith(
      expect.objectContaining({
        filter: 'metadata["user_id"] = "u1"',
        limit: 10,
      }),
    );
    expect(listed).toEqual([
      { id: "id-1", payload: { data: "alpha", user_id: "u1" } },
      { id: "id-2", payload: { data: "beta", user_id: "u2" } },
    ]);
    expect(count).toBe(2);

    await store.delete("id-2");
    expect(mockTable.delete).toHaveBeenCalledWith({
      primaryKey: { id: "id-2" },
      primary_key: { id: "id-2" },
    });

    await store.reset();
    expect(mockDatabase.dropTable).toHaveBeenCalledWith("memories");
    expect(mockDatabase.createTable).toHaveBeenCalledTimes(2);
  });

  test("supports snake_case SDK methods and alternate response envelopes", async () => {
    const { mockClient, mockDatabase, mockTable } = createMockClient({
      methodStyle: "snake_case",
    });

    const store = new BaiduDB({
      ...baseConfig,
      client: mockClient,
    });

    await store.initialize();

    const searchResults = await store.search([0.1, 0.2, 0.3, 0.4], 2, {
      user_id: "u1",
    });
    expect(mockTable.vector_search).toHaveBeenCalledWith(
      expect.objectContaining({
        vector_field: "vector",
        vector: [0.1, 0.2, 0.3, 0.4],
        filter: 'metadata["user_id"] = "u1"',
      }),
    );
    expect(searchResults).toEqual([
      { id: "id-1", payload: { data: "alpha", user_id: "u1" }, score: 0.91 },
      { id: "id-2", payload: { data: "beta", user_id: "u2" }, score: 0.72 },
    ]);

    const keywordResults = await store.keywordSearch("alpha", 1, {
      user_id: "u1",
    });
    expect(mockTable.bm25_search).toHaveBeenCalledWith(
      expect.objectContaining({
        search_text: "alpha",
        limit: 1,
        filter: 'metadata["user_id"] = "u1"',
      }),
    );
    expect(keywordResults).toEqual([
      { id: "id-1", payload: { data: "alpha", user_id: "u1" }, score: 0.55 },
    ]);

    const item = await store.get("id-1");
    expect(item).toEqual({
      id: "id-1",
      payload: { data: "alpha", user_id: "u1" },
    });

    const [listed, count] = await store.list({ user_id: "u1" }, 10);
    expect(mockTable.select).toHaveBeenCalledWith(
      expect.objectContaining({
        filter: 'metadata["user_id"] = "u1"',
        limit: 10,
      }),
    );
    expect(listed).toEqual([
      { id: "id-1", payload: { data: "alpha", user_id: "u1" } },
      { id: "id-2", payload: { data: "beta", user_id: "u2" } },
    ]);
    expect(count).toBe(2);

    await store.delete("id-2");
    expect(mockTable.delete).toHaveBeenCalledWith({
      primaryKey: { id: "id-2" },
      primary_key: { id: "id-2" },
    });

    await store.reset();
    expect(mockDatabase.drop_table).toHaveBeenCalledWith("memories");
    expect(mockDatabase.create_table).toHaveBeenCalledTimes(2);
  });

  test("rejects unsafe filter keys and non-primitive values", async () => {
    const { mockClient } = createMockClient();
    const store = new BaiduDB({ ...baseConfig, client: mockClient });
    await store.initialize();

    await expect(
      store.search([0.1, 0.2, 0.3, 0.4], 2, {
        '"] = "") or true or ("': "x",
      } as any),
    ).rejects.toThrow("Invalid filter key");

    await expect(
      store.search([0.1, 0.2, 0.3, 0.4], 2, {
        user_id: { $ne: "x" } as any,
      }),
    ).rejects.toThrow("must be str, int, float, or bool");
  });

  test("returns null and warns when keyword search fails", async () => {
    const { mockClient } = createMockClient({ keywordSearchFails: true });
    const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
    const store = new BaiduDB({ ...baseConfig, client: mockClient });

    await store.initialize();

    await expect(store.keywordSearch("alpha", 1)).resolves.toBeNull();
    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("Baidu keyword search failed"),
      expect.any(Error),
    );

    warnSpy.mockRestore();
  });

  test("tracks user IDs in memory for the OSS contract", async () => {
    const { mockClient } = createMockClient();
    const store = new BaiduDB({ ...baseConfig, client: mockClient });
    await store.initialize();

    expect(await store.getUserId()).toBe("anonymous-baidu-user");
    await store.setUserId("custom-user");
    expect(await store.getUserId()).toBe("custom-user");
  });
});
