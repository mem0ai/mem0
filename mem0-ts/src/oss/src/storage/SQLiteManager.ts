import { HistoryManager } from "./base";
import { ensureSQLiteDirectory } from "../utils/sqlite";
import { loadOptionalDependency } from "../utils/optional-deps";

export class SQLiteManager implements HistoryManager {
  private db: any;
  private stmtInsert!: any;
  private stmtSelect!: any;

  constructor(dbPath: string) {
    ensureSQLiteDirectory(dbPath);
    const Database = loadOptionalDependency<any>(
      "better-sqlite3",
      "sqlite history store",
    );
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

  async reset(): Promise<void> {
    this.db.exec("DROP TABLE IF EXISTS memory_history");
    this.init();
  }

  close(): void {
    this.db.close();
  }
}
