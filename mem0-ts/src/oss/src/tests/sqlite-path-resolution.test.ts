import fs from "fs";
import os from "os";
import path from "path";
import { ConfigManager } from "../config/manager";
import { SQLiteManager } from "../storage/SQLiteManager";
import { MemoryVectorStore } from "../vector_stores/memory";

function normalize(vector: number[]): number[] {
  const norm = Math.sqrt(vector.reduce((sum, value) => sum + value * value, 0));
  return vector.map((value) => value / norm);
}

describe("SQLite path resolution", () => {
  const originalCwd = process.cwd();

  afterEach(() => {
    process.chdir(originalCwd);
    jest.restoreAllMocks();
  });

  it("propagates top-level historyDbPath into the sqlite history store config", async () => {
    const tempDir = fs.mkdtempSync(
      path.join(os.tmpdir(), "mem0-history-path-"),
    );
    const historyDbPath = path.join(tempDir, "nested", "history.db");
    let manager: SQLiteManager | undefined;

    try {
      const mergedConfig = ConfigManager.mergeConfig({ historyDbPath });

      expect(mergedConfig.historyDbPath).toBe(historyDbPath);
      expect(mergedConfig.historyStore?.provider).toBe("sqlite");
      expect(mergedConfig.historyStore?.config.historyDbPath).toBe(
        historyDbPath,
      );

      // Verify the DB is actually created at the configured path
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

  it("explicit historyStore.config.historyDbPath takes precedence over top-level historyDbPath", () => {
    const mergedConfig = ConfigManager.mergeConfig({
      historyDbPath: "/path/from/shorthand.db",
      historyStore: {
        provider: "sqlite",
        config: { historyDbPath: "/path/from/explicit.db" },
      },
    });

    expect(mergedConfig.historyStore?.config.historyDbPath).toBe(
      "/path/from/explicit.db",
    );
  });

  it("uses default memory.db when neither historyDbPath nor historyStore is provided", () => {
    const mergedConfig = ConfigManager.mergeConfig({});

    expect(mergedConfig.historyStore?.provider).toBe("sqlite");
    expect(mergedConfig.historyStore?.config.historyDbPath).toBe("memory.db");
  });

  it("defaults the memory vector store dbPath to ~/.mem0/vector_store.db", async () => {
    const fakeHomeDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-home-"));
    const tempCwd = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-cwd-"));
    const expectedDbPath = path.join(fakeHomeDir, ".mem0", "vector_store.db");

    try {
      jest.spyOn(os, "homedir").mockReturnValue(fakeHomeDir);
      process.chdir(tempCwd);

      const store = new MemoryVectorStore({ dimension: 4 });
      await store.insert(
        [normalize([1, 0, 0, 0])],
        ["vector-1"],
        [{ data: "hello" }],
      );

      expect(fs.existsSync(expectedDbPath)).toBe(true);
      expect(fs.existsSync(path.join(tempCwd, "vector_store.db"))).toBe(false);
    } finally {
      fs.rmSync(fakeHomeDir, { recursive: true, force: true });
      fs.rmSync(tempCwd, { recursive: true, force: true });
    }
  });

  it("does not depend on a writable current working directory for the default vector store db", async () => {
    const fakeHomeDir = fs.mkdtempSync(path.join(os.tmpdir(), "mem0-home-"));
    const readOnlyCwd = fs.mkdtempSync(
      path.join(os.tmpdir(), "mem0-readonly-cwd-"),
    );
    const expectedDbPath = path.join(fakeHomeDir, ".mem0", "vector_store.db");

    try {
      fs.chmodSync(readOnlyCwd, 0o555);
      jest.spyOn(os, "homedir").mockReturnValue(fakeHomeDir);
      process.chdir(readOnlyCwd);

      const store = new MemoryVectorStore({ dimension: 4 });
      await store.insert(
        [normalize([0, 1, 0, 0])],
        ["vector-2"],
        [{ data: "hello again" }],
      );

      expect(fs.existsSync(expectedDbPath)).toBe(true);
      expect(fs.existsSync(path.join(readOnlyCwd, "vector_store.db"))).toBe(
        false,
      );
    } finally {
      fs.chmodSync(readOnlyCwd, 0o755);
      fs.rmSync(fakeHomeDir, { recursive: true, force: true });
      fs.rmSync(readOnlyCwd, { recursive: true, force: true });
    }
  });
});
