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
// Config merging – historyDbPath
// ---------------------------------------------------------------------------

describe("ConfigManager.mergeConfig – historyDbPath handling", () => {
  it("propagates top-level historyDbPath into historyStore.config", () => {
    const cfg = ConfigManager.mergeConfig({
      historyDbPath: "/tmp/custom/history.db",
    });
    expect(cfg.historyDbPath).toBe("/tmp/custom/history.db");
    expect(cfg.historyStore?.provider).toBe("sqlite");
    expect(cfg.historyStore?.config.historyDbPath).toBe(
      "/tmp/custom/history.db",
    );
  });

  it("explicit historyStore.config.historyDbPath takes precedence over top-level", () => {
    const cfg = ConfigManager.mergeConfig({
      historyDbPath: "/tmp/shorthand.db",
      historyStore: {
        provider: "sqlite",
        config: { historyDbPath: "/tmp/explicit.db" },
      },
    });
    expect(cfg.historyStore?.config.historyDbPath).toBe("/tmp/explicit.db");
  });

  it("preserves default memory.db when nothing is provided", () => {
    const cfg = ConfigManager.mergeConfig({});
    expect(cfg.historyStore?.provider).toBe("sqlite");
    expect(cfg.historyStore?.config.historyDbPath).toBe("memory.db");
  });

  it("respects only historyStore.config when top-level is absent", () => {
    const cfg = ConfigManager.mergeConfig({
      historyStore: {
        provider: "sqlite",
        config: { historyDbPath: "/tmp/nested-only.db" },
      },
    });
    expect(cfg.historyStore?.config.historyDbPath).toBe("/tmp/nested-only.db");
  });

  it("does not leak historyDbPath into non-sqlite providers", () => {
    const cfg = ConfigManager.mergeConfig({
      historyDbPath: "/tmp/should-not-apply.db",
      historyStore: {
        provider: "supabase",
        config: {
          supabaseUrl: "https://x.supabase.co",
          supabaseKey: "key",
        },
      },
    });
    expect(cfg.historyStore?.provider).toBe("supabase");
    expect(cfg.historyStore?.config.historyDbPath).toBeUndefined();
  });

  it("disableHistory does not prevent historyStore config from merging", () => {
    const cfg = ConfigManager.mergeConfig({
      disableHistory: true,
      historyDbPath: "/tmp/disabled.db",
    });
    expect(cfg.disableHistory).toBe(true);
    expect(cfg.historyStore?.config.historyDbPath).toBe("/tmp/disabled.db");
  });
});

// ---------------------------------------------------------------------------
// SQLiteManager – directory creation & DB operations
// ---------------------------------------------------------------------------

describe("SQLiteManager – directory auto-creation", () => {
  it("creates nested parent directories and writes to the DB", async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-sqlite-"));
    const dbPath = path.join(tempDir, "a", "b", "c", "history.db");
    let manager: SQLiteManager | undefined;

    try {
      manager = new SQLiteManager(dbPath);
      await manager.addHistory("mem-1", null, "test value", "ADD");
      const history = await manager.getHistory("mem-1");

      expect(fs.existsSync(dbPath)).toBe(true);
      expect(history).toHaveLength(1);
      expect(history[0].new_value).toBe("test value");
    } finally {
      manager?.close();
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("end-to-end: mergeConfig + SQLiteManager at configured path", async () => {
    const tempDir = fs.mkdtempSync(
      path.join(os.tmpdir(), "mem0-history-path-"),
    );
    const historyDbPath = path.join(tempDir, "nested", "history.db");
    let manager: SQLiteManager | undefined;

    try {
      const mergedConfig = ConfigManager.mergeConfig({ historyDbPath });

      manager = new SQLiteManager(
        mergedConfig.historyStore!.config.historyDbPath!,
      );
      await manager.addHistory("memory-1", null, "remember me", "ADD");

      expect(fs.existsSync(historyDbPath)).toBe(true);
    } finally {
      manager?.close();
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("works with :memory: without attempting directory creation", () => {
    const manager = new SQLiteManager(":memory:");
    expect(manager).toBeDefined();
    manager.close();
  });
});

// ---------------------------------------------------------------------------
// MemoryVectorStore – path handling
// ---------------------------------------------------------------------------

describe("MemoryVectorStore – path handling", () => {
  const originalCwd = process.cwd();

  afterEach(() => {
    process.chdir(originalCwd);
    jest.restoreAllMocks();
  });

  it("uses ~/.mem0/vector_store.db by default", () => {
    const fakeHome = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-home-"));
    try {
      jest.spyOn(os, "homedir").mockReturnValue(fakeHome);
      new MemoryVectorStore({ dimension: 4 });
      expect(
        fs.existsSync(path.join(fakeHome, ".mem0", "vector_store.db")),
      ).toBe(true);
    } finally {
      fs.rmSync(fakeHome, { recursive: true, force: true });
    }
  });

  it("respects explicit dbPath config", async () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-vs-"));
    const dbPath = path.join(tempDir, "custom", "vectors.db");

    try {
      const store = new MemoryVectorStore({ dimension: 4, dbPath });
      await store.insert(
        [normalize([1, 0, 0, 0])],
        ["v1"],
        [{ text: "hello" }],
      );

      expect(fs.existsSync(dbPath)).toBe(true);
      const results = await store.search(normalize([1, 0, 0, 0]), 1);
      expect(results).toHaveLength(1);
      expect(results[0].payload.text).toBe("hello");
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("works when CWD is read-only", async () => {
    const fakeHome = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-home-"));
    const readOnlyCwd = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-ro-"));

    try {
      fs.chmodSync(readOnlyCwd, 0o555);
      jest.spyOn(os, "homedir").mockReturnValue(fakeHome);
      process.chdir(readOnlyCwd);

      const store = new MemoryVectorStore({ dimension: 4 });
      await store.insert(
        [normalize([0, 1, 0, 0])],
        ["v2"],
        [{ text: "works" }],
      );

      expect(
        fs.existsSync(path.join(fakeHome, ".mem0", "vector_store.db")),
      ).toBe(true);
      expect(fs.existsSync(path.join(readOnlyCwd, "vector_store.db"))).toBe(
        false,
      );
    } finally {
      fs.chmodSync(readOnlyCwd, 0o755);
      fs.rmSync(fakeHome, { recursive: true, force: true });
      fs.rmSync(readOnlyCwd, { recursive: true, force: true });
    }
  });

  it("emits migration warning when old CWD-based vector_store.db exists", () => {
    const fakeHome = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-home-"));
    const tempCwd = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-cwd-"));

    try {
      fs.writeFileSync(path.join(tempCwd, "vector_store.db"), "");
      jest.spyOn(os, "homedir").mockReturnValue(fakeHome);
      const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
      process.chdir(tempCwd);

      new MemoryVectorStore({ dimension: 4 });

      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining("Default vector_store.db location changed"),
      );
    } finally {
      fs.rmSync(fakeHome, { recursive: true, force: true });
      fs.rmSync(tempCwd, { recursive: true, force: true });
    }
  });

  it("does NOT emit migration warning when dbPath is explicitly set", () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-vs-"));
    const tempCwd = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-cwd-"));

    try {
      fs.writeFileSync(path.join(tempCwd, "vector_store.db"), "");
      const warnSpy = jest.spyOn(console, "warn").mockImplementation(() => {});
      process.chdir(tempCwd);

      new MemoryVectorStore({
        dimension: 4,
        dbPath: path.join(tempDir, "explicit.db"),
      });

      expect(warnSpy).not.toHaveBeenCalled();
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
      fs.rmSync(tempCwd, { recursive: true, force: true });
    }
  });
});

// ---------------------------------------------------------------------------
// Utils
// ---------------------------------------------------------------------------

describe("ensureSQLiteDirectory", () => {
  it("creates nested directories", () => {
    const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-ensure-"));
    const target = path.join(tempDir, "x", "y", "z", "test.db");
    try {
      ensureSQLiteDirectory(target);
      expect(fs.existsSync(path.join(tempDir, "x", "y", "z"))).toBe(true);
    } finally {
      fs.rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("skips :memory:", () => {
    expect(() => ensureSQLiteDirectory(":memory:")).not.toThrow();
  });

  it("skips file: URIs", () => {
    expect(() => ensureSQLiteDirectory("file::memory:")).not.toThrow();
  });

  it("skips empty string", () => {
    expect(() => ensureSQLiteDirectory("")).not.toThrow();
  });
});

describe("getDefaultVectorStoreDbPath", () => {
  it("returns path under homedir/.mem0", () => {
    const result = getDefaultVectorStoreDbPath();
    expect(result).toBe(path.join(os.homedir(), ".mem0", "vector_store.db"));
  });
});
