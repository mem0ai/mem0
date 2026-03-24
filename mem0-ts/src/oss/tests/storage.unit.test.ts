/**
 * Storage manager unit tests — SQLiteManager, DummyHistoryManager.
 * Uses real in-memory SQLite, no external dependencies.
 */
/// <reference types="jest" />
import { SQLiteManager } from "../src/storage/SQLiteManager";
import { DummyHistoryManager } from "../src/storage/DummyHistoryManager";
import { MemoryHistoryManager } from "../src/storage/MemoryHistoryManager";

// ─── SQLiteManager ──────────────────────────────────────

describe("SQLiteManager", () => {
  let db: SQLiteManager;

  beforeEach(() => {
    db = new SQLiteManager(":memory:");
  });

  afterEach(() => {
    db.close();
  });

  test("constructs without throwing", () => {
    expect(db).toBeDefined();
  });

  test("addHistory inserts a record retrievable by getHistory", async () => {
    await db.addHistory(
      "mem1",
      null,
      "new value",
      "ADD",
      "2026-01-01T00:00:00Z",
    );
    const history = await db.getHistory("mem1");
    expect(history).toHaveLength(1);
    expect(history[0].memory_id).toBe("mem1");
    expect(history[0].new_value).toBe("new value");
    expect(history[0].action).toBe("ADD");
  });

  test("getHistory returns records in reverse chronological order", async () => {
    await db.addHistory("mem1", null, "first", "ADD", "2026-01-01");
    await db.addHistory("mem1", "first", "second", "UPDATE", "2026-01-02");
    await db.addHistory("mem1", "second", "third", "UPDATE", "2026-01-03");
    const history = await db.getHistory("mem1");
    expect(history).toHaveLength(3);
    // DESC order by id: most recent first
    expect(history[0].new_value).toBe("third");
    expect(history[2].new_value).toBe("first");
  });

  test("getHistory returns empty array for non-existent memory", async () => {
    const history = await db.getHistory("nonexistent");
    expect(history).toHaveLength(0);
  });

  test("addHistory stores previous_value for UPDATE", async () => {
    await db.addHistory("mem1", "old text", "new text", "UPDATE");
    const history = await db.getHistory("mem1");
    expect(history[0].previous_value).toBe("old text");
    expect(history[0].new_value).toBe("new text");
  });

  test("addHistory stores null new_value for DELETE", async () => {
    await db.addHistory(
      "mem1",
      "deleted text",
      null,
      "DELETE",
      undefined,
      undefined,
      1,
    );
    const history = await db.getHistory("mem1");
    expect(history[0].action).toBe("DELETE");
    expect(history[0].new_value).toBeNull();
    expect(history[0].is_deleted).toBe(1);
  });

  test("reset clears all history and recreates table", async () => {
    await db.addHistory("mem1", null, "data", "ADD");
    await db.addHistory("mem2", null, "data", "ADD");
    await db.reset();
    expect(await db.getHistory("mem1")).toHaveLength(0);
    expect(await db.getHistory("mem2")).toHaveLength(0);
    // Table still works after reset
    await db.addHistory("mem3", null, "after reset", "ADD");
    expect(await db.getHistory("mem3")).toHaveLength(1);
  });

  test("stores createdAt and updatedAt timestamps", async () => {
    const created = "2026-03-17T10:00:00Z";
    const updated = "2026-03-17T11:00:00Z";
    await db.addHistory("mem1", null, "data", "ADD", created, updated);
    const history = await db.getHistory("mem1");
    expect(history[0].created_at).toBe(created);
    expect(history[0].updated_at).toBe(updated);
  });

  test("handles multiple memories independently", async () => {
    await db.addHistory("mem1", null, "data1", "ADD");
    await db.addHistory("mem2", null, "data2", "ADD");
    expect(await db.getHistory("mem1")).toHaveLength(1);
    expect(await db.getHistory("mem2")).toHaveLength(1);
  });
});

// ─── DummyHistoryManager ────────────────────────────────

describe("DummyHistoryManager", () => {
  let dummy: DummyHistoryManager;

  beforeEach(() => {
    dummy = new DummyHistoryManager();
  });

  test("constructs without throwing", () => {
    expect(dummy).toBeDefined();
  });

  test("addHistory is a no-op that resolves", async () => {
    await expect(
      dummy.addHistory("id", null, "val", "ADD"),
    ).resolves.toBeUndefined();
  });

  test("getHistory returns empty array", async () => {
    const result = await dummy.getHistory("any-id");
    expect(result).toEqual([]);
  });

  test("reset resolves without throwing", async () => {
    await expect(dummy.reset()).resolves.toBeUndefined();
  });

  test("close does not throw", () => {
    expect(() => dummy.close()).not.toThrow();
  });
});

// ─── MemoryHistoryManager ───────────────────────────────

describe("MemoryHistoryManager", () => {
  let mgr: MemoryHistoryManager;

  beforeEach(() => {
    mgr = new MemoryHistoryManager();
  });

  test("constructs without throwing", () => {
    expect(mgr).toBeDefined();
  });

  test("addHistory + getHistory round-trips correctly", async () => {
    await mgr.addHistory(
      "mem1",
      null,
      "new value",
      "ADD",
      "2026-01-01T00:00:00Z",
    );
    const history = await mgr.getHistory("mem1");
    expect(history).toHaveLength(1);
    expect(history[0].memory_id).toBe("mem1");
    expect(history[0].new_value).toBe("new value");
    expect(history[0].action).toBe("ADD");
  });

  test("getHistory returns entries sorted by date descending", async () => {
    await mgr.addHistory("mem1", null, "first", "ADD", "2026-01-01T00:00:00Z");
    await mgr.addHistory(
      "mem1",
      "first",
      "second",
      "UPDATE",
      "2026-01-02T00:00:00Z",
    );
    await mgr.addHistory(
      "mem1",
      "second",
      "third",
      "UPDATE",
      "2026-01-03T00:00:00Z",
    );
    const history = await mgr.getHistory("mem1");
    expect(history).toHaveLength(3);
    expect(history[0].new_value).toBe("third");
    expect(history[2].new_value).toBe("first");
  });

  test("getHistory returns empty array for non-existent memory", async () => {
    expect(await mgr.getHistory("nonexistent")).toHaveLength(0);
  });

  test("getHistory caps at 100 entries", async () => {
    for (let i = 0; i < 110; i++) {
      await mgr.addHistory(
        "mem1",
        null,
        `entry-${i}`,
        "ADD",
        `2026-01-01T00:${String(i).padStart(2, "0")}:00Z`,
      );
    }
    const history = await mgr.getHistory("mem1");
    expect(history).toHaveLength(100);
  });

  test("reset clears all entries", async () => {
    await mgr.addHistory("mem1", null, "data", "ADD");
    await mgr.addHistory("mem2", null, "data", "ADD");
    await mgr.reset();
    expect(await mgr.getHistory("mem1")).toHaveLength(0);
    expect(await mgr.getHistory("mem2")).toHaveLength(0);
  });

  test("close does not throw", () => {
    expect(() => mgr.close()).not.toThrow();
  });

  test("isolates history by memory_id", async () => {
    await mgr.addHistory("mem1", null, "d1", "ADD");
    await mgr.addHistory("mem2", null, "d2", "ADD");
    expect(await mgr.getHistory("mem1")).toHaveLength(1);
    expect(await mgr.getHistory("mem2")).toHaveLength(1);
  });
});
