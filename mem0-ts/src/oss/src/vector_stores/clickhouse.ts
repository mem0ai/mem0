import { createClient, ClickHouseClient } from "@clickhouse/client";
import { SearchFilters, VectorStoreResult, VectorStoreConfig } from "../types";
import { VectorStore } from "./base";
import { v4 as uuidv4 } from "uuid";

export class ClickhouseDB implements VectorStore {
  private client: ClickHouseClient;
  private collectionName: string;

  constructor(config: VectorStoreConfig) {
    this.collectionName = config.collectionName || "mem0";
    
    // Support either passing a client instance directly, or config parameters
    if (config.client) {
      this.client = config.client;
    } else {
      const host = config.host || "localhost";
      const port = config.port || 8123;
      const username = config.username || "default";
      const password = config.password || "";
      const protocol = config.protocol || "http";
      
      const url = `${protocol}://${host}:${port}`;
      this.client = createClient({
        url,
        username,
        password,
        ...config.clickhouseConfig,
      });
    }
  }

  private _parseFilters(filters?: SearchFilters): string {
    if (!filters) return "";
    
    const conditions: string[] = [];
    for (const [key, value] of Object.entries(filters)) {
      if (typeof value === "object") {
        // Advanced filters handling could be added here
      } else if (typeof value === "string") {
        const val = value.replace(/'/g, "''");
        conditions.push(`JSONExtractString(payload, '${key}') = '${val}'`);
      } else if (typeof value === "number") {
        conditions.push(`JSONExtractFloat(payload, '${key}') = ${value}`);
      } else if (typeof value === "boolean") {
        const val = value ? 1 : 0;
        conditions.push(`JSONExtractBool(payload, '${key}') = ${val}`);
      }
    }

    return conditions.length > 0 ? conditions.join(" AND ") : "";
  }

  async initialize(): Promise<void> {
    await this.createCol();
  }

  async getUserId(): Promise<string> {
    return "ClickhouseDB";
  }

  async setUserId(userId: string): Promise<void> {
    // Not applicable
  }

  async createCol(): Promise<void> {
    const query = `
      CREATE TABLE IF NOT EXISTS ${this.collectionName} (
        id String,
        vector Array(Float32),
        payload String
      ) ENGINE = MergeTree()
      ORDER BY id
    `;
    await this.client.command({ query });
  }

  async insert(
    vectors: number[][],
    ids?: string[],
    payloads?: Record<string, any>[]
  ): Promise<void> {
    const currentIds = ids || vectors.map(() => uuidv4());
    const currentPayloads = payloads || vectors.map(() => ({}));

    const rows = vectors.map((vector, i) => ({
      id: currentIds[i],
      vector: vector,
      payload: JSON.stringify(currentPayloads[i]),
    }));

    await this.client.insert({
      table: this.collectionName,
      values: rows,
      format: "JSONEachRow",
    });
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters
  ): Promise<VectorStoreResult[]> {
    const whereClause = this._parseFilters(filters);
    const whereSql = whereClause ? `WHERE ${whereClause}` : "";
    
    // ClickHouse uses string representation for arrays in queries, 
    // or we could use query parameters. Using query parameters is safer.
    
    const sql = `
      SELECT id, 
             1.0 - cosineDistance(vector, {vector:Array(Float32)}) as score, 
             payload
      FROM ${this.collectionName}
      ${whereSql}
      ORDER BY score DESC
      LIMIT ${topK}
    `;

    const result = await this.client.query({
      query: sql,
      query_params: {
        vector: query,
      },
      format: "JSONEachRow",
    });

    const rows: any[] = await result.json();
    return rows.map((row) => ({
      id: row.id,
      score: row.score,
      payload: row.payload ? JSON.parse(row.payload) : null,
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const sql = `SELECT id, vector, payload FROM ${this.collectionName} WHERE id = {id:String} LIMIT 1`;
    const result = await this.client.query({
      query: sql,
      query_params: {
        id: vectorId,
      },
      format: "JSONEachRow",
    });

    const rows: any[] = await result.json();
    if (rows.length === 0) return null;

    const row = rows[0];
    return {
      id: row.id,
      payload: row.payload ? JSON.parse(row.payload) : null,
    };
  }

  async update(
    vectorId: string,
    vector?: number[],
    payload?: Record<string, any>
  ): Promise<void> {
    if (vector) {
      await this.client.command({
        query: `ALTER TABLE ${this.collectionName} UPDATE vector = {vector:Array(Float32)} WHERE id = {id:String}`,
        query_params: {
          vector: vector,
          id: vectorId,
        },
      });
    }

    if (payload) {
      await this.client.command({
        query: `ALTER TABLE ${this.collectionName} UPDATE payload = {payload:String} WHERE id = {id:String}`,
        query_params: {
          payload: JSON.stringify(payload),
          id: vectorId,
        },
      });
    }
  }

  async delete(vectorId: string): Promise<void> {
    await this.client.command({
      query: `ALTER TABLE ${this.collectionName} DELETE WHERE id = {id:String}`,
      query_params: {
        id: vectorId,
      },
    });
  }

  async deleteCol(): Promise<void> {
    await this.client.command({
      query: `DROP TABLE IF EXISTS ${this.collectionName}`,
    });
  }

  async listCols(): Promise<string[]> {
    const result = await this.client.query({
      query: "SHOW TABLES",
      format: "JSONEachRow",
    });
    const rows: any[] = await result.json();
    return rows.map((r) => Object.values(r)[0] as string);
  }

  async colInfo(): Promise<{ name: string; count: number }> {
    try {
      const result = await this.client.query({
        query: `SELECT count() as count FROM ${this.collectionName}`,
        format: "JSONEachRow",
      });
      const rows: any[] = await result.json();
      const count = rows.length > 0 ? Number(rows[0].count) : 0;
      return { name: this.collectionName, count };
    } catch (e) {
      return { name: this.collectionName, count: 0 };
    }
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100
  ): Promise<[VectorStoreResult[], number]> {
    const whereClause = this._parseFilters(filters);
    const whereSql = whereClause ? `WHERE ${whereClause}` : "";
    
    const countSql = `SELECT count() as count FROM ${this.collectionName} ${whereSql}`;
    const countResult = await this.client.query({
      query: countSql,
      format: "JSONEachRow",
    });
    const countRows: any[] = await countResult.json();
    const count = countRows.length > 0 ? Number(countRows[0].count) : 0;

    const sql = `SELECT id, payload FROM ${this.collectionName} ${whereSql} LIMIT ${topK}`;
    const result = await this.client.query({
      query: sql,
      format: "JSONEachRow",
    });

    const rows: any[] = await result.json();
    const results = rows.map((row) => ({
      id: row.id,
      payload: row.payload ? JSON.parse(row.payload) : null,
    }));

    return [results, count];
  }
}
