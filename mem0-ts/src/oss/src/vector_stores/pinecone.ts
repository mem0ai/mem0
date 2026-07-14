import type { Pinecone, Index } from "@pinecone-database/pinecone";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

const MIGRATIONS_NAMESPACE = "__mem0_migrations__";
const MIGRATIONS_RECORD_ID = "mem0-user-id";

interface PineconeDBConfig extends VectorStoreConfig {
  collectionName: string;
  embeddingModelDims: number;
  /** Pre-configured Pinecone client instance (typed as `any` to keep the
   *  optional driver's types out of the published type declarations). */
  client?: any;
  apiKey?: string;
  serverlessConfig?: { cloud: string; region: string };
  podConfig?: {
    environment: string;
    podType?: string;
    pods?: number;
    replicas?: number;
    shards?: number;
  };
  metric?: "cosine" | "dotproduct" | "euclidean";
  batchSize?: number;
  namespace?: string;
  extraParams?: Record<string, any>;
}

export class PineconeDB implements VectorStore {
  private client!: Pinecone;
  private readonly config: PineconeDBConfig;
  private readonly collectionName: string;
  private readonly dimension: number;
  private readonly metric: "cosine" | "dotproduct" | "euclidean";
  private readonly batchSize: number;
  private readonly namespace: string;
  private readonly serverlessConfig?: { cloud: string; region: string };
  private readonly podConfig?: {
    environment: string;
    podType?: string;
    pods?: number;
    replicas?: number;
    shards?: number;
  };
  private readonly extraParams: Record<string, any>;
  private _index?: Index;
  private _initPromise?: Promise<void>;

  constructor(config: PineconeDBConfig) {
    if (!config.client) {
      const apiKey = config.apiKey || process.env.PINECONE_API_KEY;
      if (!apiKey) {
        throw new Error(
          "Pinecone API key required: pass apiKey or set PINECONE_API_KEY env var",
        );
      }
    }

    this.config = config;
    this.collectionName = config.collectionName;
    this.dimension = config.embeddingModelDims || config.dimension || 1536;
    this.metric = config.metric || "cosine";
    this.batchSize = config.batchSize || 100;
    this.namespace = config.namespace || "";
    this.serverlessConfig = config.serverlessConfig;
    this.podConfig = config.podConfig;
    this.extraParams = config.extraParams || {};

    this.initialize().catch(console.error);
  }

  /**
   * Lazily construct (or reuse) the Pinecone client, importing the optional
   * `@pinecone-database/pinecone` peer only when the store is first used so
   * consumers that never touch Pinecone don't need it installed.
   */
  private async ensureClient(): Promise<void> {
    if (this.client) return;

    const config = this.config;
    if (config.client) {
      this.client = config.client;
    } else {
      const apiKey = config.apiKey || process.env.PINECONE_API_KEY;
      let sdk: any;
      try {
        sdk = await import("@pinecone-database/pinecone");
      } catch {
        throw new Error(
          "The '@pinecone-database/pinecone' package is required to use the Pinecone vector store. Install it with: npm install @pinecone-database/pinecone",
        );
      }
      this.client = new sdk.Pinecone({ apiKey });
    }
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    await this.ensureClient();
    await this._ensureIndex();
    this._index = this.client.index({ name: this.collectionName });
  }

  private async _ensureIndex(): Promise<void> {
    const indexList = await this.client.listIndexes();
    const exists = ((indexList as any).indexes || []).some(
      (idx: { name: string }) => idx.name === this.collectionName,
    );
    if (exists) return;

    const spec: Record<string, any> = this.podConfig
      ? {
          pod: {
            environment: this.podConfig.environment,
            podType: this.podConfig.podType || "p1.x1",
            pods: this.podConfig.pods || 1,
            replicas: this.podConfig.replicas || 1,
            shards: this.podConfig.shards || 1,
          },
        }
      : {
          serverless: this.serverlessConfig || {
            cloud: "aws",
            region: "us-east-1",
          },
        };

    await this.client.createIndex({
      name: this.collectionName,
      dimension: this.dimension,
      metric: this.metric,
      spec,
      waitUntilReady: true,
      ...this.extraParams,
    });
  }

  private index(): Index {
    return this._index!;
  }

  private namespacedIndex(): Index {
    return this.namespace
      ? this.index().namespace(this.namespace)
      : this.index();
  }

  private migrationsIndex(): Index {
    return this.index().namespace(MIGRATIONS_NAMESPACE);
  }

  private createFilter(
    filters?: SearchFilters,
  ): Record<string, any> | undefined {
    if (!filters || Object.keys(filters).length === 0) return undefined;

    const result: Record<string, any> = {};

    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null) continue;

      if (key === "AND" || key === "$and") {
        result["$and"] = (value as SearchFilters[]).map(
          (sub) => this.createFilter(sub) || {},
        );
        continue;
      }
      if (key === "OR" || key === "$or") {
        result["$or"] = (value as SearchFilters[]).map(
          (sub) => this.createFilter(sub) || {},
        );
        continue;
      }
      if (key === "NOT" || key === "$not") {
        console.warn(
          "Filter operator 'NOT' is not supported by Pinecone metadata filters; skipping.",
        );
        continue;
      }

      if (value === "*") continue;

      if (Array.isArray(value)) {
        result[key] = { $in: value };
        continue;
      }

      if (typeof value === "object" && value !== null) {
        const pineconeOps: Record<string, any> = {};
        for (const [op, opVal] of Object.entries(value)) {
          switch (op) {
            case "eq":
              pineconeOps["$eq"] = opVal;
              break;
            case "ne":
              pineconeOps["$ne"] = opVal;
              break;
            case "gt":
              pineconeOps["$gt"] = opVal;
              break;
            case "gte":
              pineconeOps["$gte"] = opVal;
              break;
            case "lt":
              pineconeOps["$lt"] = opVal;
              break;
            case "lte":
              pineconeOps["$lte"] = opVal;
              break;
            case "in":
              pineconeOps["$in"] = opVal;
              break;
            case "nin":
              pineconeOps["$nin"] = opVal;
              break;
            case "contains":
            case "icontains":
              console.warn(
                `Filter operator '${op}' is not supported by Pinecone metadata filters; skipping.`,
              );
              break;
            default:
              throw new Error(
                `Unsupported filter operator '${op}' for Pinecone`,
              );
          }
        }
        if (Object.keys(pineconeOps).length > 0) {
          result[key] = pineconeOps;
        }
        continue;
      }

      result[key] = { $eq: value };
    }

    return Object.keys(result).length > 0 ? result : undefined;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();
    const records = vectors.map((values, i) => ({
      id: ids[i],
      values,
      metadata: payloads[i] || {},
    }));
    for (let i = 0; i < records.length; i += this.batchSize) {
      await this.namespacedIndex().upsert({
        records: records.slice(i, i + this.batchSize),
      });
    }
  }

  async keywordSearch(
    _query: string,
    _topK?: number,
    _filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    return null;
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();
    const filter = this.createFilter(filters);
    const response = await this.namespacedIndex().query({
      vector: query,
      topK,
      includeMetadata: true,
      includeValues: false,
      ...(filter ? { filter } : {}),
    });
    return (response.matches || []).map((match: any) => ({
      id: match.id,
      payload: (match.metadata as Record<string, any>) || {},
      score: match.score,
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();
    const response = await this.namespacedIndex().fetch({ ids: [vectorId] });
    const record = (response.records || {})[vectorId];
    if (!record) return null;
    return {
      id: record.id,
      payload: (record.metadata as Record<string, any>) || {},
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();
    await this.namespacedIndex().upsert({
      records: [{ id: vectorId, values: vector, metadata: payload }],
    });
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();
    await this.namespacedIndex().deleteOne({ id: vectorId });
  }

  async deleteCol(): Promise<void> {
    if (this._initPromise) {
      await this._initPromise.catch(() => {});
    }
    await this.client.deleteIndex(this.collectionName);
    this._index = undefined;
    this._initPromise = undefined;
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();
    const zeroVector = new Array(this.dimension).fill(0);
    const filter = this.createFilter(filters);
    const response = await this.namespacedIndex().query({
      vector: zeroVector,
      topK,
      includeMetadata: true,
      includeValues: false,
      ...(filter ? { filter } : {}),
    });
    const results = (response.matches || []).map((match: any) => ({
      id: match.id,
      payload: (match.metadata as Record<string, any>) || {},
      score: match.score,
    }));
    return [results, results.length];
  }

  async getUserId(): Promise<string> {
    await this.initialize();
    try {
      const response = await this.migrationsIndex().fetch({
        ids: [MIGRATIONS_RECORD_ID],
      });
      const record = (response.records || {})[MIGRATIONS_RECORD_ID];
      if (record?.metadata?.user_id) {
        return record.metadata.user_id as string;
      }
    } catch {
      // no record yet, fall through
    }
    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.migrationsIndex().upsert({
      records: [
        {
          id: MIGRATIONS_RECORD_ID,
          values: new Array(this.dimension).fill(0),
          metadata: { user_id: randomUserId },
        },
      ],
    });
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();
    await this.migrationsIndex().upsert({
      records: [
        {
          id: MIGRATIONS_RECORD_ID,
          values: new Array(this.dimension).fill(0),
          metadata: { user_id: userId },
        },
      ],
    });
  }
}
