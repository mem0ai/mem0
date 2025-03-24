import sqlite3 from "sqlite3";
import { HistoryManager } from "./base";

export class SQLiteManager implements HistoryManager {
  private db: sqlite3.Database;

  constructor(dbPath: string) {
    this.db = new sqlite3.Database(dbPath);
    this.init().catch(console.error);
  }

  private async init() {
    await this.run(`
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

  private async run(sql: string, params: any[] = []): Promise<void> {
    return new Promise((resolve, reject) => {
      this.db.run(sql, params, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }

  private async all(sql: string, params: any[] = []): Promise<any[]> {
    return new Promise((resolve, reject) => {
      this.db.all(sql, params, (err, rows) => {
        if (err) reject(err);
        else resolve(rows);
      });
    });
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
    await this.run(
      `INSERT INTO memory_history 
      (memory_id, previous_value, new_value, action, created_at, updated_at, is_deleted)
      VALUES (?, ?, ?, ?, ?, ?, ?)`,
      [
        memoryId,
        previousValue,
        newValue,
        action,
        createdAt,
        updatedAt,
        isDeleted,
      ],
    );
  }

  async getHistory(memoryId: string): Promise<any[]> {
    return this.all(
      "SELECT * FROM memory_history WHERE memory_id = ? ORDER BY id DESC",
      [memoryId],
    );
  }

  async reset(): Promise<void> {
    await this.run("DROP TABLE IF EXISTS memory_history");
    await this.init();
  }

  close(): void {
    this.db.close();
  }
}
