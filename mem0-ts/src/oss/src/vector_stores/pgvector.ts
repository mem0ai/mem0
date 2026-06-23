import type { Client as ClientType, ClientConfig } from "pg";
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

interface FilterResult {
  conditions: string[];
  values: any[];
  paramIndex: number;
}

const OPERATOR_SQL_MAP: Record<string, { template: string; numeric: boolean }> =
  {
    eq: { template: "payload->>'%KEY%' = $%IDX%", numeric: false },
    ne: { template: "payload->>'%KEY%' != $%IDX%", numeric: false },
    gt: { template: "(payload->>'%KEY%')::numeric > $%IDX%", numeric: true },
    gte: { template: "(payload->>'%KEY%')::numeric >= $%IDX%", numeric: true },
    lt: { template: "(payload->>'%KEY%')::numeric < $%IDX%", numeric: true },
    lte: { template: "(payload->>'%KEY%')::numeric <= $%IDX%", numeric: true },
    in: { template: "payload->>'%KEY%' = ANY($%IDX%::text[])", numeric: false },
    nin: {
      template: "NOT (payload->>'%KEY%' = ANY($%IDX%::text[]))",
      numeric: false,
    },
    contains: {
      template: "payload->>'%KEY%' LIKE $%IDX% ESCAPE '\\'",
      numeric: false,
    },
    icontains: {
      template: "payload->>'%KEY%' ILIKE $%IDX% ESCAPE '\\'",
      numeric: false,
    },
  };

export function buildFilterConditions(
  filters: Record<string, any> | undefined,
  startIndex: number,
): FilterResult {
  const conditions: string[] = [];
  const values: any[] = [];
  let paramIndex = startIndex;

  if (!filters) {
    return { conditions, values, paramIndex };
  }

  for (const [key, value] of Object.entries(filters)) {
    if (key === "$or") {
      const orGroups: string[] = [];
      for (const orFilter of value as Record<string, any>[]) {
        const sub = buildFilterConditions(orFilter, paramIndex);
        if (sub.conditions.length > 0) {
          orGroups.push("(" + sub.conditions.join(" AND ") + ")");
          values.push(...sub.values);
          paramIndex = sub.paramIndex;
        }
      }
      if (orGroups.length > 0) {
        conditions.push("(" + orGroups.join(" OR ") + ")");
      }
      continue;
    }

    if (key === "$not") {
      const notGroups: string[] = [];
      for (const notFilter of value as Record<string, any>[]) {
        const sub = buildFilterConditions(notFilter, paramIndex);
        if (sub.conditions.length > 0) {
          notGroups.push("(" + sub.conditions.join(" AND ") + ")");
          values.push(...sub.values);
          paramIndex = sub.paramIndex;
        }
      }
      if (notGroups.length > 0) {
        conditions.push("NOT (" + notGroups.join(" OR ") + ")");
      }
      continue;
    }

    const safeKey = escapeFilterKey(key);

    if (value === "*") {
      conditions.push(`payload ? $${paramIndex}`);
      values.push(key);
      paramIndex++;
      continue;
    }

    if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      for (const [op, opValue] of Object.entries(value)) {
        const mapping = OPERATOR_SQL_MAP[op];
        if (!mapping) {
          throw new Error(`Unsupported filter operator: ${op}`);
        }
        const clause = mapping.template
          .replace("%KEY%", safeKey)
          .replace("%IDX%", String(paramIndex));
        conditions.push(clause);

        if (op === "in" || op === "nin") {
          values.push((opValue as any[]).map(String));
        } else if (op === "contains" || op === "icontains") {
          const escaped = String(opValue)
            .replace(/\\/g, "\\\\")
            .replace(/%/g, "\\%")
            .replace(/_/g, "\\_");
          values.push(`%${escaped}%`);
        } else if (mapping.numeric) {
          values.push(Number(opValue));
        } else {
          values.push(String(opValue));
        }
        paramIndex++;
      }
    } else if (Array.isArray(value)) {
      conditions.push(`payload->>'${safeKey}' = ANY($${paramIndex}::text[])`);
      values.push(value.map(String));
      paramIndex++;
    } else {
      conditions.push(`payload->>'${safeKey}' = $${paramIndex}`);
      if (typeof value === "boolean") {
        values.push(JSON.stringify(value));
      } else {
        values.push(String(value));
      }
      paramIndex++;
    }
  }

  return { conditions, values, paramIndex };
}

interface PGVectorConfig extends VectorStoreConfig {
  dbname?: string;
  user?: string;
  password?: string;
  host?: string;
  port?: number;
  connectionString?: string;
  ssl?: ClientConfig["ssl"];
  embeddingModelDims: number;
  diskann?: boolean;
  hnsw?: boolean;
}

function getConnectionString(config: PGVectorConfig): string | undefined {
  return config.connectionString?.trim() || undefined;
}

function validateConnectionConfig(config: PGVectorConfig): void {
  if (getConnectionString(config)) {
    return;
  }

  const missingFields = ["user", "password", "host", "port"].filter(
    (field) => config[field as keyof PGVectorConfig] === undefined,
  );

  if (missingFields.length > 0) {
    throw new Error(
      `PGVector requires either connectionString or ${missingFields.join(", ")}`,
    );
  }
}

function buildClientConfig(
  config: PGVectorConfig,
  database?: string,
): ClientConfig {
  const connectionString = getConnectionString(config);
  if (connectionString) {
    return {
      connectionString,
      ...(config.ssl !== undefined ? { ssl: config.ssl } : {}),
    };
  }

  return {
    database,
    user: config.user,
    password: config.password,
    host: config.host,
    port: config.port,
    ...(config.ssl !== undefined ? { ssl: config.ssl } : {}),
  };
}

export class PGVector implements VectorStore {
  private client: ClientType;
  private collectionName: string;
  private useDiskann: boolean;
  private useHnsw: boolean;
  private readonly dbName: string;
  private readonly useDirectConnection: boolean;
  private config: PGVectorConfig;
  private _initPromise?: Promise<void>;

  constructor(config: PGVectorConfig) {
    validateConnectionConfig(config);
    this.collectionName = validateIdentifier(
      config.collectionName || "memories",
      "collectionName",
    );
    this.useDiskann = config.diskann || false;
    this.useHnsw = config.hnsw || false;
    this.useDirectConnection = !!getConnectionString(config);
    this.dbName = this.useDirectConnection
      ? ""
      : validateIdentifier(config.dbname || "vector_store", "dbname");
    this.config = config;

    this.client = new Client(
      buildClientConfig(
        config,
        this.useDirectConnection ? undefined : "postgres",
      ),
    );
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

      if (!this.useDirectConnection) {
        const dbExists = await this.checkDatabaseExists(this.dbName);
        if (!dbExists) {
          await this.createDatabase(this.dbName);
        }

        await this.client.end();

        this.client = new Client(buildClientConfig(this.config, this.dbName));
        await this.client.connect();
      }

      await this.client.query("CREATE EXTENSION IF NOT EXISTS vector");

      await this.client.query(`
        CREATE TABLE IF NOT EXISTS memory_migrations (
          id SERIAL PRIMARY KEY,
          user_id TEXT NOT NULL UNIQUE
        )
      `);

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
      const {
        conditions,
        values,
        paramIndex: _,
      } = buildFilterConditions(filters, 3);
      const filterValues: any[] = [query, topK, ...values];

      const filterClause =
        conditions.length > 0 ? "AND " + conditions.join(" AND ") : "";

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
    const queryVector = `[${query.join(",")}]`;
    const {
      conditions,
      values,
      paramIndex: _,
    } = buildFilterConditions(filters, 3);
    const filterValues: any[] = [queryVector, topK, ...values];

    const filterClause =
      conditions.length > 0 ? "WHERE " + conditions.join(" AND ") : "";

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
    const {
      conditions,
      values: filterValues,
      paramIndex,
    } = buildFilterConditions(filters, 1);

    const filterClause =
      conditions.length > 0 ? "WHERE " + conditions.join(" AND ") : "";

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

    const listValues = [...filterValues, topK];

    const [listResult, countResult] = await Promise.all([
      this.client.query(listQuery, listValues),
      this.client.query(countQuery, filterValues),
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
