/**
 * Tests for the sqlite3 → better-sqlite3 migration.
 *
 * Covers:
 * - SQLiteManager: all HistoryManager interface methods
 * - MemoryVectorStore: insert, search, get, update, delete, list, userId mgmt
 * - File-based persistence and in-memory mode
 * - Backward compatibility: same schema, same data shapes
 */

import { SQLiteManager } from "../storage/SQLiteManager";
import { MemoryVectorStore } from "../vector_stores/memory";
import fs from "fs";
import path from "path";
import os from "os";

// ---------------------------------------------------------------------------
// SQLiteManager tests
// ---------------------------------------------------------------------------

describe("SQLiteManager (better-sqlite3)", () => {
  let mgr: SQLiteManager;

  beforeEach(() => {
    mgr = new SQLiteManager(":memory:");
  });

  afterEach(() => {
    mgr.close();
  });

  it("creates an in-memory database without errors", () => {
    expect(mgr).toBeDefined();
  });

  it("addHistory inserts a row that getHistory returns", async () => {
    await mgr.addHistory(
      "mem-001",
      null,
      "User likes TypeScript",
      "ADD",
      "2026-01-01T00:00:00Z",
    );

    const history = await mgr.getHistory("mem-001");
    expect(history).toHaveLength(1);
    expect(history[0].memory_id).toBe("mem-001");
    expect(history[0].new_value).toBe("User likes TypeScript");
    expect(history[0].action).toBe("ADD");
    expect(history[0].previous_value).toBeNull();
    expect(history[0].is_deleted).toBe(0);
  });

  it("returns history in DESC order (most recent first)", async () => {
    await mgr.addHistory("mem-002", null, "First", "ADD", "2026-01-01");
    await mgr.addHistory(
      "mem-002",
      "First",
      "Updated",
      "UPDATE",
      "2026-01-01",
      "2026-01-02",
    );
    await mgr.addHistory(
      "mem-002",
      "Updated",
      null,
      "DELETE",
      undefined,
      undefined,
      1,
    );

    const history = await mgr.getHistory("mem-002");
    expect(history).toHaveLength(3);
    expect(history[0].action).toBe("DELETE");
    expect(history[1].action).toBe("UPDATE");
    expect(history[2].action).toBe("ADD");
    expect(history[0].is_deleted).toBe(1);
  });

  it("isolates history by memory_id", async () => {
    await mgr.addHistory("mem-A", null, "Fact A", "ADD", "2026-01-01");
    await mgr.addHistory("mem-B", null, "Fact B", "ADD", "2026-01-01");

    expect(await mgr.getHistory("mem-A")).toHaveLength(1);
    expect(await mgr.getHistory("mem-B")).toHaveLength(1);
    expect((await mgr.getHistory("mem-A"))[0].new_value).toBe("Fact A");
    expect((await mgr.getHistory("mem-B"))[0].new_value).toBe("Fact B");
  });

  it("handles NULL/undefined optional fields correctly", async () => {
    await mgr.addHistory(
      "mem-null",
      null,
      null,
      "DELETE",
      undefined,
      undefined,
      1,
    );

    const history = await mgr.getHistory("mem-null");
    expect(history).toHaveLength(1);
    expect(history[0].previous_value).toBeNull();
    expect(history[0].new_value).toBeNull();
    expect(history[0].created_at).toBeNull();
    expect(history[0].updated_at).toBeNull();
  });

  it("reset() clears all history and allows re-insertion", async () => {
    await mgr.addHistory("mem-003", null, "Fact", "ADD", "2026-01-01");
    expect(await mgr.getHistory("mem-003")).toHaveLength(1);

    await mgr.reset();
    expect(await mgr.getHistory("mem-003")).toHaveLength(0);

    await mgr.addHistory("mem-004", null, "New fact", "ADD", "2026-02-01");
    expect(await mgr.getHistory("mem-004")).toHaveLength(1);
  });

  it("works with file-based database and persists data", async () => {
    const dbPath = path.join(os.tmpdir(), `mem0-test-history-${Date.now()}.db`);

    try {
      const fmgr = new SQLiteManager(dbPath);
      await fmgr.addHistory(
        "mem-file",
        null,
        "Persistent",
        "ADD",
        "2026-01-01",
      );
      fmgr.close();

      expect(fs.existsSync(dbPath)).toBe(true);
      expect(fs.statSync(dbPath).size).toBeGreaterThan(0);

      // Reopen and verify
      const fmgr2 = new SQLiteManager(dbPath);
      const history = await fmgr2.getHistory("mem-file");
      expect(history).toHaveLength(1);
      expect(history[0].new_value).toBe("Persistent");
      fmgr2.close();
    } finally {
      if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath);
    }
  });

  it("handles many rapid insertions", async () => {
    for (let i = 0; i < 100; i++) {
      await mgr.addHistory(
        `mem-rapid-${i}`,
        null,
        `Fact ${i}`,
        "ADD",
        new Date().toISOString(),
      );
    }

    for (let i = 0; i < 100; i++) {
      const h = await mgr.getHistory(`mem-rapid-${i}`);
      expect(h).toHaveLength(1);
      expect(h[0].new_value).toBe(`Fact ${i}`);
    }
  });
});

// ---------------------------------------------------------------------------
// MemoryVectorStore tests
// ---------------------------------------------------------------------------

describe("MemoryVectorStore (better-sqlite3)", () => {
  const DIM = 4;
  let store: MemoryVectorStore;
  let dbPath: string;

  function normalize(v: number[]): number[] {
    const norm = Math.sqrt(v.reduce((s, x) => s + x * x, 0));
    return v.map((x) => x / norm);
  }

  beforeEach(() => {
    dbPath = path.join(os.tmpdir(), `mem0-test-vectors-${Date.now()}.db`);
    store = new MemoryVectorStore({ dimension: DIM, dbPath } as any);
  });

  afterEach(() => {
    if (fs.existsSync(dbPath)) fs.unlinkSync(dbPath);
  });

  it("insert + get returns the stored payload", async () => {
    const v = normalize([1, 0, 0, 0]);
    await store.insert([v], ["id-1"], [{ data: "hello", userId: "u1" }]);

    const result = await store.get("id-1");
    expect(result).not.toBeNull();
    expect(result!.id).toBe("id-1");
    expect(result!.payload.data).toBe("hello");
    expect(result!.payload.user_id).toBe("u1");
  });

  it("get returns null for non-existent id", async () => {
    const result = await store.get("nope");
    expect(result).toBeNull();
  });

  it("search returns results sorted by cosine similarity", async () => {
    const v1 = normalize([1, 0, 0, 0]);
    const v2 = normalize([0, 1, 0, 0]);
    const v3 = normalize([1, 1, 0, 0]);

    await store.insert(
      [v1, v2, v3],
      ["id-1", "id-2", "id-3"],
      [{ data: "exact" }, { data: "orthogonal" }, { data: "close" }],
    );

    const results = await store.search(v1, 3);
    expect(results).toHaveLength(3);
    expect(results[0].id).toBe("id-1");
    expect(results[0].score).toBeCloseTo(1.0, 5);
    expect(results[1].id).toBe("id-3");
    expect(results[2].id).toBe("id-2");
    expect(results[2].score).toBeCloseTo(0, 5);
  });

  it("search respects limit", async () => {
    const vectors = [];
    const ids = [];
    const payloads = [];
    for (let i = 0; i < 10; i++) {
      const v = [0, 0, 0, 0];
      v[i % DIM] = 1;
      vectors.push(normalize(v));
      ids.push(`id-${i}`);
      payloads.push({ data: `item-${i}` });
    }
    await store.insert(vectors, ids, payloads);

    const results = await store.search(normalize([1, 0, 0, 0]), 3);
    expect(results).toHaveLength(3);
  });

  it("search respects filters", async () => {
    const v = normalize([1, 0, 0, 0]);
    await store.insert(
      [v, v],
      ["id-1", "id-2"],
      [
        { data: "a", userId: "alice" },
        { data: "b", userId: "bob" },
      ],
    );

    const results = await store.search(v, 10, { user_id: "alice" });
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe("id-1");
  });

  it("search throws on dimension mismatch", async () => {
    await expect(store.search([1, 0, 0], 10)).rejects.toThrow(
      "dimension mismatch",
    );
  });

  it("insert throws on dimension mismatch", async () => {
    await expect(
      store.insert([[1, 0, 0]], ["id-1"], [{ data: "x" }]),
    ).rejects.toThrow("dimension mismatch");
  });

  it("update modifies the stored vector and payload", async () => {
    const v1 = normalize([1, 0, 0, 0]);
    const v2 = normalize([0, 1, 0, 0]);
    await store.insert([v1], ["id-1"], [{ data: "original" }]);

    await store.update("id-1", v2, { data: "updated" });

    const result = await store.get("id-1");
    expect(result!.payload.data).toBe("updated");

    const results = await store.search(v2, 1);
    expect(results[0].id).toBe("id-1");
    expect(results[0].score).toBeCloseTo(1.0, 5);
  });

  it("delete removes the vector", async () => {
    const v = normalize([1, 0, 0, 0]);
    await store.insert([v], ["id-1"], [{ data: "doomed" }]);

    await store.delete("id-1");
    expect(await store.get("id-1")).toBeNull();
  });

  it("deleteCol drops and recreates table", async () => {
    const v = normalize([1, 0, 0, 0]);
    await store.insert([v], ["id-1"], [{ data: "will be gone" }]);

    await store.deleteCol();
    expect(await store.get("id-1")).toBeNull();

    await store.insert([v], ["id-2"], [{ data: "fresh" }]);
    expect(await store.get("id-2")).not.toBeNull();
  });

  it("list returns all vectors with optional filters", async () => {
    const v = normalize([1, 0, 0, 0]);
    await store.insert(
      [v, v, v],
      ["id-1", "id-2", "id-3"],
      [
        { data: "a", userId: "alice" },
        { data: "b", userId: "bob" },
        { data: "c", userId: "alice" },
      ],
    );

    const [all, totalAll] = await store.list();
    expect(all).toHaveLength(3);
    expect(totalAll).toBe(3);

    const [filtered, totalFiltered] = await store.list({ user_id: "alice" });
    expect(filtered).toHaveLength(2);
    expect(totalFiltered).toBe(2);
  });

  it("list respects limit", async () => {
    const v = normalize([1, 0, 0, 0]);
    await store.insert(
      [v, v, v],
      ["id-1", "id-2", "id-3"],
      [{ data: "a" }, { data: "b" }, { data: "c" }],
    );

    const [results] = await store.list(undefined, 2);
    expect(results).toHaveLength(2);
  });

  it("getUserId generates and persists a userId", async () => {
    const id1 = await store.getUserId();
    expect(typeof id1).toBe("string");
    expect(id1.length).toBeGreaterThan(0);

    const id2 = await store.getUserId();
    expect(id2).toBe(id1);
  });

  it("setUserId overrides the stored userId", async () => {
    await store.setUserId("custom-user-123");
    const id = await store.getUserId();
    expect(id).toBe("custom-user-123");
  });

  it("INSERT OR REPLACE upserts on id conflict", async () => {
    const v1 = normalize([1, 0, 0, 0]);
    const v2 = normalize([0, 1, 0, 0]);
    await store.insert([v1], ["id-1"], [{ data: "original" }]);
    await store.insert([v2], ["id-1"], [{ data: "replaced" }]);

    const result = await store.get("id-1");
    expect(result!.payload.data).toBe("replaced");

    const [all] = await store.list();
    expect(all).toHaveLength(1);
  });

  it("file-based database persists across reopens", async () => {
    const v = normalize([1, 0, 0, 0]);
    await store.insert([v], ["id-persist"], [{ data: "persistent" }]);

    const store2 = new MemoryVectorStore({ dimension: DIM, dbPath } as any);
    const result = await store2.get("id-persist");
    expect(result).not.toBeNull();
    expect(result!.payload.data).toBe("persistent");
  });
});
