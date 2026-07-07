import { OpenSearchDB } from "../src/vector_stores/opensearch";

// These tests run entirely against a mocked OpenSearch client (no live cluster).
// They lock the index mapping and the filter query paths together: `payload` must
// stay a dynamic object so that a `.keyword` sub-field exists for the exact-match
// term clauses the filter builder emits. Mapping payload sub-keys as explicit
// `keyword` fields removes that sub-field and makes every scoped filter match
// nothing, so the createCol + search assertions here guard that regression.

describe("OpenSearchDB", () => {
  const collectionName = "memories";
  const dims = 3;

  function createClient(overrides: Record<string, any> = {}) {
    const { indices: indicesOverride, ...rest } = overrides;
    return {
      indices: {
        exists: jest.fn().mockResolvedValue(false),
        create: jest.fn().mockResolvedValue({ body: { acknowledged: true } }),
        delete: jest.fn().mockResolvedValue({ body: { acknowledged: true } }),
        ...(indicesOverride || {}),
      },
      bulk: jest.fn().mockResolvedValue({ body: { errors: false, items: [] } }),
      search: jest.fn().mockResolvedValue({
        body: { hits: { hits: [], total: { value: 0 } } },
      }),
      get: jest.fn().mockResolvedValue({ body: { _source: null } }),
      update: jest.fn().mockResolvedValue({ body: {} }),
      delete: jest.fn().mockResolvedValue({ body: {} }),
      index: jest.fn().mockResolvedValue({ body: {} }),
      ...rest,
    };
  }

  async function createStore(client: any) {
    const store = new OpenSearchDB({
      collectionName,
      embeddingModelDims: dims,
      client: client as any,
    });
    await store.initialize();
    return store;
  }

  it("maps payload as a dynamic object and enables knn without a slow refresh override", async () => {
    const client = createClient();
    await createStore(client);

    const createCall = client.indices.create.mock.calls.find(
      ([arg]: any[]) => arg.index === collectionName,
    );
    expect(createCall).toBeDefined();

    const body = createCall[0].body;
    // Dynamic payload object is what gives user_id/agent_id/run_id their
    // `.keyword` sub-field. Enumerated keyword sub-properties would break filters.
    expect(body.mappings.properties.payload).toEqual({ type: "object" });
    expect(body.mappings.properties.payload.properties).toBeUndefined();
    // No dead metadata mirror of payload.
    expect(body.mappings.properties.metadata).toBeUndefined();
    // knn on, and no 10s refresh_interval that would hide freshly added memories.
    expect(body.settings.index.knn).toBe(true);
    expect(body.settings.index.refresh_interval).toBeUndefined();
  });

  it("inserts payload and id without a duplicate metadata field", async () => {
    const client = createClient();
    const store = await createStore(client);

    await store.insert(
      [[0.1, 0.2, 0.3]],
      ["mem-1"],
      [{ user_id: "alice", data: "Alice likes pizza" }],
    );

    expect(client.bulk).toHaveBeenCalledTimes(1);
    const operations = client.bulk.mock.calls[0][0].body;
    const [action, doc] = operations;
    expect(action).toEqual({ index: { _index: collectionName, _id: "mem-1" } });
    expect(doc.payload).toEqual({
      user_id: "alice",
      data: "Alice likes pizza",
    });
    expect(doc.id).toBe("mem-1");
    // No dead metadata/text mirror fields (Python live insert writes neither).
    expect(doc).not.toHaveProperty("metadata");
    expect(doc).not.toHaveProperty("text");
  });

  it("scopes search by user_id via the payload.<key>.keyword term path", async () => {
    const client = createClient();
    const store = await createStore(client);

    await store.search([0.1, 0.2, 0.3], 5, { user_id: "alice" });

    const searchCall = client.search.mock.calls.find(
      ([arg]: any[]) => arg.index === collectionName,
    );
    expect(searchCall).toBeDefined();
    const filter = searchCall[0].body.query.bool.filter;
    expect(filter).toContainEqual({
      term: { "payload.user_id.keyword": "alice" },
    });
  });

  it("lists filtered results with a total count", async () => {
    const client = createClient({
      search: jest.fn().mockResolvedValue({
        body: {
          hits: {
            total: { value: 1 },
            hits: [
              {
                _id: "mem-1",
                _score: 1,
                _source: { id: "mem-1", payload: { user_id: "alice" } },
              },
            ],
          },
        },
      }),
    });
    const store = await createStore(client);

    const [results, total] = await store.list({ user_id: "alice" });

    expect(total).toBe(1);
    expect(results).toEqual([
      { id: "mem-1", payload: { user_id: "alice" }, score: 1 },
    ]);
  });

  it("rejects object filter values that could inject query parameters", async () => {
    const client = createClient();
    const store = await createStore(client);

    // A term query accepts an object form ({value, boost, case_insensitive}),
    // so an object leaf would let a caller inject raw query params. Guarded.
    await expect(
      store.search([0.1, 0.2, 0.3], 5, {
        user_id: { eq: { boost: 999, value: "x" } },
      } as any),
    ).rejects.toThrow(/must be a string, number, or boolean/);

    expect(client.search).not.toHaveBeenCalled();
  });

  it("returns null from get when the document is missing (404)", async () => {
    const client = createClient({
      get: jest.fn().mockRejectedValue({ statusCode: 404 }),
    });
    const store = await createStore(client);

    await expect(store.get("missing")).resolves.toBeNull();
  });
});
