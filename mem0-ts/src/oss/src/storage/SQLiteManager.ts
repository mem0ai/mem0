import Database from "better-sqlite3";
import { HistoryManager } from "./base";

export class SQLiteManager implements HistoryManager {
  private db: Database.Database;

  constructor(dbPath: string) {
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
    const stmt = this.db.prepare(
      `INSERT INTO memory_history 
      (memory_id, previous_value, new_value, action, created_at, updated_at, is_deleted)
      VALUES (?, ?, ?, ?, ?, ?, ?)`
    );
    stmt.run(
      memoryId,
      previousValue,
      newValue,
      action,
      createdAt,
      updatedAt,
      isDeleted,
    );
  }

  async getHistory(memoryId: string): Promise<any[]> {
    const stmt = this.db.prepare(
      "SELECT * FROM memory_history WHERE memory_id = ? ORDER BY id DESC"
    );
    return stmt.all(memoryId) as any[];
  }

  async reset(): Promise<void> {
    this.db.exec("DROP TABLE IF EXISTS memory_history");
    this.init();
  }

  close(): void {
    this.db.close();
  }
}
