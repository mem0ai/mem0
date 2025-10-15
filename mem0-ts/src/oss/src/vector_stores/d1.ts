// packages/mem0-ts/src/history/providers/d1.ts
// Minimal Cloudflare D1 provider for mem0 historyStore

import type { D1Database } from '@cloudflare/workers-types'; // dev-time types only
// Replace Path/Types below with actual mem0 HistoryStore types
type MemoryEntry = {
  id: string;
  user_id?: string;
  memory: string;
  metadata?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
};

type D1ProviderConfig = {
  // any provider-specific config here (tableName etc.)
  tableName?: string;
};

export class D1HistoryProvider {
  db: D1Database;
  table: string;

  constructor(db: D1Database, config?: D1ProviderConfig) {
    this.db = db;
    this.table = config?.tableName ?? 'mem0_history';
  }

  // helper: create table if not exists (call from init/migrations)
  async ensureTable() {
    const q = `
      CREATE TABLE IF NOT EXISTS ${this.table} (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        memory TEXT,
        metadata TEXT,
        created_at TEXT,
        updated_at TEXT
      );
    `;
    await this.db.prepare(q).run();
  }

  // Add entries (simple implementation)
  async add(entries: MemoryEntry[] | MemoryEntry) {
    const list = Array.isArray(entries) ? entries : [entries];
    const tx = this.db;
    // Use individual inserts (D1 does not support explicit transactions API)
    for (const e of list) {
      const metadata = e.metadata ? JSON.stringify(e.metadata) : null;
      await tx
        .prepare(
          `INSERT INTO ${this.table} (id, user_id, memory, metadata, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET memory = excluded.memory, metadata = excluded.metadata, updated_at = excluded.updated_at;`
        )
        .bind(e.id, e.user_id ?? null, e.memory, metadata, e.created_at ?? new Date().toISOString(), e.updated_at ?? new Date().toISOString())
        .run();
    }
    return { success: true, inserted: list.length };
  }

  async get(id: string) {
    const res = await this.db.prepare(`SELECT * FROM ${this.table} WHERE id = ?`).bind(id).all();
    const row = res.results?.[0] ?? null;
    return row ? this._rowToEntry(row) : null;
  }

  async delete(id: string) {
    await this.db.prepare(`DELETE FROM ${this.table} WHERE id = ?`).bind(id).run();
    return { success: true };
  }

  async update(id: string, changes: Partial<MemoryEntry>) {
    const cur = await this.get(id);
    if (!cur) throw new Error('not found');
    const updated = { ...cur, ...changes, updated_at: new Date().toISOString() };
    const metadata = updated.metadata ? JSON.stringify(updated.metadata) : null;
    await this.db
      .prepare(`UPDATE ${this.table} SET memory = ?, metadata = ?, updated_at = ? WHERE id = ?`)
      .bind(updated.memory, metadata, updated.updated_at, id)
      .run();
    return this._rowToEntry((await this.db.prepare(`SELECT * FROM ${this.table} WHERE id = ?`).bind(id).all()).results?.[0]);
  }

  // Very simple search (full-text search would be better if supported)
  async search(query: string, opts?: { userId?: string; limit?: number }) {
    const q = `SELECT * FROM ${this.table} WHERE memory LIKE ? ${opts?.userId ? 'AND user_id = ?' : ''} ORDER BY created_at DESC LIMIT ?`;
    const like = `%${query}%`;
    const bindArgs = opts?.userId ? [like, opts.userId, opts.limit ?? 10] : [like, opts?.limit ?? 10];
    const res = await this.db.prepare(q).bind(...bindArgs).all();
    const rows = res.results ?? [];
    return rows.map(this._rowToEntry);
  }

  async reset() {
    await this.db.prepare(`DELETE FROM ${this.table}`).run();
    return { success: true };
  }

  _rowToEntry(row: any): MemoryEntry {
    return {
      id: row.id,
      user_id: row.user_id,
      memory: row.memory,
      metadata: row.metadata ? JSON.parse(row.metadata) : undefined,
      created_at: row.created_at,
      updated_at: row.updated_at,
    };
  }
}
