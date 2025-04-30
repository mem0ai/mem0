import { Client, Pool } from "pg";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

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
  private client: Client;
  private collectionName: string;
  private useDiskann: boolean;
  private useHnsw: boolean;
  private readonly dbName: string;
  private config: PGVectorConfig;

  constructor(config: PGVectorConfig) {
    this.collectionName = config.collectionName || "memories";
    this.useDiskann = config.diskann || false;
    this.useHnsw = config.hnsw || false;
    this.dbName = config.dbname || "vector_store";
    this.config = config;

    this.client = new Client({
      database: "postgres", // Initially connect to default postgres database
      user: config.user,
      password: config.password,
      host: config.host,
      port: config.port,
    });
  }

  async initialize(): Promise<void> {
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
    // Create database (cannot be parameterized)
    await this.client.query(`CREATE DATABASE ${dbName}`);
  }

  private async createCol(embeddingModelDims: number): Promise<void> {
    // Create the table
    await this.client.query(`
      CREATE TABLE IF NOT EXISTS ${this.collectionName} (
        id UUID PRIMARY KEY,
        vector vector(${embeddingModelDims}),
        payload JSONB
      );
    `);

    // Create indexes based on configuration
    if (this.useDiskann && embeddingModelDims < 2000) {
      try {
        // Check if vectorscale extension is available
        const result = await this.client.query(
          "SELECT * FROM pg_extension WHERE extname = 'vectorscale'",
        );
        if (result.rows.length > 0) {
          await this.client.query(`
            CREATE INDEX IF NOT EXISTS ${this.collectionName}_diskann_idx
            ON ${this.collectionName}
            USING diskann (vector);
          `);
        }
      } catch (error) {
        console.warn("DiskANN index creation failed:", error);
      }
    } else if (this.useHnsw) {
      try {
        await this.client.query(`
          CREATE INDEX IF NOT EXISTS ${this.collectionName}_hnsw_idx
          ON ${this.collectionName}
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
      vector: `[${vector.join(",")}]`, // Format vector as string with square brackets
      payload: payloads[i],
    }));

    const query = `
      INSERT INTO ${this.collectionName} (id, vector, payload)
      VALUES ($1, $2::vector, $3::jsonb)
    `;

    // Execute inserts in parallel using Promise.all
    await Promise.all(
      values.map((value) =>
        this.client.query(query, [value.id, value.vector, value.payload]),
      ),
    );
  }

  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const filterConditions: string[] = [];
    const queryVector = `[${query.join(",")}]`; // Format query vector as string with square brackets
    const filterValues: any[] = [queryVector, limit];
    let filterIndex = 3;

    if (filters) {
      for (const [key, value] of Object.entries(filters)) {
        filterConditions.push(`payload->>'${key}' = $${filterIndex}`);
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
      FROM ${this.collectionName}
      ${filterClause}
      ORDER BY distance
      LIMIT $2
    `;

    const result = await this.client.query(searchQuery, filterValues);

    return result.rows.map((row) => ({
      id: row.id,
      payload: row.payload,
      score: row.distance,
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const result = await this.client.query(
      `SELECT id, payload FROM ${this.collectionName} WHERE id = $1`,
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
    const vectorStr = `[${vector.join(",")}]`; // Format vector as string with square brackets
    await this.client.query(
      `
      UPDATE ${this.collectionName}
      SET vector = $1::vector, payload = $2::jsonb
      WHERE id = $3
      `,
      [vectorStr, payload, vectorId],
    );
  }

  async delete(vectorId: string): Promise<void> {
    await this.client.query(
      `DELETE FROM ${this.collectionName} WHERE id = $1`,
      [vectorId],
    );
  }

  async deleteCol(): Promise<void> {
    await this.client.query(`DROP TABLE IF EXISTS ${this.collectionName}`);
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
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const filterConditions: string[] = [];
    const filterValues: any[] = [];
    let paramIndex = 1;

    if (filters) {
      for (const [key, value] of Object.entries(filters)) {
        filterConditions.push(`payload->>'${key}' = $${paramIndex}`);
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
      FROM ${this.collectionName}
      ${filterClause}
      LIMIT $${paramIndex}
    `;

    const countQuery = `
      SELECT COUNT(*)
      FROM ${this.collectionName}
      ${filterClause}
    `;

    filterValues.push(limit); // Add limit as the last parameter

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
