import { Milvus } from "../vector_stores/milvus";

/**
 * In-memory fake of the subset of the `@zilliz/milvus2-sdk-node` MilvusClient
 * API that the Milvus vector store uses. Lets us exercise the provider's
 * request shaping and response parsing without a live Milvus server or the SDK.
 */
class FakeMilvusClient {
  public calls: { method: string; args: any }[] = [];
  private collections = new Set<string>();
  // collection -> id -> row
  private store: Record<string, Record<string, any>> = {};
  // collection -> declared vector dimension (recorded from createCollection)
  private dims: Record<string, number> = {};

  // Allow tests to script search responses.
  public searchResponse: any = { results: [] };

  constructor(opts?: { existing?: string[] }) {
    for (const c of opts?.existing || []) {
      this.collections.add(c);
      this.store[c] = {};
    }
  }

  async hasCollection({ collection_name }: any) {
    this.calls.push({ method: "hasCollection", args: { collection_name } });
    return { value: this.collections.has(collection_name) };
  }

  async createCollection(args: any) {
    this.calls.push({ method: "createCollection", args });
    // Mirror Milvus's real server constraint: a FloatVector field's dim must be
    // in [2, 32768]. Vector fields are the ones carrying a numeric `dim`.
    for (const f of args.fields || []) {
      if (typeof f.dim === "number" && (f.dim < 2 || f.dim > 32768)) {
        throw new Error(
          `invalid dimension: ${f.dim}. should be in range 2 ~ 32768`,
        );
      }
    }
    const vectorField = (args.fields || []).find(
      (f: any) => typeof f.dim === "number",
    );
    if (vectorField) this.dims[args.collection_name] = vectorField.dim;
    this.collections.add(args.collection_name);
    this.store[args.collection_name] = this.store[args.collection_name] || {};
  }

  // Reject rows whose vector length disagrees with the collection's declared
  // dim, exactly as the real server would.
  private checkDims(collection: string, data: any[]) {
    const dim = this.dims[collection];
    if (dim == null) return; // pre-seeded collection: dim not tracked
    for (const row of data || []) {
      if (Array.isArray(row.vectors) && row.vectors.length !== dim) {
        throw new Error(
          `vector dimension mismatch: expected ${dim}, got ${row.vectors.length}`,
        );
      }
    }
  }

  async loadCollection(args: any) {
    this.calls.push({ method: "loadCollection", args });
  }

  async dropCollection(args: any) {
    this.calls.push({ method: "dropCollection", args });
    this.collections.delete(args.collection_name);
    delete this.store[args.collection_name];
  }

  async insert(args: any) {
    this.calls.push({ method: "insert", args });
    this.checkDims(args.collection_name, args.data);
    const col = (this.store[args.collection_name] =
      this.store[args.collection_name] || {});
    for (const row of args.data) col[String(row.id)] = row;
  }

  async upsert(args: any) {
    this.calls.push({ method: "upsert", args });
    this.checkDims(args.collection_name, args.data);
    const col = (this.store[args.collection_name] =
      this.store[args.collection_name] || {});
    for (const row of args.data) col[String(row.id)] = row;
  }

  async delete(args: any) {
    this.calls.push({ method: "delete", args });
    const col = this.store[args.collection_name] || {};
    for (const id of args.ids) delete col[String(id)];
  }

  async get(args: any) {
    this.calls.push({ method: "get", args });
    const col = this.store[args.collection_name] || {};
    const data = args.ids.map((id: string) => col[String(id)]).filter(Boolean);
    return { data };
  }

  async query(args: any) {
    this.calls.push({ method: "query", args });
    const col = this.store[args.collection_name] || {};
    return { data: Object.values(col).slice(0, args.limit ?? 100) };
  }

  async search(args: any) {
    this.calls.push({ method: "search", args });
    return this.searchResponse;
  }
}

// Suppress the constructor's fire-and-forget initialize() console noise.
beforeAll(() => {
  jest.spyOn(console, "error").mockImplementation(() => {});
});
afterAll(() => {
  (console.error as jest.Mock).mockRestore?.();
});

describe("Milvus vector store (TS OSS SDK)", () => {
  function makeStore(client: FakeMilvusClient, overrides: any = {}) {
    return new Milvus({
      client,
      collectionName: "mem0",
      embeddingModelDims: 3,
      ...overrides,
    });
  }

  it("creates the collection on initialize when it does not exist", async () => {
    const client = new FakeMilvusClient();
    const store = makeStore(client);
    await store.initialize();

    const created = client.calls.find((c) => c.method === "createCollection");
    expect(created).toBeDefined();
    expect(created!.args.collection_name).toBe("mem0");
    const vectorField = created!.args.fields.find(
      (f: any) => f.name === "vectors",
    );
    expect(vectorField.dim).toBe(3);
    // AUTOINDEX dense index with the default metric (L2, matching the Python provider).
    expect(created!.args.index_params[0].metric_type).toBe("L2");
  });

  it("does not recreate an existing collection", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    const store = makeStore(client);
    await store.initialize();
    expect(client.calls.some((c) => c.method === "createCollection")).toBe(
      false,
    );
  });

  it("inserts records mapping payloads into the metadata field", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    const store = makeStore(client);
    await store.initialize();

    await store.insert(
      [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
      ],
      ["a", "b"],
      [
        { data: "first", user_id: "u1" },
        { data: "second", user_id: "u1" },
      ],
    );

    const insertCall = client.calls.find((c) => c.method === "insert")!;
    expect(insertCall.args.data).toHaveLength(2);
    expect(insertCall.args.data[0]).toEqual({
      id: "a",
      vectors: [0.1, 0.2, 0.3],
      metadata: { data: "first", user_id: "u1" },
    });
  });

  it("round-trips a stored record through get()", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    const store = makeStore(client);
    await store.initialize();
    await store.insert([[1, 0, 0]], ["x"], [{ data: "hello" }]);

    const got = await store.get("x");
    expect(got).not.toBeNull();
    expect(got!.id).toBe("x");
    expect(got!.payload).toEqual({ data: "hello" });

    const missing = await store.get("nope");
    expect(missing).toBeNull();
  });

  it("builds an AND-combined equality filter expression for search", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    client.searchResponse = {
      results: [{ id: "a", score: 0.9, metadata: { data: "first" } }],
    };
    // Pin a non-L2 metric so the raw score passes through unnormalised.
    const store = makeStore(client, { metricType: "COSINE" });
    await store.initialize();

    const res = await store.search([0.1, 0.2, 0.3], 5, {
      user_id: "u1",
      agent_id: 7 as any,
    });

    const searchCall = client.calls.find((c) => c.method === "search")!;
    expect(searchCall.args.filter).toBe(
      '(metadata["user_id"] == "u1") and (metadata["agent_id"] == 7)',
    );
    expect(searchCall.args.limit).toBe(5);
    expect(res[0]).toEqual({
      id: "a",
      payload: { data: "first" },
      score: 0.9,
    });
  });

  it("normalises L2 distances into a 0..1 similarity score", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    client.searchResponse = {
      results: [{ id: "a", score: 3.0, metadata: {} }],
    };
    const store = makeStore(client, { metricType: "L2" });
    await store.initialize();

    const res = await store.search([0, 0, 1], 1);
    // 1 / (1 + 3) = 0.25
    expect(res[0].score).toBeCloseTo(0.25, 6);
  });

  it("escapes embedded quotes in string filter values", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    const store = makeStore(client);
    await store.initialize();
    await store.list({ data: 'a"b' });
    const queryCall = client.calls.filter((c) => c.method === "query").pop()!;
    expect(queryCall.args.filter).toBe('(metadata["data"] == "a\\"b")');
  });

  it("escapes backslashes in string filter values", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    const store = makeStore(client);
    await store.initialize();
    // Value is a\b (one backslash); it must be doubled so the expression
    // stays well-formed and the backslash can't escape the closing quote.
    await store.list({ data: "a\\b" });
    const queryCall = client.calls.filter((c) => c.method === "query").pop()!;
    expect(queryCall.args.filter).toBe('(metadata["data"] == "a\\\\b")');
  });

  it("rejects filter keys that are not safe identifiers", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    const store = makeStore(client);
    await store.initialize();
    await expect(
      store.list({ 'x"] or true or ["y': "z" } as any),
    ).rejects.toThrow(/Invalid filter key/);
  });

  it("lists records and returns the count", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    const store = makeStore(client);
    await store.initialize();
    await store.insert(
      [
        [1, 0, 0],
        [0, 1, 0],
      ],
      ["a", "b"],
      [{ data: "x" }, { data: "y" }],
    );

    const [results, count] = await store.list(undefined, 100);
    expect(count).toBe(2);
    expect(results.map((r) => r.id).sort()).toEqual(["a", "b"]);
  });

  it("deletes a record by id", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    const store = makeStore(client);
    await store.initialize();
    await store.insert([[1, 0, 0]], ["a"], [{ data: "x" }]);
    await store.delete("a");
    const got = await store.get("a");
    expect(got).toBeNull();
  });

  it("generates and persists a user id, then reads it back", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    const store = makeStore(client);
    await store.initialize();

    const created = await store.getUserId();
    expect(typeof created).toBe("string");
    expect(created.length).toBeGreaterThan(0);

    const readBack = await store.getUserId();
    expect(readBack).toBe(created);
  });

  it("setUserId overwrites in place instead of appending rows", async () => {
    const client = new FakeMilvusClient();
    const store = makeStore(client);
    await store.initialize();

    await store.setUserId("user-1");
    await store.setUserId("user-2");

    // A fresh insert per call would leave two rows; the reuse-id upsert keeps one.
    const all = await client.query({
      collection_name: "memory_migrations",
      limit: 100,
    });
    expect(all.data).toHaveLength(1);
    expect(all.data[0].user_id).toBe("user-2");
    expect(await store.getUserId()).toBe("user-2");
  });

  it("creates the telemetry collection with a Milvus-valid vector dim (>= 2)", async () => {
    // Regression: the helper collection previously used dim 1, which a real
    // Milvus server rejects (valid range is 2~32768), silently breaking
    // getUserId/setUserId. The fake now enforces the same bound, so a dim < 2
    // would throw here instead of passing as it did against the old mock.
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    const store = makeStore(client);
    await store.initialize();
    await store.getUserId();

    const migCreate = client.calls.find(
      (c) =>
        c.method === "createCollection" &&
        c.args.collection_name === "memory_migrations",
    )!;
    expect(migCreate).toBeDefined();
    const vectorField = migCreate.args.fields.find(
      (f: any) => f.name === "vectors",
    );
    expect(vectorField.dim).toBeGreaterThanOrEqual(2);
  });

  it("keywordSearch returns null (BM25 not implemented in TS provider)", async () => {
    const client = new FakeMilvusClient({ existing: ["mem0"] });
    const store = makeStore(client);
    await store.initialize();
    expect(await store.keywordSearch()).toBeNull();
  });
});
