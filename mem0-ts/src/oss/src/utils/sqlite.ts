import type Database from "better-sqlite3";
import fs from "fs";
import os from "os";
import path from "path";
import { loadPeer } from "./load_peer";

export function getDefaultVectorStoreDbPath(): string {
  return path.join(os.homedir(), ".mem0", "vector_store.db");
}

export function ensureSQLiteDirectory(dbPath: string): void {
  if (!dbPath || dbPath === ":memory:" || dbPath.startsWith("file:")) {
    return;
  }

  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
}

// better-sqlite3 is a native addon. Load it only when a SQLite-backed store is first used, so
// importing mem0ai/oss never binds it on runtimes that cannot (#3291).
export async function openSQLiteDatabase(
  dbPath: string,
  label: string,
): Promise<Database.Database> {
  const sqlite = await loadPeer(
    "better-sqlite3",
    label,
    () => import("better-sqlite3"),
  );
  const BetterSqlite3 = sqlite.default ?? sqlite;
  ensureSQLiteDirectory(dbPath);
  return new BetterSqlite3(dbPath);
}
