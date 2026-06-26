import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

/**
 * Supported Milvus metric types. Mirrors the Python provider
 * (`mem0/configs/vector_stores/milvus.py`).
 */
export type MilvusMetricType = "L2" | "IP" | "COSINE" | "HAMMING" | "JACCARD";

export interface MilvusConfig extends VectorStoreConfig {
  /**
   * Full URL/address for the Milvus or Zilliz server.
   * Defaults to `http://localhost:19530`.
   */
  url?: string;
  /** Token / API key for Zilliz Cloud. Optional for a local setup. */
  token?: string;
  /** Name of the database. Optional (Milvus default database when empty). */
  dbName?: string;
  /** Collection name. Defaults to `mem0`. */
  collectionName?: string;
  /** Embedding dimensionality. Defaults to 1536 (OpenAI). */
  embeddingModelDims?: number;
  dimension?: number;
  /** Similarity metric. Defaults to `COSINE`. */
  metricType?: MilvusMetricType;
  /**
   * Pre-constructed `MilvusClient` instance. When provided, `url`/`token`/`dbName`
   * are ignored. Primarily useful for dependency injection in tests.
   */
  client?: any;
}

/**
 * Milvus vector store provider for the TypeScript OSS SDK.
 *
 * Mirrors the Python provider in `mem0/vector_stores/milvus.py`, scoped to the
 * dense-vector CRUD surface the TS `VectorStore` interface requires
 * (insert / search / get / update / delete / list / reset + user-id helpers).
 *
 * The `@zilliz/milvus2-sdk-node` dependency is lazily required so the package
 * remains optional — importing this module never forces the SDK to be installed
 * until a Milvus store is actually constructed.
 */
export class Milvus implements VectorStore {
  private client: any;
  private readonly collectionName: string;
  private readonly dimension: number;
  private readonly metricType: MilvusMetricType;
  private _initPromise?: Promise<void>;
  // Lazily-resolved DataType enum from the SDK (set during client construction).
  private DataType: any;

  constructor(config: MilvusConfig) {
    this.collectionName = config.collectionName || "mem0";
    this.dimension = config.embeddingModelDims || config.dimension || 1536;
    this.metricType = config.metricType || "COSINE";

    if (config.client) {
      this.client = config.client;
      // Best-effort DataType resolution for an injected client.
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        this.DataType = require("@zilliz/milvus2-sdk-node").DataType;
      } catch (_) {
        this.DataType = undefined;
      }
    } else {
      let MilvusClient: any;
      let DataType: any;
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const sdk = require("@zilliz/milvus2-sdk-node");
        MilvusClient = sdk.MilvusClient;
        DataType = sdk.DataType;
      } catch (_) {
        throw new Error(
          "The '@zilliz/milvus2-sdk-node' package is required to use the Milvus vector store. " +
            "Install it with: npm install @zilliz/milvus2-sdk-node",
        );
      }
      this.DataType = DataType;
      this.client = new MilvusClient({
        address: config.url || "http://localhost:19530",
        token: config.token,
        database: config.dbName || undefined,
      });
    }

    this.initialize().catch((err) =>
      console.error("Error initializing Milvus:", err),
    );
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this.createCol(this.collectionName, this.dimension);
    }
    return this._initPromise;
  }

  /**
   * Create the collection with an AUTOINDEX dense-vector index if it does not
   * already exist. Idempotent — mirrors the Python `create_col`.
   */
  private async createCol(
    collectionName: string,
    vectorSize: number,
  ): Promise<void> {
    const has = await this.client.hasCollection({
      collection_name: collectionName,
    });
    // milvus2-sdk-node returns { value: boolean } for hasCollection.
    const exists = typeof has === "object" && has !== null ? has.value : has;
    if (exists) {
      return;
    }

    const DataType = this.DataType || {};
    const fields = [
      {
        name: "id",
        data_type: DataType.VarChar,
        is_primary_key: true,
        max_length: 512,
      },
      {
        name: "vectors",
        data_type: DataType.FloatVector,
        dim: vectorSize,
      },
      {
        name: "metadata",
        data_type: DataType.JSON,
      },
    ];

    await this.client.createCollection({
      collection_name: collectionName,
      fields,
      enable_dynamic_field: true,
      index_params: [
        {
          field_name: "vectors",
          index_type: "AUTOINDEX",
          metric_type: this.metricType,
          index_name: "vector_index",
        },
      ],
    });

    await this.client.loadCollection({ collection_name: collectionName });
  }

  /**
   * Build a Milvus boolean filter expression from a flat filters object.
   * Mirrors the Python `_create_filter` (equality only, AND-combined).
   */
  private createFilter(filters?: SearchFilters): string | undefined {
    if (!filters || Object.keys(filters).length === 0) return undefined;
    const operands: string[] = [];
    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null) continue;
      if (typeof value === "string") {
        // Escape embedded double quotes to keep the expression well-formed.
        const escaped = value.replace(/"/g, '\\"');
        operands.push(`(metadata["${key}"] == "${escaped}")`);
      } else {
        operands.push(`(metadata["${key}"] == ${value})`);
      }
    }
    return operands.length > 0 ? operands.join(" and ") : undefined;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const data = vectors.map((vector, idx) => ({
      id: ids[idx],
      vectors: vector,
      metadata: payloads[idx] || {},
    }));
    await this.client.insert({
      collection_name: this.collectionName,
      data,
    });
  }

  async keywordSearch(): Promise<null> {
    // BM25 / sparse hybrid search is not implemented in the TS provider yet.
    return null;
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const filter = this.createFilter(filters);
    const res = await this.client.search({
      collection_name: this.collectionName,
      data: [query],
      limit: topK,
      filter,
      output_fields: ["*"],
    });
    const hits = res?.results || [];
    return hits.map((hit: any) => {
      const rawDistance = hit.score ?? hit.distance;
      let score = rawDistance;
      // L2 distances are unbounded and smaller-is-better; normalise to a
      // 0..1 similarity so consumers can treat all metrics uniformly.
      if (rawDistance != null && this.metricType === "L2") {
        score = 1.0 / (1.0 + rawDistance);
      }
      return {
        id: String(hit.id),
        payload: hit.metadata || {},
        score,
      } as VectorStoreResult;
    });
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const res = await this.client.get({
      collection_name: this.collectionName,
      ids: [vectorId],
      output_fields: ["*"],
    });
    const rows = res?.data || [];
    if (!rows.length) return null;
    return {
      id: String(rows[0].id),
      payload: rows[0].metadata || {},
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.client.upsert({
      collection_name: this.collectionName,
      data: [{ id: vectorId, vectors: vector, metadata: payload }],
    });
  }

  async delete(vectorId: string): Promise<void> {
    await this.client.delete({
      collection_name: this.collectionName,
      ids: [vectorId],
    });
  }

  async deleteCol(): Promise<void> {
    await this.client.dropCollection({
      collection_name: this.collectionName,
    });
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const filter = this.createFilter(filters);
    const res = await this.client.query({
      collection_name: this.collectionName,
      filter: filter ?? "",
      limit: topK,
      output_fields: ["*"],
    });
    const rows = res?.data || [];
    const results: VectorStoreResult[] = rows.map((row: any) => ({
      id: String(row.id),
      payload: row.metadata || {},
    }));
    return [results, results.length];
  }

  private generateUUID(): string {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  private async ensureMigrationsCol(): Promise<void> {
    const name = "memory_migrations";
    const has = await this.client.hasCollection({ collection_name: name });
    const exists = typeof has === "object" && has !== null ? has.value : has;
    if (exists) return;

    const DataType = this.DataType || {};
    await this.client.createCollection({
      collection_name: name,
      fields: [
        {
          name: "id",
          data_type: DataType.VarChar,
          is_primary_key: true,
          max_length: 512,
        },
        { name: "vectors", data_type: DataType.FloatVector, dim: 1 },
        { name: "user_id", data_type: DataType.VarChar, max_length: 512 },
      ],
      index_params: [
        {
          field_name: "vectors",
          index_type: "AUTOINDEX",
          metric_type: this.metricType,
          index_name: "vector_index",
        },
      ],
    });
    await this.client.loadCollection({ collection_name: name });
  }

  async getUserId(): Promise<string> {
    await this.ensureMigrationsCol();
    const res = await this.client.query({
      collection_name: "memory_migrations",
      filter: "",
      limit: 1,
      output_fields: ["*"],
    });
    const rows = res?.data || [];
    if (rows.length > 0 && rows[0].user_id) {
      return String(rows[0].user_id);
    }
    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.client.insert({
      collection_name: "memory_migrations",
      data: [{ id: this.generateUUID(), vectors: [0], user_id: randomUserId }],
    });
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.ensureMigrationsCol();
    await this.client.insert({
      collection_name: "memory_migrations",
      data: [{ id: this.generateUUID(), vectors: [0], user_id: userId }],
    });
  }
}
