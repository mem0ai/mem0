import { UpstashVector } from "../src/vector_stores/upstash_vector";

describe("UpstashVector", () => {
  const namespace = "memories";

  function createClient(overrides: Record<string, jest.Mock> = {}) {
    return {
      upsert: jest.fn().mockResolvedValue("Success"),
      query: jest.fn().mockResolvedValue([]),
      fetch: jest.fn().mockResolvedValue([]),
      update: jest.fn().mockResolvedValue({ updated: 1 }),
      delete: jest.fn().mockResolvedValue({ deleted: 1 }),
      reset: jest.fn().mockResolvedValue("Success"),
      range: jest.fn().mockResolvedValue({ vectors: [], nextCursor: "" }),
      ...overrides,
    };
  }

  it("upserts vectors into the collection namespace", async () => {
    const client = createClient();
    const store = new UpstashVector({
      collectionName: namespace,
      client: client as any,
    });

    await store.insert(
      [[0.1, 0.2]],
      ["memory-1"],
      [{ data: "hello", user_id: "user-1" }],
    );

    expect(client.upsert).toHaveBeenCalledWith(
      [
        {
          id: "memory-1",
          vector: [0.1, 0.2],
          metadata: { data: "hello", user_id: "user-1" },
        },
      ],
      { namespace },
    );
  });

  it("queries vectors with converted filters", async () => {
    const client = createClient({
      query: jest.fn().mockResolvedValue([
        {
          id: "memory-1",
          score: 0.9,
          metadata: { data: "hello", user_id: "user-1" },
        },
      ]),
    });
    const store = new UpstashVector({
      collectionName: namespace,
      client: client as any,
    });

    const results = await store.search([0.1, 0.2], 3, {
      user_id: "user-1",
      active: true,
    });

    expect(client.query).toHaveBeenCalledWith(
      {
        vector: [0.1, 0.2],
        topK: 3,
        filter: 'user_id = "user-1" AND active = true',
        includeMetadata: true,
      },
      { namespace },
    );
    expect(results).toEqual([
      {
        id: "memory-1",
        payload: { data: "hello", user_id: "user-1" },
        score: 0.9,
      },
    ]);
  });

  it("fetches, updates, deletes, resets, and lists vectors in the namespace", async () => {
    const client = createClient({
      fetch: jest.fn().mockResolvedValue([
        {
          id: "memory-1",
          metadata: { data: "hello" },
        },
      ]),
      range: jest
        .fn()
        .mockResolvedValueOnce({
          vectors: [
            { id: "memory-1", metadata: { user_id: "user-1" } },
            { id: "memory-2", metadata: { user_id: "user-2" } },
          ],
          nextCursor: "2",
        })
        .mockResolvedValueOnce({
          vectors: [{ id: "memory-3", metadata: { user_id: "user-1" } }],
          nextCursor: "",
        }),
    });
    const store = new UpstashVector({
      collectionName: namespace,
      client: client as any,
    });

    await expect(store.get("memory-1")).resolves.toEqual({
      id: "memory-1",
      payload: { data: "hello" },
    });
    await store.update("memory-1", [0.3], { data: "updated" });
    await store.delete("memory-1");
    await store.deleteCol();
    await store.reset();
    await expect(store.list({ user_id: "user-1" }, 2)).resolves.toEqual([
      [
        { id: "memory-1", payload: { user_id: "user-1" } },
        { id: "memory-3", payload: { user_id: "user-1" } },
      ],
      2,
    ]);

    expect(client.fetch).toHaveBeenCalledWith(["memory-1"], {
      includeMetadata: true,
      namespace,
    });
    expect(client.upsert).toHaveBeenCalledWith(
      { id: "memory-1", vector: [0.3], metadata: { data: "updated" } },
      { namespace },
    );
    expect(client.delete).toHaveBeenCalledWith("memory-1", { namespace });
    expect(client.reset).toHaveBeenCalledTimes(2);
    expect(client.reset).toHaveBeenCalledWith({ namespace });
  });

  it("stops paging when the cursor is exhausted instead of re-scanning", async () => {
    // Upstash returns nextCursor "" at the end of a scan. If list() treated ""
    // as "keep going" (e.g. by checking for "0"), it would re-fetch from the
    // start and pile up duplicates until it hit topK. With fewer vectors than
    // topK, a single page must end the scan: one range call, no duplicates.
    const client = createClient({
      range: jest.fn().mockResolvedValue({
        vectors: [
          { id: "memory-1", metadata: { user_id: "user-1" } },
          { id: "memory-2", metadata: { user_id: "user-1" } },
        ],
        nextCursor: "",
      }),
    });
    const store = new UpstashVector({
      collectionName: namespace,
      client: client as any,
    });

    const [rows, count] = await store.list({ user_id: "user-1" }, 100);

    expect(client.range).toHaveBeenCalledTimes(1);
    expect(rows).toEqual([
      { id: "memory-1", payload: { user_id: "user-1" } },
      { id: "memory-2", payload: { user_id: "user-1" } },
    ]);
    expect(count).toBe(2);
  });
});
