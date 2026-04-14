import fs from "fs";
import os from "os";
import path from "path";

export function getDefaultVectorStoreDbPath(collectionName?: string): string {
  // Scope the default DB file by collection name so that parallel stores
  // (e.g. "memories" vs "memories_entities") don't collide in the same
  // SQLite table. Without this, both collections write to the same
  // `vectors` table and search results leak across them.
  const filename =
    collectionName && collectionName.length > 0
      ? `vector_store_${collectionName.replace(/[^a-zA-Z0-9_-]/g, "_")}.db`
      : "vector_store.db";
  return path.join(os.homedir(), ".mem0", filename);
}

export function ensureSQLiteDirectory(dbPath: string): void {
  if (!dbPath || dbPath === ":memory:" || dbPath.startsWith("file:")) {
    return;
  }

  fs.mkdirSync(path.dirname(dbPath), { recursive: true });
}
