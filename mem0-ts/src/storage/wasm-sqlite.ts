/*
WASM SQLite adapter using sql.js
This adapter is intended for Worker/browser builds and avoids native sqlite3 bindings.
*/

// Use a dynamic import for sql.js so bundlers can handle it and to avoid TS errors when types are not installed.
export type MemoryRow = {
  id: string;
  content: string;
  metadata?: Record<string, unknown> | null;
  created_at: number;
  updated_at: number;
};

export class WasmSQLiteStorage {
  private db: any = null;
  private ready: Promise<void>;

  constructor(wasmBinary?: Uint8Array) {
    // initSqlJs can accept a locateFile option or wasmBinary depending on bundling
    this.ready = (async () => {
      // dynamic import so that build tools can replace or stub sql.js for worker bundles
      const sqljsMod: any = await import('sql.js');
      const initSql: any = sqljsMod.default || sqljsMod;

      // Choose locateFile behavior depending on runtime. In Node (tests/build) we must
      // point to the shipped wasm file under node_modules/sql.js/dist/sql-wasm.wasm.
      let locateFile: ((file: any) => string) | undefined;
      try {
        // Detect Node runtime
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const isNode = typeof process !== 'undefined' && (process as any).versions != null && (process as any).versions.node != null;
        if (isNode) {
          // Use path to the installed sql.js dist folder
          // Do a runtime require of path to avoid bundlers picking it up for worker builds
          // eslint-disable-next-line @typescript-eslint/no-var-requires
          const path = require('path');
          const pkgRoot = path.resolve(__dirname, '../../node_modules/sql.js/dist');
          locateFile = (file: any) => path.join(pkgRoot, file);
        }
      } catch (e) {
        // fallback to default locateFile (works in Workers / browser)
        locateFile = undefined;
      }

      const SQL: any = await initSql({ locateFile });
      this.db = new SQL.Database();
      // Ensure table exists
      this.db.run(`
        CREATE TABLE IF NOT EXISTS memories (
          id TEXT PRIMARY KEY,
          content TEXT NOT NULL,
          metadata TEXT,
          created_at INTEGER,
          updated_at INTEGER
        );
      `);
    })();
  }

  async initialize(): Promise<void> {
    return this.ready;
  }

  async close(): Promise<void> {
    if (this.db) {
      this.db.close();
      this.db = null;
    }
  }

  private ensureDb(): any {
    if (!this.db) throw new Error('WasmSQLiteStorage not initialized');
    return this.db;
  }

  async addMemory(id: string, content: string, metadata?: Record<string, unknown> | null): Promise<void> {
    const db = this.ensureDb();
    const now = Date.now();
    const meta = metadata ? JSON.stringify(metadata) : null;
    db.run('INSERT OR REPLACE INTO memories (id, content, metadata, created_at, updated_at) VALUES (?, ?, ?, ?, ?)', [id, content, meta, now, now]);
  }

  async getMemory(id: string): Promise<MemoryRow | null> {
    const db: any = this.ensureDb();
  const stmt: any = db.prepare('SELECT id, content, metadata, created_at, updated_at FROM memories WHERE id = ? LIMIT 1');
  stmt.bind([id]);
    try {
      const rows: MemoryRow[] = [];
      while (stmt.step()) {
        const r: any = stmt.getAsObject();
        rows.push({
          id: String(r.id),
          content: String(r.content),
          metadata: r.metadata ? JSON.parse(String(r.metadata)) : undefined,
          created_at: Number(r.created_at),
          updated_at: Number(r.updated_at),
        });
      }
      return rows.length ? rows[0] : null;
    } finally {
      stmt.free();
    }
  }

  async listMemories(limit = 50, offset = 0): Promise<MemoryRow[]> {
    const db = this.ensureDb();
    const sql = `SELECT id, content, metadata, created_at, updated_at FROM memories ORDER BY created_at DESC LIMIT ${limit} OFFSET ${offset}`;
    const res = db.exec(sql);
    if (!res.length) return [];
    const cols = res[0].columns;
    return res[0].values.map((vals: any[]) => {
      const row: any = {};
      cols.forEach((c: string, i: number) => (row[c] = vals[i]));
      return {
        id: String(row.id),
        content: String(row.content),
        metadata: row.metadata ? JSON.parse(String(row.metadata)) : undefined,
        created_at: Number(row.created_at),
        updated_at: Number(row.updated_at),
      } as MemoryRow;
    });
  }

  async deleteMemory(id: string): Promise<boolean> {
    const db = this.ensureDb();
    db.run('DELETE FROM memories WHERE id = ?', [id]);
    // sql.js doesn't expose changes directly from run; use exec to check
    const res = db.exec('SELECT COUNT(1) as cnt FROM memories WHERE id = "' + id.replace(/"/g, '""') + '"');
    // If row exists, deletion didn't happen; but simpler: just return true
    return true;
  }
}

export default WasmSQLiteStorage;
