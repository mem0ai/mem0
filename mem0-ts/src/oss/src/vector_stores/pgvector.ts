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
  // Connection pool and retry options
  maxConnections?: number;
  connectionTimeoutMs?: number;
  idleTimeoutMs?: number;
  maxRetries?: number;
  retryDelayMs?: number;
  retryBackoffFactor?: number;
}

export class PGVector implements VectorStore {
  private client: Pool;
  private collectionName: string;
  private useDiskann: boolean;
  private useHnsw: boolean;
  private readonly dbName: string;
  private config: PGVectorConfig;
  private initializationPromise: Promise<void>;
  private isInitialized: boolean = false;

  constructor(config: PGVectorConfig) {
    this.collectionName = config.collectionName || "memories";
    this.useDiskann = config.diskann || false;
    this.useHnsw = config.hnsw || false;
    this.dbName = config.dbname || "vector_store";
    this.config = config;

    // Initialize pool (will be recreated during initialization for target database)
    this.client = this.createPool("postgres");
    
    // Start initialization immediately but don't block constructor
    this.initializationPromise = this.initialize();
  }

  private createPool(database: string): Pool {
    const client = new Pool({
      database,
      user: this.config.user,
      password: this.config.password,
      host: this.config.host,
      port: this.config.port,
      max: this.config.maxConnections || 10,
      connectionTimeoutMillis: this.config.connectionTimeoutMs || 30000,
      idleTimeoutMillis: this.config.idleTimeoutMs || 10000,
    });

    client.on("error", (err) => {
      console.error("Postgres connection error:", err);
      console.error("Trying to restore Postgres connection");
      this.isInitialized = false;
      this.initializationPromise = this.initialize();
    });

    return client;
  }

  private async executeWithRetry<T>(
    operation: () => Promise<T>,
    operationName: string = "database operation"
  ): Promise<T> {
    const maxRetries = this.config.maxRetries || 3;
    const baseDelay = this.config.retryDelayMs || 1000;
    const backoffFactor = this.config.retryBackoffFactor || 2;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        return await operation();
      } catch (error) {
        const isLastAttempt = attempt === maxRetries;
        
        if (isLastAttempt) {
          console.error(`${operationName} failed after ${maxRetries} attempts:`, error);
          throw error;
        }

        const delay = baseDelay * Math.pow(backoffFactor, attempt - 1);
        console.warn(`${operationName} failed (attempt ${attempt}/${maxRetries}), retrying in ${delay}ms:`, error);

        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }

    // This should never be reached, but TypeScript requires it
    throw new Error(`Unexpected error in retry logic for ${operationName}`);
  }

  async initialize(): Promise<void> {
    if (this.isInitialized) {
      return;
    }
    console.log("Initializing database");
    await this.executeWithRetry(async () => {
      // Check if database exists
      const dbExists = await this.checkDatabaseExists(this.dbName);
      if (!dbExists) {
        await this.createDatabase(this.dbName);
      }

      // Close the current pool and create a new one for the target database
      await this.client.end();
      this.client = this.createPool(this.dbName);

      // Test connection to the target database
      const client = await this.client.connect();
      try {
        // Create vector extension
        await client.query("CREATE EXTENSION IF NOT EXISTS vector");

        // Create memory_migrations table
        await client.query(`
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
      } finally {
        client.release();
      }
    }, "Database initialization");
    this.isInitialized = true;
  }

  async waitForInitialization(): Promise<void> {
    await this.initializationPromise;
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
    await this.client.query(`CREATE DATABASE IF NOT EXISTS ${dbName}`);
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
    await this.initializationPromise;
    await this.executeWithRetry(async () => {
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
    }, "Insert operation");
  }

  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initializationPromise;
    return await this.executeWithRetry(async () => {
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

      return result.rows.map((row: any) => ({
        id: row.id,
        payload: row.payload,
        score: row.distance,
      }));
    }, "Search operation");
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initializationPromise;
    return await this.executeWithRetry(async () => {
      const result = await this.client.query(
        `SELECT id, payload FROM ${this.collectionName} WHERE id = $1`,
        [vectorId],
      );

      if (result.rows.length === 0) return null;

      return {
        id: result.rows[0].id,
        payload: result.rows[0].payload,
      };
    }, "Get operation");
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initializationPromise;
    await this.executeWithRetry(async () => {
      const vectorStr = `[${vector.join(",")}]`; // Format vector as string with square brackets
      await this.client.query(
        `
        UPDATE ${this.collectionName}
        SET vector = $1::vector, payload = $2::jsonb
        WHERE id = $3
        `,
        [vectorStr, payload, vectorId],
      );
    }, "Update operation");
  }

  async delete(vectorId: string): Promise<void> {
    await this.initializationPromise;
    await this.executeWithRetry(async () => {
      await this.client.query(
        `DELETE FROM ${this.collectionName} WHERE id = $1`,
        [vectorId],
      );
    }, "Delete operation");
  }

  async deleteCol(): Promise<void> {
    await this.initializationPromise;
    await this.executeWithRetry(async () => {
      await this.client.query(`DROP TABLE IF EXISTS ${this.collectionName}`);
    }, "Delete collection operation");
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
    await this.initializationPromise;
    return await this.executeWithRetry(async () => {
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
    }, "List operation");
  }

  async close(): Promise<void> {
    await this.client.end();
  }

  async getUserId(): Promise<string> {
    await this.initializationPromise;
    return await this.executeWithRetry(async () => {
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
    }, "Get user ID operation");
  }

  async setUserId(userId: string): Promise<void> {
    await this.initializationPromise;
    await this.executeWithRetry(async () => {
      await this.client.query("DELETE FROM memory_migrations");
      await this.client.query(
        "INSERT INTO memory_migrations (user_id) VALUES ($1)",
        [userId],
      );
    }, "Set user ID operation");
  }
}
