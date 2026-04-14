import Database from "better-sqlite3";
import { randomUUID } from "crypto";
import { HistoryManager } from "./base";
import { ensureSQLiteDirectory } from "../utils/sqlite";

export class SQLiteManager implements HistoryManager {
  private db: Database.Database;
  private stmtInsert!: Database.Statement;
  private stmtSelect!: Database.Statement;

  constructor(dbPath: string) {
    ensureSQLiteDirectory(dbPath);
    this.db = new Database(dbPath);
    this.init();
  }

  private init(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS memory_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_id TEXT NOT NULL,
        previous_value TEXT,
        new_value TEXT,
        action TEXT NOT NULL,
        created_at TEXT,
        updated_at TEXT,
        is_deleted INTEGER DEFAULT 0
      )
    `);
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        session_scope TEXT,
        role TEXT,
        content TEXT,
        name TEXT,
        created_at TEXT
      )
    `);
    this.stmtInsert = this.db.prepare(
      `INSERT INTO memory_history
      (memory_id, previous_value, new_value, action, created_at, updated_at, is_deleted)
      VALUES (?, ?, ?, ?, ?, ?, ?)`,
    );
    this.stmtSelect = this.db.prepare(
      "SELECT * FROM memory_history WHERE memory_id = ? ORDER BY id DESC",
    );
  }

  async addHistory(
    memoryId: string,
    previousValue: string | null,
    newValue: string | null,
    action: string,
    createdAt?: string,
    updatedAt?: string,
    isDeleted: number = 0,
  ): Promise<void> {
    this.stmtInsert.run(
      memoryId,
      previousValue,
      newValue,
      action,
      createdAt ?? null,
      updatedAt ?? null,
      isDeleted,
    );
  }

  async getHistory(memoryId: string): Promise<any[]> {
    return this.stmtSelect.all(memoryId) as any[];
  }

  async saveMessages(
    messages: Array<{ role: string; content: string; name?: string }>,
    sessionScope: string,
  ): Promise<void> {
    if (!messages.length) return;

    const insertMsg = this.db.prepare(
      `INSERT INTO messages (id, session_scope, role, content, name, created_at)
       VALUES (?, ?, ?, ?, ?, ?)`,
    );
    const evict = this.db.prepare(
      `DELETE FROM messages WHERE session_scope = ? AND id NOT IN (
         SELECT id FROM (
           SELECT id FROM messages WHERE session_scope = ? ORDER BY created_at DESC LIMIT 10
         )
       )`,
    );

    const txn = this.db.transaction(() => {
      const now = new Date().toISOString();
      for (const msg of messages) {
        insertMsg.run(
          randomUUID(),
          sessionScope,
          msg.role,
          msg.content,
          msg.name ?? null,
          now,
        );
      }
      evict.run(sessionScope, sessionScope);
    });

    txn();
  }

  async getLastMessages(
    sessionScope: string,
    limit = 10,
  ): Promise<
    Array<{ role: string; content: string; name?: string; createdAt: string }>
  > {
    const rows = this.db
      .prepare(
        `SELECT role, content, name, created_at FROM (
           SELECT role, content, name, created_at
           FROM messages
           WHERE session_scope = ?
           ORDER BY created_at DESC
           LIMIT ?
         ) ORDER BY created_at ASC`,
      )
      .all(sessionScope, limit) as Array<{
      role: string;
      content: string;
      name: string | null;
      created_at: string;
    }>;

    return rows.map((r) => ({
      role: r.role,
      content: r.content,
      ...(r.name != null ? { name: r.name } : {}),
      createdAt: r.created_at,
    }));
  }

  async batchAddHistory(
    records: Array<{
      memoryId: string;
      previousValue: string | null;
      newValue: string | null;
      action: string;
      createdAt?: string;
      updatedAt?: string;
      isDeleted?: number;
    }>,
  ): Promise<void> {
    const txn = this.db.transaction(() => {
      for (const record of records) {
        this.stmtInsert.run(
          record.memoryId,
          record.previousValue,
          record.newValue,
          record.action,
          record.createdAt ?? null,
          record.updatedAt ?? null,
          record.isDeleted ?? 0,
        );
      }
    });
    txn();
  }

  async reset(): Promise<void> {
    this.db.exec("DROP TABLE IF EXISTS memory_history");
    this.db.exec("DROP TABLE IF EXISTS messages");
    this.init();
  }

  close(): void {
    this.db.close();
  }
}
