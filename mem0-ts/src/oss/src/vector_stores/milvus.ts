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
  /** Similarity metric. Defaults to `L2` (matches the Python provider). */
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
 * Mirrors the Python provider in `mem0/vector_stores/milvus.py`: dense-vector
 * CRUD (insert / search / get / update / delete / list + user-id helpers) plus
 * BM25 hybrid keyword search. New collections are created with a `text` +
 * `sparse` field pair and a BM25 function so `keywordSearch` can run full-text
 * search; collections created before BM25 support keep working with it disabled.
 *
 * The `@zilliz/milvus2-sdk-node` dependency is lazily required so the package
 * remains optional. Importing this module never forces the SDK to be installed
 * until a Milvus store is actually constructed.
 */
export class Milvus implements VectorStore {
  private client: any;
  private readonly collectionName: string;
  private readonly dimension: number;
  private readonly metricType: MilvusMetricType;
  private _initPromise?: Promise<void>;
  // Lazily-resolved SDK enums (set during client construction).
  private DataType: any;
  private FunctionType: any;
  // Whether this collection has the `text` + `sparse` fields for BM25 hybrid
  // search. Collections created before BM25 support lack them, so writing a
  // top-level `text` field or passing a sparse anns_field would be rejected.
  private hasBm25Schema = false;

  constructor(config: MilvusConfig) {
    this.collectionName = config.collectionName || "mem0";
    this.dimension = config.embeddingModelDims || config.dimension || 1536;
    this.metricType = config.metricType || "L2";

    if (config.client) {
      this.client = config.client;
      // Best-effort SDK enum resolution for an injected client (undefined when
      // the SDK isn't installed, e.g. unit tests that pass a fake client).
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const sdk = require("@zilliz/milvus2-sdk-node");
        this.DataType = sdk.DataType;
        this.FunctionType = sdk.FunctionType;
      } catch (_) {
        this.DataType = undefined;
        this.FunctionType = undefined;
      }
    } else {
      let MilvusClient: any;
      let DataType: any;
      let FunctionType: any;
      try {
        // eslint-disable-next-line @typescript-eslint/no-var-requires
        const sdk = require("@zilliz/milvus2-sdk-node");
        MilvusClient = sdk.MilvusClient;
        DataType = sdk.DataType;
        FunctionType = sdk.FunctionType;
      } catch (_) {
        throw new Error(
          "The '@zilliz/milvus2-sdk-node' package is required to use the Milvus vector store. " +
            "Install it with: npm install @zilliz/milvus2-sdk-node",
        );
      }
      this.DataType = DataType;
      this.FunctionType = FunctionType;
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
   * Create the collection if it does not already exist, with an AUTOINDEX
   * dense-vector index plus a BM25 `text` -> `sparse` full-text index. Idempotent
   * (mirrors the Python `create_col`). When the collection already exists, detect
   * whether the BM25 `text`/`sparse` fields are present so keyword search
   * degrades gracefully on collections created before BM25 support.
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
      // A pre-existing collection may predate BM25 support. Inspect its schema
      // so insert/search/keywordSearch know whether the text + sparse fields
      // exist instead of assuming and getting rejected by the server.
      const desc = await this.client.describeCollection({
        collection_name: collectionName,
      });
      const names = new Set(
        (desc?.schema?.fields || []).map((f: any) => f.name),
      );
      this.hasBm25Schema = names.has("text") && names.has("sparse");
      if (!this.hasBm25Schema) {
        console.warn(
          `Milvus collection '${collectionName}' predates BM25 hybrid search ` +
            "(no 'text'/'sparse' fields). Keyword scoring is disabled for it; " +
            "semantic search still works. Use a fresh collection to enable it.",
        );
      }
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
      // Analyzer-enabled text field that feeds the BM25 function below.
      {
        name: "text",
        data_type: DataType.VarChar,
        max_length: 65535,
        enable_analyzer: true,
      },
      // Sparse vectors are generated automatically by the BM25 function.
      {
        name: "sparse",
        data_type: DataType.SparseFloatVector,
      },
    ];

    await this.client.createCollection({
      collection_name: collectionName,
      fields,
      enable_dynamic_field: true,
      // BM25 turns the `text` field into `sparse` vectors for full-text search.
      functions: [
        {
          name: "bm25",
          type: this.FunctionType?.BM25,
          input_field_names: ["text"],
          output_field_names: ["sparse"],
          params: {},
        },
      ],
      index_params: [
        {
          field_name: "vectors",
          index_type: "AUTOINDEX",
          metric_type: this.metricType,
          index_name: "vector_index",
        },
        {
          field_name: "sparse",
          index_type: "SPARSE_INVERTED_INDEX",
          metric_type: "BM25",
          index_name: "sparse_index",
        },
      ],
    });

    await this.client.loadCollection({ collection_name: collectionName });
    this.hasBm25Schema = true;
  }

  /**
   * Filter keys are interpolated straight into the expression, so restrict them
   * to safe identifiers (same rule as the Python provider) to block injection.
   */
  private static readonly SAFE_FILTER_KEY = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

  /**
   * Build a Milvus boolean filter expression from a flat filters object.
   * Mirrors the Python `_create_filter` (equality only, AND-combined): validate
   * each key, escape string values (backslash first, then double-quote), and
   * reject value types Milvus can't compare against a scalar field.
   */
  private createFilter(filters?: SearchFilters): string | undefined {
    if (!filters || Object.keys(filters).length === 0) return undefined;
    const operands: string[] = [];
    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null) continue;
      if (!Milvus.SAFE_FILTER_KEY.test(key)) {
        throw new Error(`Invalid filter key: ${JSON.stringify(key)}`);
      }
      if (typeof value === "string") {
        // Escape backslashes before quotes so a value can't break out of the
        // string literal (order matters, exactly as in the Python provider).
        const escaped = value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
        operands.push(`(metadata["${key}"] == "${escaped}")`);
      } else if (typeof value === "number" || typeof value === "boolean") {
        operands.push(`(metadata["${key}"] == ${value})`);
      } else {
        throw new Error(
          `Filter value for ${JSON.stringify(key)} must be a string, number, or boolean, got ${typeof value}`,
        );
      }
    }
    return operands.length > 0 ? operands.join(" and ") : undefined;
  }

  /**
   * Text fed to the BM25 sparse index for a payload. Prefers the lemmatized
   * text, falls back to the raw memory `data`, and truncates to the VarChar
   * limit (mirrors the Python provider).
   */
  private bm25Text(payload?: Record<string, any>): string {
    if (!payload) return "";
    const raw = payload.text_lemmatized || payload.data || "";
    return String(raw).slice(0, 65535);
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const data = vectors.map((vector, idx) => {
      const metadata = payloads[idx] || {};
      const row: Record<string, any> = {
        id: ids[idx],
        vectors: vector,
        metadata,
      };
      // Only write `text` when the collection has the BM25 schema; legacy
      // collections reject an unknown top-level field.
      if (this.hasBm25Schema) row.text = this.bm25Text(metadata);
      return row;
    });
    await this.client.insert({
      collection_name: this.collectionName,
      data,
    });
  }

  /**
   * Map raw Milvus search hits to VectorStoreResult. For the L2 metric,
   * distances are unbounded and smaller-is-better, so normalise them to a 0..1
   * similarity; every other metric passes the raw score through. Shared by
   * search and keywordSearch so both match the Python provider's `_parse_output`
   * (which likewise normalises by metric type regardless of dense vs BM25 score).
   */
  private parseHits(hits: any[]): VectorStoreResult[] {
    return hits.map((hit: any) => {
      const rawDistance = hit.score ?? hit.distance;
      let score = rawDistance;
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

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const filter = this.createFilter(filters);
    const req: Record<string, any> = {
      collection_name: this.collectionName,
      data: [query],
      limit: topK,
      filter,
      output_fields: ["*"],
    };
    // A BM25 collection has both a dense `vectors` and a sparse `sparse` field,
    // so anns_field is ambiguous unless we name the dense one explicitly.
    if (this.hasBm25Schema) req.anns_field = "vectors";
    const res = await this.client.search(req);
    return this.parseHits(res?.results || []);
  }

  /**
   * BM25 full-text keyword search over the sparse field. Milvus tokenizes the
   * raw query string via the collection's BM25 function. Returns null when the
   * collection has no BM25 schema so callers fall back to dense search only
   * (mirrors the Python provider).
   */
  async keywordSearch(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    if (!this.hasBm25Schema) return null;
    try {
      const filter = this.createFilter(filters);
      const res = await this.client.search({
        collection_name: this.collectionName,
        data: [query],
        anns_field: "sparse",
        limit: topK,
        filter,
        output_fields: ["*"],
      });
      return this.parseHits(res?.results || []);
    } catch (_) {
      // Keyword search is best-effort; degrade to null rather than failing the
      // whole retrieval path.
      return null;
    }
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const res = await this.client.get({
      collection_name: this.collectionName,
      ids: [vectorId],
      output_fields: ["id", "metadata"],
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
    const row: Record<string, any> = {
      id: vectorId,
      vectors: vector,
      metadata: payload,
    };
    if (this.hasBm25Schema) row.text = this.bm25Text(payload);
    await this.client.upsert({
      collection_name: this.collectionName,
      data: [row],
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
      output_fields: ["id", "metadata"],
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
        // Milvus rejects a FloatVector with dim < 2, so use the minimum (2). This
        // helper collection is never vector-searched; the vector is a fixed
        // placeholder that exists only to satisfy the required-vector-field schema.
        { name: "vectors", data_type: DataType.FloatVector, dim: 2 },
        { name: "user_id", data_type: DataType.VarChar, max_length: 512 },
      ],
      index_params: [
        {
          field_name: "vectors",
          index_type: "AUTOINDEX",
          // Fixed metric: this helper collection is never vector-searched, and a
          // zero vector has no direction, so COSINE would be degenerate here.
          metric_type: "L2",
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
      data: [
        { id: this.generateUUID(), vectors: [0, 0], user_id: randomUserId },
      ],
    });
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.ensureMigrationsCol();
    // Keep a single row: reuse the existing row's id when present so the upsert
    // overwrites it in place instead of appending a new row on every call
    // (mirrors the qdrant provider's single-row telemetry id).
    const existing = await this.client.query({
      collection_name: "memory_migrations",
      filter: "",
      limit: 1,
      output_fields: ["id"],
    });
    const rows = existing?.data || [];
    const id =
      rows.length > 0 && rows[0].id ? String(rows[0].id) : this.generateUUID();
    await this.client.upsert({
      collection_name: "memory_migrations",
      data: [{ id, vectors: [0, 0], user_id: userId }],
    });
  }
}
