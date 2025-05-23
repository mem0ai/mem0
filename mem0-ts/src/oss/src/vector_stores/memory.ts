import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
import sqlite3 from "sqlite3";
import path from "path";

interface MemoryVector {
  id: string;
  vector: number[];
  payload: Record<string, any>;
}

export class MemoryVectorStore implements VectorStore {
  private db: sqlite3.Database;
  private dimension: number;
  private dbPath: string;

  constructor(config: VectorStoreConfig) {
    this.dimension = config.dimension || 1536; // Default OpenAI dimension
    this.dbPath = path.join(process.cwd(), "vector_store.db");
    if (config.dbPath) {
      this.dbPath = config.dbPath;
    }
    this.db = new sqlite3.Database(this.dbPath);
    this.init().catch(console.error);
  }

  private async init() {
    await this.run(`
      CREATE TABLE IF NOT EXISTS vectors (
        id TEXT PRIMARY KEY,
        vector BLOB NOT NULL,
        payload TEXT NOT NULL
      )
    `);

    await this.run(`
      CREATE TABLE IF NOT EXISTS memory_migrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL UNIQUE
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

  private async getOne(sql: string, params: any[] = []): Promise<any> {
    return new Promise((resolve, reject) => {
      this.db.get(sql, params, (err, row) => {
        if (err) reject(err);
        else resolve(row);
      });
    });
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
    for (let i = 0; i < vectors.length; i++) {
      if (vectors[i].length !== this.dimension) {
        throw new Error(
          `Vector dimension mismatch. Expected ${this.dimension}, got ${vectors[i].length}`,
        );
      }
      const vectorBuffer = Buffer.from(new Float32Array(vectors[i]).buffer);
      await this.run(
        `INSERT OR REPLACE INTO vectors (id, vector, payload) VALUES (?, ?, ?)`,
        [ids[i], vectorBuffer, JSON.stringify(payloads[i])],
      );
    }
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

    const rows = await this.all(`SELECT * FROM vectors`);
    const results: VectorStoreResult[] = [];

    for (const row of rows) {
      const vector = new Float32Array(row.vector.buffer);
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
    const row = await this.getOne(`SELECT * FROM vectors WHERE id = ?`, [
      vectorId,
    ]);
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
    await this.run(`UPDATE vectors SET vector = ?, payload = ? WHERE id = ?`, [
      vectorBuffer,
      JSON.stringify(payload),
      vectorId,
    ]);
  }

  async delete(vectorId: string): Promise<void> {
    await this.run(`DELETE FROM vectors WHERE id = ?`, [vectorId]);
  }

  async deleteCol(): Promise<void> {
    await this.run(`DROP TABLE IF EXISTS vectors`);
    await this.init();
  }

  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const rows = await this.all(`SELECT * FROM vectors`);
    const results: VectorStoreResult[] = [];

    for (const row of rows) {
      const payload = JSON.parse(row.payload);
      const memoryVector: MemoryVector = {
        id: row.id,
        vector: Array.from(new Float32Array(row.vector.buffer)),
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
    const row = await this.getOne(
      `SELECT user_id FROM memory_migrations LIMIT 1`,
    );
    if (row) {
      return row.user_id;
    }

    // Generate a random user_id if none exists
    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.run(`INSERT INTO memory_migrations (user_id) VALUES (?)`, [
      randomUserId,
    ]);
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.run(`DELETE FROM memory_migrations`);
    await this.run(`INSERT INTO memory_migrations (user_id) VALUES (?)`, [
      userId,
    ]);
  }

  async initialize(): Promise<void> {
    await this.init();
  }
}
