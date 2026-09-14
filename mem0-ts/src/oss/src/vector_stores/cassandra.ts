import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
import { loadPeer } from "../utils/load_peer";

const MIGRATION_ROW_ID = "mem0-user";
const SAFE_IDENTIFIER_RE = /^[A-Za-z_][A-Za-z0-9_]{0,127}$/;

interface CassandraConfig extends VectorStoreConfig {
  contactPoints?: string[];
  port?: number;
  username?: string;
  password?: string;
  keyspace?: string;
  collectionName?: string;
  embeddingModelDims?: number;
  secureConnectBundle?: string;
  localDataCenter?: string;
  protocolVersion?: number;
  loadBalancingPolicy?: any;
  client?: CassandraClientLike;
  /** Pre-configured Cassandra driver module (typed as `any` to keep the
   *  optional driver's types out of the published type declarations). */
  driver?: any;
}

interface CassandraClientLike {
  connect?(): Promise<void>;
  execute(
    query: string,
    params?: any[],
    options?: Record<string, any>,
  ): Promise<{ rows?: any[]; pageState?: string | null }>;
}

interface CassandraVector {
  id: string;
  vector: number[];
  payload: Record<string, any>;
}

export class CassandraDB implements VectorStore {
  private static readonly PAGE_SIZE = 500;
  private readonly driver?: any;
  private readonly contactPoints?: string[];
  private readonly port: number;
  private readonly username?: string;
  private readonly password?: string;
  private readonly keyspace: string;
  private readonly collectionName: string;
  private readonly dimension: number;
  private readonly secureConnectBundle?: string;
  private readonly localDataCenter?: string;
  private readonly protocolVersion?: number;
  private readonly loadBalancingPolicy?: any;
  private client?: CassandraClientLike;
  private _initPromise?: Promise<void>;

  constructor(config: CassandraConfig) {
    this.driver = config.driver;
    this.contactPoints = config.contactPoints;
    this.port = config.port || 9042;
    this.username = config.username;
    this.password = config.password;
    this.keyspace = this.validateIdentifier(
      config.keyspace || "mem0",
      "keyspace",
    );
    this.collectionName = this.validateIdentifier(
      config.collectionName || "memories",
      "collectionName",
    );
    this.dimension = config.embeddingModelDims || config.dimension || 1536;
    this.secureConnectBundle = config.secureConnectBundle;
    this.localDataCenter = config.localDataCenter;
    this.protocolVersion = config.protocolVersion;
    this.loadBalancingPolicy = config.loadBalancingPolicy;
    this.client = config.client;
    this.initialize().catch(console.error);
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    if (!this.client) {
      this.client = await this.createClient();
    }
    if (typeof this.client.connect === "function") {
      await this.client.connect();
    }

    await this.client.execute(`
      CREATE KEYSPACE IF NOT EXISTS ${this.keyspace}
      WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
    `);

    await this.client.execute(`
      CREATE TABLE IF NOT EXISTS ${this.keyspace}.${this.collectionName} (
        id text PRIMARY KEY,
        vector list<float>,
        payload text
      )
    `);

    await this.client.execute(`
      CREATE TABLE IF NOT EXISTS ${this.keyspace}.memory_migrations (
        id text PRIMARY KEY,
        user_id text
      )
    `);
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();
    this.assertBatchDimensions(vectors, "Vector");

    const query = `
      INSERT INTO ${this.keyspace}.${this.collectionName} (id, vector, payload)
      VALUES (?, ?, ?)
    `;

    for (let index = 0; index < vectors.length; index += 1) {
      await this.client!.execute(
        query,
        [ids[index], vectors[index], JSON.stringify(payloads[index] || {})],
        { prepare: true },
      );
    }
  }

  async keywordSearch(): Promise<null> {
    return null;
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();
    this.assertVectorDimension(query, "Query");

    const scored: VectorStoreResult[] = [];
    await this.scanRows(
      `
        SELECT id, vector, payload
        FROM ${this.keyspace}.${this.collectionName}
      `,
      async (row) => {
        const vector = this.normalizeVector(row.vector);
        const payload = this.parsePayload(row.payload);
        if (!vector || vector.length !== this.dimension) {
          return;
        }
        const item: CassandraVector = {
          id: String(row.id),
          vector,
          payload,
        };
        if (!this.filterVector(item, filters)) {
          return;
        }
        this.pushTopResult(
          scored,
          {
            id: item.id,
            payload: item.payload,
            score: this.cosineSimilarity(query, item.vector),
          },
          topK,
        );
      },
      Math.max(topK, CassandraDB.PAGE_SIZE),
    );

    return scored;
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();

    const result = await this.client!.execute(
      `
        SELECT id, payload
        FROM ${this.keyspace}.${this.collectionName}
        WHERE id = ?
      `,
      [vectorId],
      { prepare: true },
    );

    const row = result.rows?.[0];
    if (!row) {
      return null;
    }

    return {
      id: String(row.id),
      payload: this.parsePayload(row.payload),
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();
    this.assertVectorDimension(vector, "Vector");

    await this.client!.execute(
      `
        INSERT INTO ${this.keyspace}.${this.collectionName} (id, vector, payload)
        VALUES (?, ?, ?)
      `,
      [vectorId, vector, JSON.stringify(payload || {})],
      { prepare: true },
    );
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();

    await this.client!.execute(
      `
        DELETE FROM ${this.keyspace}.${this.collectionName}
        WHERE id = ?
      `,
      [vectorId],
      { prepare: true },
    );
  }

  async deleteCol(): Promise<void> {
    await this.initialize();

    await this.client!.execute(`
      DROP TABLE IF EXISTS ${this.keyspace}.${this.collectionName}
    `);
    await this.client!.execute(`
      CREATE TABLE IF NOT EXISTS ${this.keyspace}.${this.collectionName} (
        id text PRIMARY KEY,
        vector list<float>,
        payload text
      )
    `);
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();

    const rows: VectorStoreResult[] = [];
    let total = 0;
    await this.scanRows(
      `
        SELECT id, payload
        FROM ${this.keyspace}.${this.collectionName}
      `,
      async (row) => {
        const item: CassandraVector = {
          id: String(row.id),
          vector: [],
          payload: this.parsePayload(row.payload),
        };
        if (!this.filterVector(item, filters)) {
          return;
        }
        total += 1;
        if (rows.length < topK) {
          rows.push({
            id: item.id,
            payload: item.payload,
          });
        }
      },
      CassandraDB.PAGE_SIZE,
    );

    return [rows, total];
  }

  async getUserId(): Promise<string> {
    await this.initialize();

    const result = await this.client!.execute(
      `
        SELECT user_id
        FROM ${this.keyspace}.memory_migrations
        WHERE id = ?
      `,
      [MIGRATION_ROW_ID],
      { prepare: true },
    );

    const existing = result.rows?.[0]?.user_id;
    if (typeof existing === "string" && existing.length > 0) {
      return existing;
    }

    const userId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.setUserId(userId);
    return userId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();

    await this.client!.execute(
      `
        INSERT INTO ${this.keyspace}.memory_migrations (id, user_id)
        VALUES (?, ?)
      `,
      [MIGRATION_ROW_ID, userId],
      { prepare: true },
    );
  }

  private async createClient(): Promise<CassandraClientLike> {
    const driver = this.driver ?? (await this.loadDriver());
    const clientConfig: Record<string, any> = {};

    if (this.secureConnectBundle) {
      clientConfig.cloud = {
        secureConnectBundle: this.secureConnectBundle,
      };
    } else {
      if (!this.contactPoints || this.contactPoints.length === 0) {
        throw new Error(
          "Cassandra vector store requires contactPoints when secureConnectBundle is not provided.",
        );
      }
      if (!this.localDataCenter) {
        throw new Error(
          "Cassandra vector store requires localDataCenter when secureConnectBundle is not provided.",
        );
      }
      clientConfig.contactPoints = this.contactPoints;
      clientConfig.localDataCenter = this.localDataCenter;
      clientConfig.protocolOptions = {
        port: this.port,
      };
    }

    if (this.protocolVersion !== undefined) {
      clientConfig.protocolOptions = {
        ...(clientConfig.protocolOptions || {}),
        maxVersion: this.protocolVersion,
      };
    }
    if (this.loadBalancingPolicy) {
      clientConfig.policies = {
        loadBalancing: this.loadBalancingPolicy,
      };
    }
    if (this.username && this.password) {
      clientConfig.authProvider = new driver.auth.PlainTextAuthProvider(
        this.username,
        this.password,
      );
    }

    return new driver.Client(clientConfig);
  }

  // Loaded dynamically: cassandra-driver is an optional peer dependency, so a static
  // value import would break `import { Memory } from "mem0ai/oss"` for everyone else.
  private async loadDriver(): Promise<any> {
    const sdk = await loadPeer(
      "cassandra-driver",
      "Cassandra vector store",
      () => import("cassandra-driver"),
    );
    return sdk.default ?? sdk;
  }

  private validateIdentifier(name: string, label: string): string {
    if (!SAFE_IDENTIFIER_RE.test(name)) {
      throw new Error(
        `Invalid ${label} '${name}': only letters, digits, and underscores are allowed, ` +
          "must start with a letter or underscore, and be at most 128 characters.",
      );
    }
    return name;
  }

  private cosineSimilarity(left: number[], right: number[]): number {
    let dotProduct = 0;
    let leftNorm = 0;
    let rightNorm = 0;

    for (let index = 0; index < left.length; index += 1) {
      dotProduct += left[index] * right[index];
      leftNorm += left[index] * left[index];
      rightNorm += right[index] * right[index];
    }

    if (leftNorm === 0 || rightNorm === 0) {
      return 0;
    }
    return dotProduct / (Math.sqrt(leftNorm) * Math.sqrt(rightNorm));
  }

  private normalizeVector(rawValue: any): number[] | undefined {
    if (Array.isArray(rawValue)) {
      return rawValue.map((value) => Number(value));
    }
    return undefined;
  }

  private parsePayload(rawValue: any): Record<string, any> {
    if (typeof rawValue === "string") {
      try {
        const parsed = JSON.parse(rawValue);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          return parsed;
        }
      } catch (error) {
        return {};
      }
    }
    if (rawValue && typeof rawValue === "object" && !Array.isArray(rawValue)) {
      return rawValue;
    }
    return {};
  }

  private matchFieldCondition(
    payload: Record<string, any>,
    key: string,
    value: any,
  ): boolean {
    const payloadValue = payload[key];

    if (typeof value !== "object" || value === null) {
      if (value === "*") {
        return true;
      }
      return payloadValue === value;
    }

    if (Array.isArray(value)) {
      return value.includes(payloadValue);
    }

    // Every operator present in a compound condition must hold (AND), so check
    // them all instead of returning on the first match. Returning early meant a
    // range like { gte: 10, lte: 20 } only applied `gte`. Mirrors the databricks
    // store's matcher.
    let sawOperator = false;

    if ("eq" in value) {
      sawOperator = true;
      if (payloadValue !== value.eq) return false;
    }
    if ("ne" in value) {
      sawOperator = true;
      if (payloadValue === value.ne) return false;
    }
    if ("gt" in value) {
      sawOperator = true;
      if (!(payloadValue > value.gt)) return false;
    }
    if ("gte" in value) {
      sawOperator = true;
      if (!(payloadValue >= value.gte)) return false;
    }
    if ("lt" in value) {
      sawOperator = true;
      if (!(payloadValue < value.lt)) return false;
    }
    if ("lte" in value) {
      sawOperator = true;
      if (!(payloadValue <= value.lte)) return false;
    }
    if ("in" in value) {
      sawOperator = true;
      if (!Array.isArray(value.in) || !value.in.includes(payloadValue))
        return false;
    }
    if ("nin" in value) {
      sawOperator = true;
      if (Array.isArray(value.nin) && value.nin.includes(payloadValue))
        return false;
    }
    if ("contains" in value) {
      sawOperator = true;
      if (
        typeof payloadValue !== "string" ||
        !payloadValue.includes(value.contains)
      )
        return false;
    }
    if ("icontains" in value) {
      sawOperator = true;
      if (
        typeof payloadValue !== "string" ||
        !payloadValue.toLowerCase().includes(value.icontains.toLowerCase())
      )
        return false;
    }

    return sawOperator ? true : payloadValue === value;
  }

  private filterVector(
    vector: CassandraVector,
    filters?: SearchFilters,
  ): boolean {
    if (!filters || Object.keys(filters).length === 0) {
      return true;
    }

    const keyMap: Record<string, string> = {
      $and: "AND",
      $or: "OR",
      $not: "NOT",
    };
    const normalized: Record<string, any> = {};
    for (const [key, value] of Object.entries(filters)) {
      const normalizedKey = keyMap[key] || key;
      if (!(normalizedKey in normalized)) {
        normalized[normalizedKey] = value;
      }
    }

    for (const [key, value] of Object.entries(normalized)) {
      if (key === "AND") {
        if (!Array.isArray(value)) {
          throw new Error(
            `AND filter value must be a list of filter dicts, got ${typeof value}`,
          );
        }
        if (
          !value.every((entry: SearchFilters) =>
            this.filterVector(vector, entry),
          )
        ) {
          return false;
        }
      } else if (key === "OR") {
        if (!Array.isArray(value)) {
          throw new Error(
            `OR filter value must be a list of filter dicts, got ${typeof value}`,
          );
        }
        if (
          !value.some((entry: SearchFilters) =>
            this.filterVector(vector, entry),
          )
        ) {
          return false;
        }
      } else if (key === "NOT") {
        if (!Array.isArray(value)) {
          throw new Error(
            `NOT filter value must be a list of filter dicts, got ${typeof value}`,
          );
        }
        if (
          !value.every(
            (entry: SearchFilters) => !this.filterVector(vector, entry),
          )
        ) {
          return false;
        }
      } else if (!this.matchFieldCondition(vector.payload, key, value)) {
        return false;
      }
    }

    return true;
  }

  private assertVectorDimension(vector: number[], label: string): void {
    if (vector.length !== this.dimension) {
      throw new Error(
        `${label} dimension mismatch. Expected ${this.dimension}, got ${vector.length}`,
      );
    }
  }

  private assertBatchDimensions(vectors: number[][], label: string): void {
    for (const vector of vectors) {
      this.assertVectorDimension(vector, label);
    }
  }

  private async scanRows(
    query: string,
    onRow: (row: any) => Promise<void>,
    fetchSize: number,
  ): Promise<void> {
    let pageState: string | undefined;

    do {
      const result = await this.client!.execute(query, [], {
        autoPage: false,
        fetchSize,
        pageState,
      });
      for (const row of result.rows || []) {
        await onRow(row);
      }
      pageState = result.pageState || undefined;
    } while (pageState);
  }

  private pushTopResult(
    results: VectorStoreResult[],
    candidate: VectorStoreResult,
    topK: number,
  ): void {
    results.push(candidate);
    results.sort((left, right) => (right.score || 0) - (left.score || 0));
    if (results.length > topK) {
      results.length = topK;
    }
  }
}
