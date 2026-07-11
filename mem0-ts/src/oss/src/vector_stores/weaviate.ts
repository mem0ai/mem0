import type { WeaviateClient } from "weaviate-client";
import { v4 as uuidv4 } from "uuid";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface WeaviateConfig extends VectorStoreConfig {
  /** Pre-configured Weaviate client instance (typed as `any` to keep the
   *  optional driver's types out of the published type declarations). */
  client?: any;
  clusterUrl?: string;
  apiKey?: string;
  additionalHeaders?: Record<string, string>;
  collectionName: string;
  embeddingModelDims: number;
}

const RETURN_PROPERTIES = [
  "ids",
  "hash",
  "metadata",
  "data",
  "created_at",
  "category",
  "updated_at",
  "user_id",
  "agent_id",
  "run_id",
];

export class WeaviateDB implements VectorStore {
  private _config: WeaviateConfig;
  private _client!: WeaviateClient;
  private _sdk: any;
  private _col!: any;
  private _userId: string;
  private _initPromise?: Promise<void>;

  constructor(config: WeaviateConfig) {
    this._config = config;
    this._userId = "";
    this.initialize().catch(console.error);
  }

  initialize(): Promise<void> {
    return (this._initPromise ??= this._doInitialize());
  }

  // Loaded dynamically: weaviate-client is an optional peer dependency, so a static
  // value import would break `import { Memory } from "mem0ai/oss"` for everyone else.
  private async ensureClient(): Promise<void> {
    if (this._client) return;

    let sdk: any;
    try {
      sdk = await import("weaviate-client");
    } catch {
      throw new Error(
        "The 'weaviate-client' package is required to use the Weaviate vector store. Install it with: npm install weaviate-client",
      );
    }
    this._sdk = sdk;

    const { client, clusterUrl, apiKey, additionalHeaders } = this._config;
    const weaviate = sdk.default;

    if (client) {
      this._client = client;
    } else if (clusterUrl?.includes("localhost")) {
      this._client = await weaviate.connectToLocal({
        headers: additionalHeaders,
      });
    } else if (apiKey) {
      this._client = await weaviate.connectToWeaviateCloud(clusterUrl!, {
        authCredentials: new weaviate.ApiKey(apiKey),
        headers: additionalHeaders,
      });
    } else {
      if (!clusterUrl) {
        throw new Error(
          "WeaviateDB: clusterUrl is required when client and apiKey are not provided",
        );
      }
      const parsed = new URL(clusterUrl);
      const httpSecure = parsed.protocol === "https:";
      this._client = await weaviate.connectToCustom({
        httpHost: parsed.hostname,
        httpPort: parsed.port
          ? parseInt(parsed.port, 10)
          : httpSecure
            ? 443
            : 8080,
        httpSecure,
        grpcHost: parsed.hostname,
        grpcPort: 50051,
        grpcSecure: false,
        headers: additionalHeaders,
      });
    }
  }

  private async _doInitialize(): Promise<void> {
    await this.ensureClient();
    const { collectionName } = this._config;
    const weaviate = this._sdk.default;

    const exists = await this._client.collections.exists(collectionName);
    if (!exists) {
      await this._client.collections.create({
        name: collectionName,
        properties: RETURN_PROPERTIES.map((name) => ({
          name,
          dataType: "text" as const,
        })),
        vectorizers: weaviate.configure.vectorizer.none(),
        vectorIndex: weaviate.configure.vectorIndex.hnsw(),
      } as any);
    }

    this._col = this._client.collections.get(collectionName);
  }

  private _buildFilters(filters?: SearchFilters) {
    if (!filters) return undefined;
    const conditions = (["user_id", "agent_id", "run_id"] as const)
      .filter((key) => filters[key] != null)
      .map((key) => this._col.filter.byProperty(key).equal(filters[key]));
    return conditions.length ? this._sdk.Filters.and(...conditions) : undefined;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();
    const objects = vectors.map((vector, i) => ({
      id: ids[i],
      properties: payloads[i],
      vectors: vector,
    }));
    await this._col.data.insertMany(objects);
  }

  async search(
    query: number[],
    topK?: number,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();
    const result = await this._col.query.nearVector(query, {
      limit: topK ?? 10,
      filters: this._buildFilters(filters),
      returnMetadata: ["distance"],
    });
    return result.objects.map((obj: any) => ({
      id: obj.uuid,
      payload: obj.properties,
      score: 1 - obj.metadata.distance,
    }));
  }

  async keywordSearch(
    query: string,
    topK?: number,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    await this.initialize();
    const result = await this._col.query.bm25(query, {
      queryProperties: ["data"],
      limit: topK ?? 10,
      filters: this._buildFilters(filters),
      returnMetadata: ["score"],
    });
    return result.objects.map((obj: any) => ({
      id: obj.uuid,
      payload: obj.properties,
      score: obj.metadata.score,
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();
    const obj = await this._col.query.fetchObjectById(vectorId, {
      returnProperties: RETURN_PROPERTIES,
    });
    if (!obj) return null;
    return { id: obj.uuid, payload: obj.properties };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();
    await this._col.data.update({
      id: vectorId,
      properties: payload,
      vectors: vector,
    });
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();
    await this._col.data.deleteById(vectorId);
  }

  async deleteCol(): Promise<void> {
    await this.initialize();
    await this._client.collections.delete(this._config.collectionName);
  }

  async list(
    filters?: SearchFilters,
    topK?: number,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();
    const result = await this._col.query.fetchObjects({
      limit: topK ?? 100,
      filters: this._buildFilters(filters),
      returnProperties: RETURN_PROPERTIES,
    });
    const results = result.objects.map((obj: any) => ({
      id: obj.uuid,
      payload: obj.properties,
    }));
    return [results, results.length];
  }

  async getUserId(): Promise<string> {
    if (!this._userId) {
      this._userId = uuidv4();
    }
    return this._userId;
  }

  async setUserId(userId: string): Promise<void> {
    this._userId = userId;
  }
}
