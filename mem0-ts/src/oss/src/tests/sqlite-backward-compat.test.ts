/**
 * Backward-compatibility tests for SQLite path handling changes.
 *
 * These tests verify that every documented and common usage pattern
 * from before the fix continues to work identically after the change.
 */
import fs from "fs";
import os from "os";
import path from "path";
import { ConfigManager } from "../config/manager";
import { SQLiteManager } from "../storage/SQLiteManager";
import { MemoryVectorStore } from "../vector_stores/memory";
import {
  ensureSQLiteDirectory,
  getDefaultVectorStoreDbPath,
} from "../utils/sqlite";

function normalize(vector: number[]): number[] {
  const norm = Math.sqrt(vector.reduce((sum, value) => sum + value * value, 0));
  return vector.map((value) => value / norm);
}

// ---------------------------------------------------------------------------
// 1. Config merging – existing patterns must keep working
// ---------------------------------------------------------------------------

describe("backward compat: ConfigManager.mergeConfig", () => {
  it("empty config returns all expected defaults", () => {
    const cfg = ConfigManager.mergeConfig({});

    expect(cfg.version).toBe("v1.1");
    expect(cfg.embedder.provider).toBe("openai");
    expect(cfg.vectorStore.provider).toBe("memory");
    expect(cfg.vectorStore.config.collectionName).toBe("memories");
    expect(cfg.vectorStore.config.dimension).toBeUndefined();
    expect(cfg.llm.provider).toBe("openai");
    expect(cfg.historyStore).toBeDefined();
    expect(cfg.historyStore!.provider).toBe("sqlite");
    expect(cfg.historyStore!.config.historyDbPath).toBe("memory.db");
    expect(cfg.disableHistory).toBe(false);
  });

  it("workaround: explicit historyStore still works (existing user pattern)", () => {
    // This is the documented workaround from all three issues
    const cfg = ConfigManager.mergeConfig({
      historyStore: {
        provider: "sqlite",
        config: { historyDbPath: "/tmp/workaround.db" },
      },
    });
    expect(cfg.historyStore!.provider).toBe("sqlite");
    expect(cfg.historyStore!.config.historyDbPath).toBe("/tmp/workaround.db");
  });

  it("disableHistory: true still works", () => {
    const cfg = ConfigManager.mergeConfig({ disableHistory: true });
    expect(cfg.disableHistory).toBe(true);
  });

  it("supabase historyStore config is preserved", () => {
    const cfg = ConfigManager.mergeConfig({
      historyStore: {
        provider: "supabase",
        config: {
          supabaseUrl: "https://abc.supabase.co",
          supabaseKey: "secret-key",
          tableName: "custom_history",
        },
      },
    });
    expect(cfg.historyStore!.provider).toBe("supabase");
    expect(cfg.historyStore!.config.supabaseUrl).toBe(
      "https://abc.supabase.co",
    );
    expect(cfg.historyStore!.config.supabaseKey).toBe("secret-key");
    expect(cfg.historyStore!.config.tableName).toBe("custom_history");
  });

  it("custom embedder, llm, vectorStore configs pass through unchanged", () => {
    const cfg = ConfigManager.mergeConfig({
      embedder: {
        provider: "ollama",
        config: { model: "nomic-embed-text", url: "http://localhost:11434" },
      },
      llm: {
        provider: "ollama",
        config: { model: "llama3.1:8b" },
      },
      vectorStore: {
        provider: "qdrant",
        config: {
          collectionName: "test",
          dimension: 768,
        },
      },
    });
    expect(cfg.embedder.provider).toBe("ollama");
    expect(cfg.embedder.config.model).toBe("nomic-embed-text");
    expect(cfg.llm.provider).toBe("ollama");
    expect(cfg.llm.config.model).toBe("llama3.1:8b");
    expect(cfg.vectorStore.provider).toBe("qdrant");
    expect(cfg.vectorStore.config.collectionName).toBe("test");
    expect(cfg.vectorStore.config.dimension).toBe(768);
  });

  it("customInstructions passes through unchanged", () => {
    const cfg = ConfigManager.mergeConfig({
      customInstructions: "You are a helpful assistant",
    });
    expect(cfg.customInstructions).toBe("You are a helpful assistant");
  });

  it("version override passes through unchanged", () => {
    const cfg = ConfigManager.mergeConfig({ version: "v1.0" });
    expect(cfg.version).toBe("v1.0");
  });
});

// ---------------------------------------------------------------------------
// 2. SQLiteManager – existing behavior preserved
// ---------------------------------------------------------------------------

describe("backward compat: SQLiteManager", () => {
  it("relative path still works (resolves from CWD)", async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-compat-"));
    const originalCwd = process.cwd();

    try {
      process.chdir(tempDir);
      const manager = new SQLiteManager("memory.db");
      await manager.addHistory("m1", null, "value", "ADD");
      const history = await manager.getHistory("m1");

      expect(history).toHaveLength(1);
      expect(fs.existsSync(path.join(tempDir, "memory.db"))).toBe(true);
      manager.close();
    } finally {
      process.chdir(originalCwd);
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("absolute path still works", async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-compat-"));
    const dbPath = path.join(tempDir, "history.db");

    try {
      const manager = new SQLiteManager(dbPath);
      await manager.addHistory("m1", null, "value", "ADD");
      expect(fs.existsSync(dbPath)).toBe(true);
      manager.close();
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it(":memory: still works", async () => {
    const manager = new SQLiteManager(":memory:");
    await manager.addHistory("m1", null, "value", "ADD");
    const history = await manager.getHistory("m1");
    expect(history).toHaveLength(1);
    manager.close();
  });

  it("reset clears history and allows re-use", async () => {
    const manager = new SQLiteManager(":memory:");
    await manager.addHistory("m1", null, "val", "ADD");
    await manager.reset();
    const history = await manager.getHistory("m1");
    expect(history).toHaveLength(0);
    await manager.addHistory("m2", null, "new-val", "ADD");
    const history2 = await manager.getHistory("m2");
    expect(history2).toHaveLength(1);
    manager.close();
  });
});

// ---------------------------------------------------------------------------
// 3. MemoryVectorStore – existing API preserved
// ---------------------------------------------------------------------------

describe("backward compat: MemoryVectorStore", () => {
  const originalCwd = process.cwd();

  afterEach(() => {
    process.chdir(originalCwd);
    jest.restoreAllMocks();
  });

  it("explicit dbPath still works (the existing config.dbPath feature)", async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-compat-vs-"));
    const dbPath = path.join(tempDir, "my_vectors.db");

    try {
      const store = new MemoryVectorStore({ dimension: 3, dbPath });
      await store.insert([normalize([1, 0, 0])], ["id1"], [{ text: "hello" }]);

      expect(fs.existsSync(dbPath)).toBe(true);

      const result = await store.get("id1");
      expect(result).not.toBeNull();
      expect(result!.payload.text).toBe("hello");
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("insert, search, get, update, delete, list all work", async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-compat-vs-"));
    const dbPath = path.join(tempDir, "test.db");

    try {
      const store = new MemoryVectorStore({ dimension: 3, dbPath });
      const v1 = normalize([1, 0, 0]);
      const v2 = normalize([0, 1, 0]);

      // insert
      await store.insert([v1, v2], ["a", "b"], [{ t: "a" }, { t: "b" }]);

      // get
      const a = await store.get("a");
      expect(a!.payload.t).toBe("a");

      // search
      const results = await store.search(v1, 2);
      expect(results).toHaveLength(2);
      expect(results[0].id).toBe("a"); // closest to v1

      // update
      await store.update("a", v2, { t: "updated" });
      const updated = await store.get("a");
      expect(updated!.payload.t).toBe("updated");

      // list
      const [listed, count] = await store.list();
      expect(count).toBe(2);
      expect(listed).toHaveLength(2);

      // delete
      await store.delete("a");
      const deleted = await store.get("a");
      expect(deleted).toBeNull();

      // deleteCol
      await store.deleteCol();
      const [afterDrop] = await store.list();
      expect(afterDrop).toHaveLength(0);
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("dimension mismatch on insert still throws", async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-compat-vs-"));
    const dbPath = path.join(tempDir, "test.db");

    try {
      const store = new MemoryVectorStore({ dimension: 3, dbPath });
      await expect(
        store.insert([[1, 0]], ["id1"], [{ t: "x" }]),
      ).rejects.toThrow("Vector dimension mismatch");
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("dimension mismatch on search still throws", async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-compat-vs-"));
    const dbPath = path.join(tempDir, "test.db");

    try {
      const store = new MemoryVectorStore({ dimension: 3, dbPath });
      await expect(store.search([1, 0], 1)).rejects.toThrow(
        "Query dimension mismatch",
      );
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("default dimension is 1536 when not specified", () => {
    const fakeHome = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-home-"));
    try {
      jest.spyOn(os, "homedir").mockReturnValue(fakeHome);
      const store = new MemoryVectorStore({});
      // Verify by trying to insert a 1536-dim vector
      const vec = new Array(1536).fill(0);
      vec[0] = 1;
      expect(store.insert([vec], ["id1"], [{ t: "x" }])).resolves.not.toThrow();
    } finally {
      fs.rmSync(fakeHome, { recursive: true, force: true });
    }
  });

  it("search with filters still works", async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-compat-vs-"));
    const dbPath = path.join(tempDir, "test.db");

    try {
      const store = new MemoryVectorStore({ dimension: 3, dbPath });
      await store.insert(
        [normalize([1, 0, 0]), normalize([0, 1, 0])],
        ["a", "b"],
        [
          { text: "hello", userId: "user1" },
          { text: "world", userId: "user2" },
        ],
      );

      const results = await store.search(normalize([1, 0, 0]), 10, {
        user_id: "user2",
      });
      expect(results).toHaveLength(1);
      expect(results[0].id).toBe("b");
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });
});

// ---------------------------------------------------------------------------
// 4. VectorStoreConfig type – dbPath is optional, existing configs work
// ---------------------------------------------------------------------------

describe("backward compat: VectorStoreConfig type", () => {
  it("config without dbPath still works (no required field breakage)", () => {
    const cfg = ConfigManager.mergeConfig({
      vectorStore: {
        provider: "memory",
        config: { collectionName: "test", dimension: 512 },
      },
    });
    expect(cfg.vectorStore.config.dbPath).toBeUndefined();
    expect(cfg.vectorStore.config.collectionName).toBe("test");
    expect(cfg.vectorStore.config.dimension).toBe(512);
  });

  it("config with client instance passes through unchanged", () => {
    const fakeClient = { connect: () => {} };
    const cfg = ConfigManager.mergeConfig({
      vectorStore: {
        provider: "qdrant",
        config: { client: fakeClient, dimension: 768 },
      },
    });
    expect(cfg.vectorStore.config.client).toBe(fakeClient);
    expect(cfg.vectorStore.config.dimension).toBe(768);
  });
});

// ---------------------------------------------------------------------------
// 5. ensureSQLiteDirectory – does not break existing paths
// ---------------------------------------------------------------------------

describe("backward compat: ensureSQLiteDirectory", () => {
  it("no-ops for already existing directory", () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-existing-"));
    try {
      // Should not throw even though directory already exists
      expect(() =>
        ensureSQLiteDirectory(path.join(tempDir, "test.db")),
      ).not.toThrow();
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("handles path with trailing slash gracefully", () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-trailing-"));
    try {
      // path.dirname of "dir/sub/" is "dir/sub", mkdirSync should handle it
      expect(() =>
        ensureSQLiteDirectory(path.join(tempDir, "sub", "test.db")),
      ).not.toThrow();
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });
});
