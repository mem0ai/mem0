import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
import Database from "better-sqlite3";
import path from "path";

interface MemoryVector {
  id: string;
  vector: number[];
  payload: Record<string, any>;
}

export class MemoryVectorStore implements VectorStore {
  private db: Database.Database;
  private dimension: number;
  private dbPath: string;

  constructor(config: VectorStoreConfig) {
    this.dimension = config.dimension || 1536; // Default OpenAI dimension
    this.dbPath = path.join(process.cwd(), "vector_store.db");
    if (config.dbPath) {
      this.dbPath = config.dbPath;
    }
    this.db = new Database(this.dbPath);
    this.init();
  }

  private init(): void {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS vectors (
        id TEXT PRIMARY KEY,
        vector BLOB NOT NULL,
        payload TEXT NOT NULL
      )
    `);

    this.db.exec(`
      CREATE TABLE IF NOT EXISTS memory_migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL UNIQUE
      )
    `);
  }

  private cosineSimilarity(a: number[], b: number[]): number {
    let dotProduct = 0;
    let normA = 0;
    let normB = 0;
    for (let i = 0; i < a.length; i++) {
      dotProduct += a[i] * b[i];
      normA += a[i] * a[i];
      normB += b[i] * b[i];
    }
    return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
  }

  private filterVector(vector: MemoryVector, filters?: SearchFilters): boolean {
    if (!filters) return true;
    return Object.entries(filters).every(
      ([key, value]) => vector.payload[key] === value,
    );
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const stmt = this.db.prepare(
      `INSERT OR REPLACE INTO vectors (id, vector, payload) VALUES (?, ?, ?)`,
    );
    const insertMany = this.db.transaction(
      (vecs: number[][], vIds: string[], vPayloads: Record<string, any>[]) => {
        for (let i = 0; i < vecs.length; i++) {
          if (vecs[i].length !== this.dimension) {
            throw new Error(
              `Vector dimension mismatch. Expected ${this.dimension}, got ${vecs[i].length}`,
            );
          }
          const vectorBuffer = Buffer.from(new Float32Array(vecs[i]).buffer);
          stmt.run(vIds[i], vectorBuffer, JSON.stringify(vPayloads[i]));
        }
      },
    );
    insertMany(vectors, ids, payloads);
  }

  async search(
    query: number[],
    limit: number = 10,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    if (query.length !== this.dimension) {
      throw new Error(
        `Query dimension mismatch. Expected ${this.dimension}, got ${query.length}`,
      );
    }

    const rows = this.db.prepare(`SELECT * FROM vectors`).all() as any[];
    const results: VectorStoreResult[] = [];

    for (const row of rows) {
      const vector = new Float32Array(
        row.vector.buffer,
        row.vector.byteOffset,
        row.vector.byteLength / 4,
      );
      const payload = JSON.parse(row.payload);
      const memoryVector: MemoryVector = {
        id: row.id,
        vector: Array.from(vector),
        payload,
      };

      if (this.filterVector(memoryVector, filters)) {
        const score = this.cosineSimilarity(query, Array.from(vector));
        results.push({
          id: memoryVector.id,
          payload: memoryVector.payload,
          score,
        });
      }
    }

    results.sort((a, b) => (b.score || 0) - (a.score || 0));
    return results.slice(0, limit);
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const row = this.db
      .prepare(`SELECT * FROM vectors WHERE id = ?`)
      .get(vectorId) as any;
    if (!row) return null;

    const payload = JSON.parse(row.payload);
    return {
      id: row.id,
      payload,
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    if (vector.length !== this.dimension) {
      throw new Error(
        `Vector dimension mismatch. Expected ${this.dimension}, got ${vector.length}`,
      );
    }
    const vectorBuffer = Buffer.from(new Float32Array(vector).buffer);
    this.db
      .prepare(`UPDATE vectors SET vector = ?, payload = ? WHERE id = ?`)
      .run(vectorBuffer, JSON.stringify(payload), vectorId);
  }

  async delete(vectorId: string): Promise<void> {
    this.db.prepare(`DELETE FROM vectors WHERE id = ?`).run(vectorId);
  }

  async deleteCol(): Promise<void> {
    this.db.exec(`DROP TABLE IF EXISTS vectors`);
    this.init();
  }

  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const rows = this.db.prepare(`SELECT * FROM vectors`).all() as any[];
    const results: VectorStoreResult[] = [];

    for (const row of rows) {
      const payload = JSON.parse(row.payload);
      const memoryVector: MemoryVector = {
        id: row.id,
        vector: Array.from(
          new Float32Array(
            row.vector.buffer,
            row.vector.byteOffset,
            row.vector.byteLength / 4,
          ),
        ),
        payload,
      };

      if (this.filterVector(memoryVector, filters)) {
        results.push({
          id: memoryVector.id,
          payload: memoryVector.payload,
        });
      }
    }

    return [results.slice(0, limit), results.length];
  }

  async getUserId(): Promise<string> {
    const row = this.db
      .prepare(`SELECT user_id FROM memory_migrations LIMIT 1`)
      .get() as any;
    if (row) {
      return row.user_id;
    }

    // Generate a random user_id if none exists
    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    this.db
      .prepare(`INSERT INTO memory_migrations (user_id) VALUES (?)`)
      .run(randomUserId);
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    this.db.prepare(`DELETE FROM memory_migrations`).run();
    this.db
      .prepare(`INSERT INTO memory_migrations (user_id) VALUES (?)`)
      .run(userId);
  }

  async initialize(): Promise<void> {
    this.init();
  }
}
