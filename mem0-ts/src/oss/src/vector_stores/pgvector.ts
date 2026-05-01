import type { Client as ClientType } from "pg";
import pkg from "pg";
const { Client, escapeIdentifier } = pkg;
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

const SAFE_IDENTIFIER_RE = /^[a-zA-Z_][a-zA-Z0-9_]{0,127}$/;

function validateIdentifier(
  name: string,
  label: string = "identifier",
): string {
  if (!SAFE_IDENTIFIER_RE.test(name)) {
    throw new Error(
      `Invalid ${label} '${name}': only letters, digits, and underscores are allowed, ` +
        `must start with a letter or underscore, and be at most 128 characters.`,
    );
  }
  return name;
}

function escapeFilterKey(key: string): string {
  if (!SAFE_IDENTIFIER_RE.test(key)) {
    throw new Error(
      `Invalid filter key '${key}': only letters, digits, and underscores are allowed.`,
    );
  }
  return key;
}

interface PGVectorConfig extends VectorStoreConfig {
  dbname?: string;
  user: string;
  password: string;
  host: string;
  port: number;
  embeddingModelDims: number;
  diskann?: boolean;
  hnsw?: boolean;
}

export class PGVector implements VectorStore {
  private client: ClientType;
  private collectionName: string;
  private useDiskann: boolean;
  private useHnsw: boolean;
  private readonly dbName: string;
  private config: PGVectorConfig;
  private _initPromise?: Promise<void>;

  constructor(config: PGVectorConfig) {
    this.collectionName = validateIdentifier(
      config.collectionName || "memories",
      "collectionName",
    );
    this.useDiskann = config.diskann || false;
    this.useHnsw = config.hnsw || false;
    this.dbName = validateIdentifier(config.dbname || "vector_store", "dbname");
    this.config = config;

    this.client = new Client({
      database: "postgres", // Initially connect to default postgres database
      user: config.user,
      password: config.password,
      host: config.host,
      port: config.port,
    });
    this.initialize().catch(console.error);
  }

  private col(): string {
    return escapeIdentifier(this.collectionName);
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    try {
      await this.client.connect();

      // Check if database exists
      const dbExists = await this.checkDatabaseExists(this.dbName);
      if (!dbExists) {
        await this.createDatabase(this.dbName);
      }

      // Disconnect from postgres database
      await this.client.end();

      // Connect to the target database
      this.client = new Client({
        database: this.dbName,
        user: this.config.user,
        password: this.config.password,
        host: this.config.host,
        port: this.config.port,
      });
      await this.client.connect();

      // Create vector extension
      await this.client.query("CREATE EXTENSION IF NOT EXISTS vector");

      // Create memory_migrations table
      await this.client.query(`
        CREATE TABLE IF NOT EXISTS memory_migrations (
          id SERIAL PRIMARY KEY,
          user_id TEXT NOT NULL UNIQUE
        )
      `);

      // Check if the collection exists
      const collections = await this.listCols();
      if (!collections.includes(this.collectionName)) {
        await this.createCol(this.config.embeddingModelDims);
      }
    } catch (error) {
      console.error("Error during initialization:", error);
      throw error;
    }
  }

  private async checkDatabaseExists(dbName: string): Promise<boolean> {
    const result = await this.client.query(
      "SELECT 1 FROM pg_database WHERE datname = $1",
      [dbName],
    );
    return result.rows.length > 0;
  }

  private async createDatabase(dbName: string): Promise<void> {
    await this.client.query(`CREATE DATABASE ${escapeIdentifier(dbName)}`);
  }

  private async createCol(embeddingModelDims: number): Promise<void> {
    const dims = Math.floor(embeddingModelDims);
    await this.client.query(`
      CREATE TABLE IF NOT EXISTS ${this.col()} (
        id UUID PRIMARY KEY,
        vector vector(${dims}),
        payload JSONB
      );
    `);

    if (this.useDiskann && embeddingModelDims < 2000) {
      try {
        const result = await this.client.query(
          "SELECT * FROM pg_extension WHERE extname = 'vectorscale'",
        );
        if (result.rows.length > 0) {
          await this.client.query(`
            CREATE INDEX IF NOT EXISTS ${escapeIdentifier(this.collectionName + "_diskann_idx")}
            ON ${this.col()}
            USING diskann (vector);
          `);
        }
      } catch (error) {
        console.warn("DiskANN index creation failed:", error);
      }
    } else if (this.useHnsw) {
      try {
        await this.client.query(`
          CREATE INDEX IF NOT EXISTS ${escapeIdentifier(this.collectionName + "_hnsw_idx")}
          ON ${this.col()}
          USING hnsw (vector vector_cosine_ops);
        `);
      } catch (error) {
        console.warn("HNSW index creation failed:", error);
      }
    }
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const values = vectors.map((vector, i) => ({
      id: ids[i],
      vector: `[${vector.join(",")}]`,
      payload: payloads[i],
    }));

    const query = `
      INSERT INTO ${this.col()} (id, vector, payload)
      VALUES ($1, $2::vector, $3::jsonb)
    `;

    await Promise.all(
      values.map((value) =>
        this.client.query(query, [value.id, value.vector, value.payload]),
      ),
    );
  }

  async keywordSearch(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    try {
      const filterConditions: string[] = [];
      const filterValues: any[] = [query, topK];
      let filterIndex = 3;

      if (filters) {
        for (const [key, value] of Object.entries(filters)) {
          const safeKey = escapeFilterKey(key);
          filterConditions.push(`payload->>'${safeKey}' = $${filterIndex}`);
          filterValues.push(value);
          filterIndex++;
        }
      }

      const filterClause =
        filterConditions.length > 0
          ? "AND " + filterConditions.join(" AND ")
          : "";

      const searchQuery = `
        SELECT id, ts_rank_cd(to_tsvector('simple', payload->>'textLemmatized'), plainto_tsquery('simple', $1)) AS score, payload
        FROM ${this.col()}
        WHERE to_tsvector('simple', payload->>'textLemmatized') @@ plainto_tsquery('simple', $1)
        ${filterClause}
        ORDER BY score DESC
        LIMIT $2
      `;

      const result = await this.client.query(searchQuery, filterValues);

      return result.rows.map((row) => ({
        id: row.id,
        payload: row.payload,
        score: row.score,
      }));
    } catch (error) {
      console.error("Error during keyword search:", error);
      return null;
    }
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const filterConditions: string[] = [];
    const queryVector = `[${query.join(",")}]`;
    const filterValues: any[] = [queryVector, topK];
    let filterIndex = 3;

    if (filters) {
      for (const [key, value] of Object.entries(filters)) {
        const safeKey = escapeFilterKey(key);
        filterConditions.push(`payload->>'${safeKey}' = $${filterIndex}`);
        filterValues.push(value);
        filterIndex++;
      }
    }

    const filterClause =
      filterConditions.length > 0
        ? "WHERE " + filterConditions.join(" AND ")
        : "";

    const searchQuery = `
      SELECT id, vector <=> $1::vector AS distance, payload
      FROM ${this.col()}
      ${filterClause}
      ORDER BY distance
      LIMIT $2
    `;

    const result = await this.client.query(searchQuery, filterValues);

    return result.rows.map((row) => ({
      id: row.id,
      payload: row.payload,
      score: Math.max(0, Math.min(1, 1 - Number(row.distance))),
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const result = await this.client.query(
      `SELECT id, payload FROM ${this.col()} WHERE id = $1`,
      [vectorId],
    );

    if (result.rows.length === 0) return null;

    return {
      id: result.rows[0].id,
      payload: result.rows[0].payload,
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const vectorStr = `[${vector.join(",")}]`;
    await this.client.query(
      `
      UPDATE ${this.col()}
      SET vector = $1::vector, payload = $2::jsonb
      WHERE id = $3
      `,
      [vectorStr, payload, vectorId],
    );
  }

  async delete(vectorId: string): Promise<void> {
    await this.client.query(`DELETE FROM ${this.col()} WHERE id = $1`, [
      vectorId,
    ]);
  }

  async deleteCol(): Promise<void> {
    await this.client.query(`DROP TABLE IF EXISTS ${this.col()}`);
  }

  private async listCols(): Promise<string[]> {
    const result = await this.client.query(`
      SELECT table_name
      FROM information_schema.tables
      WHERE table_schema = 'public'
    `);
    return result.rows.map((row) => row.table_name);
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const filterConditions: string[] = [];
    const filterValues: any[] = [];
    let paramIndex = 1;

    if (filters) {
      for (const [key, value] of Object.entries(filters)) {
        const safeKey = escapeFilterKey(key);
        filterConditions.push(`payload->>'${safeKey}' = $${paramIndex}`);
        filterValues.push(value);
        paramIndex++;
      }
    }

    const filterClause =
      filterConditions.length > 0
        ? "WHERE " + filterConditions.join(" AND ")
        : "";

    const listQuery = `
      SELECT id, payload
      FROM ${this.col()}
      ${filterClause}
      LIMIT $${paramIndex}
    `;

    const countQuery = `
      SELECT COUNT(*)
      FROM ${this.col()}
      ${filterClause}
    `;

    filterValues.push(topK); // Add limit as the last parameter

    const [listResult, countResult] = await Promise.all([
      this.client.query(listQuery, filterValues),
      this.client.query(countQuery, filterValues.slice(0, -1)), // Remove limit parameter for count query
    ]);

    const results = listResult.rows.map((row) => ({
      id: row.id,
      payload: row.payload,
    }));

    return [results, parseInt(countResult.rows[0].count)];
  }

  async close(): Promise<void> {
    await this.client.end();
  }

  async getUserId(): Promise<string> {
    const result = await this.client.query(
      "SELECT user_id FROM memory_migrations LIMIT 1",
    );

    if (result.rows.length > 0) {
      return result.rows[0].user_id;
    }

    // Generate a random user_id if none exists
    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.client.query(
      "INSERT INTO memory_migrations (user_id) VALUES ($1)",
      [randomUserId],
    );
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.client.query("DELETE FROM memory_migrations");
    await this.client.query(
      "INSERT INTO memory_migrations (user_id) VALUES ($1)",
      [userId],
    );
  }
}
