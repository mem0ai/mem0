import { createPool } from "mysql2/promise";
import type { Pool, RowDataPacket } from "mysql2/promise";
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

function cosineSimilarity(a: number[], b: number[]): number {
  let dot = 0;
  let normA = 0;
  let normB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }
  const denom = Math.sqrt(normA) * Math.sqrt(normB);
  return denom === 0 ? 0 : dot / denom;
}

interface AzureMySQLConfig extends VectorStoreConfig {
  host: string;
  port?: number;
  user: string;
  password?: string;
  database: string;
  collectionName: string;
  embeddingModelDims: number;
  useAzureCredential?: boolean;
  sslCa?: string;
  sslDisabled?: boolean;
  maxConn?: number;
}

export class AzureMySQLDB implements VectorStore {
  private pool?: Pool;
  private readonly collectionName: string;
  private readonly config: AzureMySQLConfig;
  private _initPromise?: Promise<void>;

  constructor(config: AzureMySQLConfig) {
    this.collectionName = validateIdentifier(
      config.collectionName || "memories",
      "collectionName",
    );
    this.config = config;
  }

  private col(): string {
    return `\`${this.collectionName}\``;
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    let password = this.config.password;

    if (this.config.useAzureCredential) {
      try {
        const { DefaultAzureCredential } = await import("@azure/identity");
        const credential = new DefaultAzureCredential();
        const token = await credential.getToken(
          "https://ossrdbms-aad.database.windows.net/.default",
        );
        password = token.token;
      } catch (err) {
        throw new Error(`Azure credential authentication failed: ${err}`);
      }
    }

    const ssl: Record<string, any> | undefined = this.config.sslDisabled
      ? undefined
      : {
          rejectUnauthorized: true,
          ...(this.config.sslCa ? { ca: this.config.sslCa } : {}),
        };

    this.pool = createPool({
      host: this.config.host,
      port: this.config.port ?? 3306,
      user: this.config.user,
      password,
      database: this.config.database,
      ssl,
      connectionLimit: this.config.maxConn ?? 5,
      waitForConnections: true,
      ...(this.config.useAzureCredential
        ? {
            authPlugins: {
              mysql_clear_password: () => () =>
                Buffer.from(`${password ?? ""}\0`),
            },
          }
        : {}),
    });

    await this.pool.execute(`
      CREATE TABLE IF NOT EXISTS ${this.col()} (
        id VARCHAR(255) PRIMARY KEY,
        vector JSON,
        payload JSON,
        text_lemmatized VARCHAR(1000) GENERATED ALWAYS AS
          (CAST(JSON_UNQUOTE(JSON_EXTRACT(payload, '$.textLemmatized')) AS CHAR(1000))) STORED
      )
    `);

    try {
      await this.pool.execute(
        `CREATE FULLTEXT INDEX ft_text_lemmatized ON ${this.col()} (text_lemmatized)`,
      );
    } catch {
      // Index may already exist or FULLTEXT may be unsupported; continue silently.
    }

    await this.pool.execute(`
      CREATE TABLE IF NOT EXISTS memory_migrations (
        id INT PRIMARY KEY,
        user_id VARCHAR(255) NOT NULL
      )
    `);
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();
    const conn = await this.pool!.getConnection();
    try {
      await conn.beginTransaction();
      for (let i = 0; i < vectors.length; i++) {
        await conn.execute(
          `INSERT INTO ${this.col()} (id, vector, payload) VALUES (?, ?, ?) AS new
           ON DUPLICATE KEY UPDATE vector = new.vector, payload = new.payload`,
          [ids[i], JSON.stringify(vectors[i]), JSON.stringify(payloads[i])],
        );
      }
      await conn.commit();
    } catch (err) {
      await conn.rollback();
      throw err;
    } finally {
      conn.release();
    }
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();

    const conditions: string[] = [];
    const params: any[] = [];

    if (filters) {
      for (const [k, v] of Object.entries(filters)) {
        conditions.push("JSON_EXTRACT(payload, ?) = ?");
        params.push(`$.${k}`, JSON.stringify(v));
      }
    }

    const whereClause =
      conditions.length > 0 ? "WHERE " + conditions.join(" AND ") : "";
    const sql = `SELECT id, vector, payload FROM ${this.col()} ${whereClause}`;
    const [rows] = await this.pool!.execute<RowDataPacket[]>(sql, params);

    const scored: Array<{ id: string; score: number; payload: any }> = [];
    for (const row of rows) {
      const vec: number[] =
        typeof row.vector === "string" ? JSON.parse(row.vector) : row.vector;
      const score = cosineSimilarity(query, vec);
      const payload =
        typeof row.payload === "string" ? JSON.parse(row.payload) : row.payload;
      scored.push({ id: row.id as string, score, payload });
    }

    scored.sort((a, b) => b.score - a.score);
    return scored.slice(0, topK).map((r) => ({
      id: r.id,
      payload: r.payload,
      score: r.score,
    }));
  }

  async keywordSearch(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    try {
      await this.initialize();

      const conditions: string[] = [];
      const params: any[] = [query, query];

      if (filters) {
        for (const [k, v] of Object.entries(filters)) {
          conditions.push("JSON_EXTRACT(payload, ?) = ?");
          params.push(`$.${k}`, JSON.stringify(v));
        }
      }

      const filterClause =
        conditions.length > 0 ? " AND " + conditions.join(" AND ") : "";
      const sql = `
        SELECT id, payload,
               MATCH(text_lemmatized) AGAINST(? IN NATURAL LANGUAGE MODE) AS score
        FROM ${this.col()}
        WHERE MATCH(text_lemmatized) AGAINST(? IN NATURAL LANGUAGE MODE)
        ${filterClause}
        ORDER BY score DESC
        LIMIT ?
      `;
      params.push(topK);

      const [rows] = await this.pool!.execute<RowDataPacket[]>(sql, params);
      return rows.map((row) => ({
        id: row.id as string,
        payload:
          typeof row.payload === "string"
            ? JSON.parse(row.payload)
            : row.payload,
        score: Number(row.score),
      }));
    } catch {
      return null;
    }
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();
    const [rows] = await this.pool!.execute<RowDataPacket[]>(
      `SELECT id, payload FROM ${this.col()} WHERE id = ?`,
      [vectorId],
    );
    if (rows.length === 0) return null;
    const row = rows[0];
    return {
      id: row.id as string,
      payload:
        typeof row.payload === "string" ? JSON.parse(row.payload) : row.payload,
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();
    const conn = await this.pool!.getConnection();
    try {
      await conn.beginTransaction();
      await conn.execute(
        `UPDATE ${this.col()} SET vector = ?, payload = ? WHERE id = ?`,
        [JSON.stringify(vector), JSON.stringify(payload), vectorId],
      );
      await conn.commit();
    } catch (err) {
      await conn.rollback();
      throw err;
    } finally {
      conn.release();
    }
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();
    await this.pool!.execute(`DELETE FROM ${this.col()} WHERE id = ?`, [
      vectorId,
    ]);
  }

  async deleteCol(): Promise<void> {
    await this.initialize();
    await this.pool!.execute(`DROP TABLE IF EXISTS ${this.col()}`);
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();

    const conditions: string[] = [];
    const params: any[] = [];

    if (filters) {
      for (const [k, v] of Object.entries(filters)) {
        conditions.push("JSON_EXTRACT(payload, ?) = ?");
        params.push(`$.${k}`, JSON.stringify(v));
      }
    }

    const whereClause =
      conditions.length > 0 ? "WHERE " + conditions.join(" AND ") : "";
    const listSql = `SELECT id, payload FROM ${this.col()} ${whereClause} LIMIT ?`;
    const countSql = `SELECT COUNT(*) AS cnt FROM ${this.col()} ${whereClause}`;

    const [rows] = await this.pool!.execute<RowDataPacket[]>(listSql, [
      ...params,
      topK,
    ]);
    const [countRows] = await this.pool!.execute<RowDataPacket[]>(
      countSql,
      params,
    );

    const results: VectorStoreResult[] = rows.map((row) => ({
      id: row.id as string,
      payload:
        typeof row.payload === "string" ? JSON.parse(row.payload) : row.payload,
    }));

    return [results, Number(countRows[0].cnt)];
  }

  async getUserId(): Promise<string> {
    await this.initialize();
    const [rows] = await this.pool!.execute<RowDataPacket[]>(
      "SELECT user_id FROM memory_migrations WHERE id = 1",
    );
    if (rows.length > 0) {
      return rows[0].user_id as string;
    }
    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.pool!.execute(
      "INSERT INTO memory_migrations (id, user_id) VALUES (1, ?) AS new ON DUPLICATE KEY UPDATE user_id = new.user_id",
      [randomUserId],
    );
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();
    await this.pool!.execute(
      "INSERT INTO memory_migrations (id, user_id) VALUES (1, ?) AS new ON DUPLICATE KEY UPDATE user_id = new.user_id",
      [userId],
    );
  }

  async close(): Promise<void> {
    if (this.pool) {
      await this.pool.end();
    }
  }
}
