import type { Client } from "@elastic/elasticsearch";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface ElasticsearchConfig extends VectorStoreConfig {
  /** Pre-configured Elasticsearch client instance (typed as `any` to keep the
   *  optional driver's types out of the published type declarations). */
  client?: any;
  host?: string;
  port?: number;
  cloudId?: string;
  apiKey?: string;
  username?: string;
  password?: string;
  collectionName: string;
  embeddingModelDims: number;
  dimension?: number;
  useSsl?: boolean;
  caCerts?: string;
  verifyCerts?: boolean;
  autoCreateIndex?: boolean;
  headers?: Record<string, string>;
}

const SAFE_FILTER_KEY = /^[a-zA-Z_][a-zA-Z0-9_]*$/;

// Mirrors the Python provider's _validate_filter. Filter keys are interpolated
// into `metadata.${key}` field paths, so reject anything that is not a plain
// identifier and reject non-scalar values before they reach the query.
function validateFilter(key: string, value: unknown): void {
  if (typeof key !== "string" || !SAFE_FILTER_KEY.test(key)) {
    throw new Error(`Invalid filter key: ${JSON.stringify(key)}`);
  }
  if (
    typeof value !== "string" &&
    typeof value !== "number" &&
    typeof value !== "boolean"
  ) {
    throw new Error(
      `Filter value for ${JSON.stringify(key)} must be string, number, or boolean`,
    );
  }
}

export class ElasticsearchDB implements VectorStore {
  private client!: Client;
  private readonly config: ElasticsearchConfig;
  private readonly collectionName: string;
  private readonly dimension: number;
  private readonly autoCreateIndex: boolean;
  private _initPromise?: Promise<void>;

  constructor(config: ElasticsearchConfig) {
    this.config = config;
    this.collectionName = config.collectionName;
    this.dimension = config.dimension || config.embeddingModelDims || 1536;
    this.autoCreateIndex = config.autoCreateIndex !== false;

    this.initialize().catch(console.error);
  }

  // The client is created lazily on first initialize() so the optional
  // `@elastic/elasticsearch` peer is only loaded when the store is actually used.
  private async ensureClient(): Promise<void> {
    if (this.client) return;

    const config = this.config;
    if (config.client) {
      this.client = config.client;
    } else {
      const params: Record<string, any> = {};

      if (config.cloudId) {
        params.cloud = { id: config.cloudId };
        if (config.apiKey) {
          params.auth = { apiKey: config.apiKey };
        }
      } else {
        const host = config.host || "localhost";
        const port = config.port || 9200;
        params.node = `${config.useSsl !== false ? "https" : "http"}://${host}:${port}`;

        if (config.apiKey) {
          params.auth = { apiKey: config.apiKey };
        } else if (config.username && config.password) {
          params.auth = {
            username: config.username,
            password: config.password,
          };
        }
      }

      if (config.verifyCerts !== undefined) {
        params.tls = { rejectUnauthorized: config.verifyCerts };
      }
      if (config.caCerts) {
        params.tls = { ...params.tls, ca: config.caCerts };
      }
      if (config.headers) {
        params.headers = config.headers;
      }

      let sdk: any;
      try {
        sdk = await import("@elastic/elasticsearch");
      } catch {
        throw new Error(
          "The '@elastic/elasticsearch' package is required to use the Elasticsearch vector store. Install it with: npm install @elastic/elasticsearch",
        );
      }

      this.client = new sdk.Client(params);
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
    try {
      if (this.autoCreateIndex) {
        await this.ensureIndex(this.collectionName, this.dimension);
      }
      await this.ensureIndex("memory_migrations", 1);
    } catch (error) {
      console.error("Error initializing Elasticsearch:", error);
      throw error;
    }
  }

  private async ensureIndex(name: string, size: number): Promise<void> {
    const exists = await this.client.indices.exists({ index: name });
    if (!exists) {
      await this.client.indices.create({
        index: name,
        settings: {
          number_of_replicas: 1,
          number_of_shards: 5,
          refresh_interval: "1s",
        },
        mappings: {
          properties: {
            vector: {
              type: "dense_vector",
              dims: size,
              index: true,
              similarity: "cosine",
            },
            metadata: {
              type: "object",
              properties: {
                user_id: { type: "keyword" },
                agent_id: { type: "keyword" },
                run_id: { type: "keyword" },
              },
            },
          },
        },
      });
    }
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();
    const operations: any[] = [];
    for (let i = 0; i < vectors.length; i++) {
      operations.push(
        { index: { _index: this.collectionName, _id: ids[i] } },
        { vector: vectors[i], metadata: payloads[i] || {} },
      );
    }

    await this.client.bulk({ operations });
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();
    const searchBody: Record<string, any> = {
      knn: {
        field: "vector",
        query_vector: query,
        k: topK,
        num_candidates: topK * 2,
      },
    };

    if (filters && Object.keys(filters).length > 0) {
      const filterConditions = Object.entries(filters).map(([key, value]) => {
        validateFilter(key, value);
        return { term: { [`metadata.${key}`]: value } };
      });
      searchBody.knn.filter = { bool: { must: filterConditions } };
    }

    const response = await this.client.search({
      index: this.collectionName,
      ...searchBody,
    });

    return response.hits.hits.map((hit: any) => ({
      id: hit._id,
      score: hit._score,
      payload: hit._source?.metadata || {},
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();
    try {
      const response = await this.client.get({
        index: this.collectionName,
        id: vectorId,
      });
      return {
        id: response._id,
        payload: (response._source as any)?.metadata || {},
      };
    } catch (error: any) {
      if (error?.meta?.statusCode === 404) return null;
      throw error;
    }
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();
    const doc: Record<string, any> = {};
    if (vector) doc.vector = vector;
    if (payload) doc.metadata = payload;

    await this.client.update({
      index: this.collectionName,
      id: vectorId,
      doc,
    });
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();
    await this.client.delete({
      index: this.collectionName,
      id: vectorId,
    });
  }

  async deleteCol(): Promise<void> {
    await this.initialize();
    await this.client.indices.delete({ index: this.collectionName });
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();
    const query: Record<string, any> = { query: { match_all: {} } };

    if (filters && Object.keys(filters).length > 0) {
      const filterConditions = Object.entries(filters).map(([key, value]) => {
        validateFilter(key, value);
        return { term: { [`metadata.${key}`]: value } };
      });
      query.query = { bool: { must: filterConditions } };
    }

    query.size = topK;

    const response = await this.client.search({
      index: this.collectionName,
      ...query,
    });

    const results = response.hits.hits.map((hit: any) => ({
      id: hit._id,
      payload: hit._source?.metadata || {},
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

  async getUserId(): Promise<string> {
    await this.initialize();
    try {
      const response = await this.client.search({
        index: "memory_migrations",
        query: { match_all: {} },
        size: 1,
      });

      if (response.hits.hits.length > 0) {
        return (response.hits.hits[0]._source as any)?.metadata
          ?.user_id as string;
      }

      const randomUserId =
        Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15);

      // memory_migrations is only ever read via match_all, never by vector,
      // so store no vector. A zero vector would be rejected by the cosine
      // dense_vector mapping ("does not support vectors with zero magnitude").
      await this.client.index({
        index: "memory_migrations",
        id: this.generateUUID(),
        document: { metadata: { user_id: randomUserId } },
      });

      return randomUserId;
    } catch (error) {
      console.error("Error getting user ID:", error);
      throw error;
    }
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();
    try {
      const response = await this.client.search({
        index: "memory_migrations",
        query: { match_all: {} },
        size: 1,
      });

      const docId =
        response.hits.hits.length > 0
          ? response.hits.hits[0]._id
          : this.generateUUID();

      await this.client.index({
        index: "memory_migrations",
        id: docId,
        document: { metadata: { user_id: userId } },
      });
    } catch (error) {
      console.error("Error setting user ID:", error);
      throw error;
    }
  }
}
