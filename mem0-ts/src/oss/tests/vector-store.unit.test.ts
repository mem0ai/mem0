/**
 * MemoryVectorStore unit tests — insert, search, get, update, delete, list, cosine similarity.
 * Uses real SQLite in-memory DB, no external dependencies.
 */
/// <reference types="jest" />
import { MemoryVectorStore } from "../src/vector_stores/memory";
import type { VectorStoreResult } from "../src/types";

const DIM = 4; // Small dimension for fast tests

function createStore(): MemoryVectorStore {
  return new MemoryVectorStore({
    collectionName: "test",
    dimension: DIM,
    dbPath: ":memory:",
  });
}

function vec(values: number[]): number[] {
  return values;
}

describe("MemoryVectorStore - insert + get", () => {
  let store: MemoryVectorStore;

  beforeAll(() => {
    store = createStore();
  });

  test("inserts and retrieves a vector by ID", async () => {
    await store.insert(
      [vec([1, 0, 0, 0])],
      ["id1"],
      [{ data: "hello", userId: "u1" }],
    );
    const result: VectorStoreResult | null = await store.get("id1");
    expect(result).not.toBeNull();
    expect(result!.id).toBe("id1");
    expect(result!.payload.data).toBe("hello");
  });

  test("returns null for non-existent ID", async () => {
    const result = await store.get("nonexistent");
    expect(result).toBeNull();
  });

  test("throws on dimension mismatch during insert", async () => {
    await expect(
      store.insert([vec([1, 0, 0])], ["bad"], [{ data: "x" }]),
    ).rejects.toThrow("Vector dimension mismatch");
  });
});

describe("MemoryVectorStore - search", () => {
  let store: MemoryVectorStore;

  beforeAll(async () => {
    store = createStore();
    await store.insert(
      [vec([1, 0, 0, 0]), vec([0, 1, 0, 0]), vec([0.9, 0.1, 0, 0])],
      ["a", "b", "c"],
      [
        { data: "north", userId: "u1" },
        { data: "east", userId: "u1" },
        { data: "north-ish", userId: "u2" },
      ],
    );
  });

  test("returns results sorted by cosine similarity descending", async () => {
    const results: VectorStoreResult[] = await store.search(
      vec([1, 0, 0, 0]),
      10,
    );
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].id).toBe("a"); // exact match
    // scores should be descending
    for (let i = 1; i < results.length; i++) {
      expect(results[i - 1].score!).toBeGreaterThanOrEqual(results[i].score!);
    }
  });

  test("respects limit parameter", async () => {
    const results = await store.search(vec([1, 0, 0, 0]), 1);
    expect(results).toHaveLength(1);
  });

  test("filters by user_id", async () => {
    const results = await store.search(vec([1, 0, 0, 0]), 10, {
      user_id: "u2",
    });
    expect(results.every((r) => r.payload.user_id === "u2")).toBe(true);
  });

  test("returns empty when filter matches nothing", async () => {
    const results = await store.search(vec([1, 0, 0, 0]), 10, {
      user_id: "nobody",
    });
    expect(results).toHaveLength(0);
  });

  test("throws on query dimension mismatch", async () => {
    await expect(store.search(vec([1, 0]), 10)).rejects.toThrow(
      "Query dimension mismatch",
    );
  });
});

describe("MemoryVectorStore - update", () => {
  let store: MemoryVectorStore;

  beforeAll(async () => {
    store = createStore();
    await store.insert([vec([1, 0, 0, 0])], ["upd1"], [{ data: "original" }]);
  });

  test("updates payload and vector", async () => {
    await store.update("upd1", vec([0, 1, 0, 0]), { data: "updated" });
    const result = await store.get("upd1");
    expect(result!.payload.data).toBe("updated");
  });

  test("throws on dimension mismatch during update", async () => {
    await expect(
      store.update("upd1", vec([1, 0]), { data: "bad" }),
    ).rejects.toThrow("Vector dimension mismatch");
  });
});

describe("MemoryVectorStore - delete + deleteCol", () => {
  test("delete removes a vector", async () => {
    const store = createStore();
    await store.insert([vec([1, 0, 0, 0])], ["del1"], [{ data: "bye" }]);
    await store.delete("del1");
    expect(await store.get("del1")).toBeNull();
  });

  test("deleteCol clears all vectors", async () => {
    const store = createStore();
    await store.insert(
      [vec([1, 0, 0, 0]), vec([0, 1, 0, 0])],
      ["x", "y"],
      [{ data: "a" }, { data: "b" }],
    );
    await store.deleteCol();
    const [results] = await store.list();
    expect(results).toHaveLength(0);
  });
});

describe("MemoryVectorStore - list", () => {
  let store: MemoryVectorStore;

  beforeAll(async () => {
    store = createStore();
    await store.insert(
      [vec([1, 0, 0, 0]), vec([0, 1, 0, 0]), vec([0, 0, 1, 0])],
      ["l1", "l2", "l3"],
      [
        { data: "a", userId: "u1" },
        { data: "b", userId: "u1" },
        { data: "c", userId: "u2" },
      ],
    );
  });

  test("returns all vectors without filter", async () => {
    const [results, count] = await store.list();
    expect(count).toBe(3);
    expect(results).toHaveLength(3);
  });

  test("filters by user_id", async () => {
    const [results, count] = await store.list({ user_id: "u1" });
    expect(count).toBe(2);
    expect(results.every((r) => r.payload.user_id === "u1")).toBe(true);
  });

  test("respects limit", async () => {
    const [results] = await store.list(undefined, 1);
    expect(results).toHaveLength(1);
  });
});

describe("MemoryVectorStore - userId tracking", () => {
  test("getUserId generates and persists a random ID", async () => {
    const store = createStore();
    const id = await store.getUserId();
    expect(typeof id).toBe("string");
    expect(id.length).toBeGreaterThan(0);
    // Calling again returns same ID
    expect(await store.getUserId()).toBe(id);
  });

  test("setUserId overrides the stored ID", async () => {
    const store = createStore();
    await store.setUserId("custom-id");
    expect(await store.getUserId()).toBe("custom-id");
  });
});
