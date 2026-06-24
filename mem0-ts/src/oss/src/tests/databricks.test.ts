/**
 * Unit tests for the Databricks vector store.
 *
 * All Databricks REST API calls are mocked via global.fetch so no real
 * workspace is needed.
 */

import { DatabricksVectorStore } from "../vector_stores/databricks";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a mock fetch that routes by URL pattern. */
function mockFetch(handlers: Record<string, (url: string, init?: any) => any>) {
  return jest.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const urlStr = typeof url === "string" ? url : url.toString();
    for (const [pattern, handler] of Object.entries(handlers)) {
      if (urlStr.includes(pattern)) {
        const body = handler(urlStr, init);
        return {
          ok: true,
          status: 200,
          text: async () => (body != null ? JSON.stringify(body) : ""),
          json: async () => body,
        };
      }
    }
    return {
      ok: true,
      status: 200,
      text: async () => "{}",
      json: async () => ({}),
    };
  });
}

/** Build a mock fetch where specific patterns return errors. */
function mockFetchWithErrors(
  handlers: Record<string, (url: string, init?: any) => any>,
  errorPatterns: Record<string, { status: number; body: string }>,
) {
  return jest.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const urlStr = typeof url === "string" ? url : url.toString();

    // Check error patterns first
    for (const [pattern, error] of Object.entries(errorPatterns)) {
      if (urlStr.includes(pattern)) {
        return {
          ok: false,
          status: error.status,
          text: async () => error.body,
          json: async () => JSON.parse(error.body),
        };
      }
    }

    for (const [pattern, handler] of Object.entries(handlers)) {
      if (urlStr.includes(pattern)) {
        const body = handler(urlStr, init);
        return {
          ok: true,
          status: 200,
          text: async () => (body != null ? JSON.stringify(body) : ""),
          json: async () => body,
        };
      }
    }
    return {
      ok: true,
      status: 200,
      text: async () => "{}",
      json: async () => ({}),
    };
  });
}

const BASE_CONFIG = {
  workspaceUrl: "https://test.databricks.com",
  accessToken: "test-token",
  endpointName: "test-endpoint",
  catalog: "test_catalog",
  schema: "test_schema",
  tableName: "test_table",
  collectionName: "test_index",
  embeddingDimension: 4,
  indexType: "DIRECT_ACCESS" as const,
};

const DEFAULT_HANDLERS: Record<string, (url: string, init?: any) => any> = {
  "/api/2.0/sql/warehouses": () => ({
    warehouses: [{ id: "wh-123", name: "default" }],
  }),
  "/api/2.0/vector-search/endpoints/test-endpoint": () => ({
    name: "test-endpoint",
  }),
  "/api/2.0/vector-search/indexes?": () => ({
    vector_indexes: [{ name: "test_catalog.test_schema.test_index" }],
  }),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DatabricksVectorStore", () => {
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    originalFetch = global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  function createStore(
    extraHandlers: Record<string, (url: string, init?: any) => any> = {},
    configOverrides: Record<string, any> = {},
  ) {
    const handlers = { ...DEFAULT_HANDLERS, ...extraHandlers };
    global.fetch = mockFetch(handlers) as any;
    return new DatabricksVectorStore({ ...BASE_CONFIG, ...configOverrides });
  }

  // -------------------------------------------------------------------------
  // Initialization
  // -------------------------------------------------------------------------

  it("should construct with required config", () => {
    const store = createStore();
    expect(store).toBeInstanceOf(DatabricksVectorStore);
  });

  it("should initialize and resolve warehouse", async () => {
    const store = createStore();
    await store.initialize();
    expect(global.fetch).toHaveBeenCalled();
  });

  it("should resolve warehouse by name when warehouseName is provided", async () => {
    const store = createStore(
      {
        "/api/2.0/sql/warehouses": () => ({
          warehouses: [
            { id: "wh-wrong", name: "other" },
            { id: "wh-correct", name: "my-warehouse" },
          ],
        }),
      },
      { warehouseName: "my-warehouse" },
    );
    await store.initialize();

    // Verify it uses the correct warehouse by making a SQL call
    const sqlCalls: any[] = [];
    const currentFetch = global.fetch as jest.Mock;
    currentFetch.mockImplementation(async (url: string, init?: any) => {
      const urlStr = typeof url === "string" ? url : url.toString();
      if (urlStr.includes("/api/2.0/sql/statements")) {
        sqlCalls.push(JSON.parse(init.body));
        return {
          ok: true,
          status: 200,
          text: async () =>
            JSON.stringify({ status: { state: "SUCCEEDED" } }),
        };
      }
      return { ok: true, status: 200, text: async () => "{}" };
    });

    await store.delete("test-id");
    expect(sqlCalls[0].warehouse_id).toBe("wh-correct");
  });

  it("should throw when warehouseName does not match any warehouse", async () => {
    const store = createStore(
      {
        "/api/2.0/sql/warehouses": () => ({
          warehouses: [{ id: "wh-1", name: "other" }],
        }),
      },
      { warehouseName: "nonexistent" },
    );

    await expect(store.initialize()).rejects.toThrow(
      /No warehouse named 'nonexistent' found/,
    );
  });

  it("should throw when no warehouses exist in workspace", async () => {
    const store = createStore({
      "/api/2.0/sql/warehouses": () => ({ warehouses: [] }),
    });

    await expect(store.initialize()).rejects.toThrow(
      /No warehouses found in workspace/,
    );
  });

  // -------------------------------------------------------------------------
  // Insert
  // -------------------------------------------------------------------------

  it("should insert vectors via SQL statement API", async () => {
    const sqlCalls: any[] = [];
    const store = createStore({
      "/api/2.0/sql/statements": (_url: string, init: any) => {
        sqlCalls.push(JSON.parse(init.body));
        return { status: { state: "SUCCEEDED" } };
      },
    });
    await store.initialize();

    await store.insert(
      [[1, 2, 3, 4]],
      ["id-1"],
      [{ data: "hello world", user_id: "u1" }],
    );

    const insertCall = sqlCalls.find((c) => c.statement?.includes("INSERT"));
    expect(insertCall).toBeDefined();
    expect(insertCall.statement).toContain(
      "test_catalog.test_schema.test_table",
    );
  });

  // -------------------------------------------------------------------------
  // Search
  // -------------------------------------------------------------------------

  it("should search using vector search index query", async () => {
    const store = createStore({
      "/query": () => ({
        manifest: {
          columns: [
            { name: "memory_id" },
            { name: "memory" },
            { name: "score" },
          ],
        },
        result: {
          data_array: [["id-1", "hello world", 0.95]],
        },
      }),
    });
    await store.initialize();

    const results = await store.search([1, 2, 3, 4], 5);
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe("id-1");
    expect(results[0].score).toBe(0.95);
  });

  it("should pass filters to search", async () => {
    let capturedBody: any;
    const store = createStore({
      "/query": (_url: string, init: any) => {
        capturedBody = JSON.parse(init.body);
        return {
          manifest: { columns: [{ name: "memory_id" }] },
          result: { data_array: [] },
        };
      },
    });
    await store.initialize();

    await store.search([1, 2, 3, 4], 5, { user_id: "u1" });
    expect(capturedBody.filters_json).toBe(
      JSON.stringify({ user_id: "u1" }),
    );
  });

  it("should throw on search when DELTA_SYNC + model endpoint is configured", async () => {
    const store = createStore({}, {
      indexType: "DELTA_SYNC",
      embeddingModelEndpointName: "my-embedding-model",
    });
    await store.initialize();

    await expect(store.search([1, 2, 3, 4], 5)).rejects.toThrow(
      /embeddingModelEndpointName require query text/,
    );
  });

  it("should throw on search when no vector is provided", async () => {
    const store = createStore();
    await store.initialize();

    await expect(store.search([], 5)).rejects.toThrow(
      /Must provide query vector/,
    );
  });

  // -------------------------------------------------------------------------
  // Get
  // -------------------------------------------------------------------------

  it("should return null for get when not found", async () => {
    const store = createStore({
      "/query": () => ({
        result: { data_array: [] },
      }),
    });
    await store.initialize();

    const result = await store.get("nonexistent");
    expect(result).toBeNull();
  });

  it("should get a vector by ID", async () => {
    const store = createStore({
      "/query": () => ({
        manifest: {
          columns: [
            { name: "memory_id" },
            { name: "hash" },
            { name: "memory" },
            { name: "created_at" },
            { name: "updated_at" },
            { name: "metadata" },
          ],
        },
        result: {
          data_array: [
            [
              "id-1",
              "abc",
              "test memory",
              "2024-01-01",
              "2024-01-02",
              null,
            ],
          ],
        },
      }),
    });
    await store.initialize();

    const result = await store.get("id-1");
    expect(result).not.toBeNull();
    expect(result!.id).toBe("id-1");
    expect(result!.payload.data).toBe("test memory");
    expect(result!.payload.hash).toBe("abc");
  });

  // -------------------------------------------------------------------------
  // Update
  // -------------------------------------------------------------------------

  it("should update a vector via SQL", async () => {
    const sqlCalls: any[] = [];
    const store = createStore({
      "/api/2.0/sql/statements": (_url: string, init: any) => {
        sqlCalls.push(JSON.parse(init.body));
        return { status: { state: "SUCCEEDED" } };
      },
    });
    await store.initialize();

    await store.update("id-1", [5, 6, 7, 8], { custom_field: "value" });

    const updateCall = sqlCalls.find((c) => c.statement?.includes("UPDATE"));
    expect(updateCall).toBeDefined();
    expect(updateCall.statement).toContain("embedding");
    expect(updateCall.statement).toContain("custom_field");
  });

  it("should skip excluded keys on update", async () => {
    const sqlCalls: any[] = [];
    const store = createStore({
      "/api/2.0/sql/statements": (_url: string, init: any) => {
        sqlCalls.push(JSON.parse(init.body));
        return { status: { state: "SUCCEEDED" } };
      },
    });
    await store.initialize();

    await store.update("id-1", [1, 2, 3, 4], {
      user_id: "should-skip",
      hash: "should-skip",
      custom: "should-include",
    });

    const updateCall = sqlCalls.find((c) => c.statement?.includes("UPDATE"));
    expect(updateCall.statement).not.toContain("user_id");
    expect(updateCall.statement).not.toContain("hash =");
    expect(updateCall.statement).toContain("custom");
  });

  it("should skip keys that are not valid SQL identifiers on update", async () => {
    const sqlCalls: any[] = [];
    const store = createStore({
      "/api/2.0/sql/statements": (_url: string, init: any) => {
        sqlCalls.push(JSON.parse(init.body));
        return { status: { state: "SUCCEEDED" } };
      },
    });
    await store.initialize();

    await store.update("id-1", [1, 2, 3, 4], {
      "valid_key": "ok",
      "invalid-key": "skip",
      "123start": "skip",
    });

    const updateCall = sqlCalls.find((c) => c.statement?.includes("UPDATE"));
    expect(updateCall.statement).toContain("valid_key");
    expect(updateCall.statement).not.toContain("invalid-key");
    expect(updateCall.statement).not.toContain("123start");
  });

  it("should no-op when update has nothing to set", async () => {
    const sqlCalls: any[] = [];
    const store = createStore({
      "/api/2.0/sql/statements": (_url: string, init: any) => {
        sqlCalls.push(JSON.parse(init.body));
        return { status: { state: "SUCCEEDED" } };
      },
    });
    await store.initialize();

    // All keys are excluded, no vector — nothing to update
    await store.update("id-1", null as any, {
      user_id: "excluded",
      hash: "excluded",
    });

    const updateCall = sqlCalls.find((c) => c.statement?.includes("UPDATE"));
    expect(updateCall).toBeUndefined();
  });

  // -------------------------------------------------------------------------
  // Delete
  // -------------------------------------------------------------------------

  it("should delete a vector via SQL", async () => {
    const sqlCalls: any[] = [];
    const store = createStore({
      "/api/2.0/sql/statements": (_url: string, init: any) => {
        sqlCalls.push(JSON.parse(init.body));
        return { status: { state: "SUCCEEDED" } };
      },
    });
    await store.initialize();

    await store.delete("id-1");

    const deleteCall = sqlCalls.find((c) => c.statement?.includes("DELETE"));
    expect(deleteCall).toBeDefined();
    expect(deleteCall.parameters).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ name: "vector_id", value: "id-1" }),
      ]),
    );
  });

  it("should delete the index via deleteCol", async () => {
    let deleteCalled = false;
    const store = createStore({
      "/api/2.0/vector-search/indexes/test_catalog": (
        _url: string,
        init: any,
      ) => {
        if (init?.method === "DELETE") deleteCalled = true;
        return {};
      },
    });
    await store.initialize();

    await store.deleteCol();
    expect(deleteCalled).toBe(true);
  });

  // -------------------------------------------------------------------------
  // List
  // -------------------------------------------------------------------------

  it("should list memories", async () => {
    const store = createStore({
      "/query": () => ({
        manifest: {
          columns: [{ name: "memory_id" }, { name: "memory" }],
        },
        result: {
          data_array: [
            ["id-1", "memory one"],
            ["id-2", "memory two"],
          ],
        },
      }),
    });
    await store.initialize();

    const [results, count] = await store.list();
    expect(results).toHaveLength(2);
    expect(count).toBe(2);
    expect(results[0].id).toBe("id-1");
  });

  // -------------------------------------------------------------------------
  // Keyword search
  // -------------------------------------------------------------------------

  it("should return null for keyword search on DIRECT_ACCESS index", async () => {
    const store = createStore();
    await store.initialize();

    const result = await store.keywordSearch("test query");
    expect(result).toBeNull();
  });

  it("should perform keyword search on DELTA_SYNC index", async () => {
    const deltaSyncHandlers = {
      ...DEFAULT_HANDLERS,
      "/query": (_url: string, init: any) => {
        const body = JSON.parse(init.body);
        expect(body.query_type).toBe("FULL_TEXT");
        return {
          manifest: {
            columns: [{ name: "memory_id" }, { name: "memory" }],
          },
          result: { data_array: [["id-1", "keyword match"]] },
        };
      },
    };

    global.fetch = mockFetch(deltaSyncHandlers) as any;
    const store = new DatabricksVectorStore({
      ...BASE_CONFIG,
      indexType: "DELTA_SYNC",
    });
    await store.initialize();

    const results = await store.keywordSearch("keyword");
    expect(results).not.toBeNull();
    expect(results!).toHaveLength(1);
  });

  // -------------------------------------------------------------------------
  // User ID management
  // -------------------------------------------------------------------------

  it("should handle getUserId and setUserId", async () => {
    let storedUserId: string | null = null;
    const store = createStore({
      "/api/2.0/sql/statements": (_url: string, init: any) => {
        const body = JSON.parse(init.body);
        if (body.statement.includes("SELECT user_id")) {
          if (storedUserId) {
            return {
              status: { state: "SUCCEEDED" },
              result: { data_array: [[storedUserId]] },
            };
          }
          return {
            status: { state: "SUCCEEDED" },
            result: { data_array: [] },
          };
        }
        if (body.statement.includes("INSERT INTO")) {
          const param = body.parameters?.find(
            (p: any) => p.name === "user_id",
          );
          if (param) storedUserId = param.value;
        }
        return { status: { state: "SUCCEEDED" } };
      },
    });
    await store.initialize();

    const userId = await store.getUserId();
    expect(typeof userId).toBe("string");
    expect(userId.length).toBeGreaterThan(0);

    await store.setUserId("custom-user");
    const fetched = await store.getUserId();
    expect(fetched).toBe("custom-user");
  });

  // -------------------------------------------------------------------------
  // Error paths
  // -------------------------------------------------------------------------

  it("should throw on failed SQL execution", async () => {
    const store = createStore({
      "/api/2.0/sql/statements": () => ({
        status: { state: "FAILED", error: { message: "syntax error" } },
      }),
    });
    await store.initialize();

    await expect(
      store.insert([[1, 2, 3, 4]], ["id-1"], [{ data: "test" }]),
    ).rejects.toThrow(/SQL execution failed/);
  });

  it("should throw on non-OK API response", async () => {
    const store = createStore();
    await store.initialize();

    // Replace fetch with one that returns 500 for query
    global.fetch = mockFetchWithErrors(
      DEFAULT_HANDLERS,
      { "/query": { status: 500, body: '{"error":"internal server error"}' } },
    ) as any;

    await expect(store.search([1, 2, 3, 4], 5)).rejects.toThrow(
      /Databricks API error \(500\)/,
    );
  });
});
