import weaviate, { Filters, type WeaviateClient } from "weaviate-client";
import { v4 as uuidv4 } from "uuid";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface WeaviateConfig extends VectorStoreConfig {
  client?: WeaviateClient;
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

  private async _doInitialize(): Promise<void> {
    const { client, clusterUrl, apiKey, additionalHeaders, collectionName } =
      this._config;

    if (client) {
      this._client = client;
    } else if (clusterUrl?.includes("localhost")) {
      this._client = await weaviate.connectToLocal({
        headers: additionalHeaders,
      });
    } else if (apiKey) {
      this._client = await weaviate.connectToWeaviateCloud(clusterUrl!, {
        authCredentials: weaviate.ApiKey(apiKey),
        headers: additionalHeaders,
      });
    } else {
      if (!clusterUrl) {
        throw new Error(
          "WeaviateDB: clusterUrl is required when client and apiKey are not provided",
        );
      }
      const parsed = new URL(clusterUrl);
      this._client = await weaviate.connectToCustom({
        httpHost: parsed.hostname,
        httpPort: parsed.port ? parseInt(parsed.port) : 80,
        httpSecure: parsed.protocol === "https:",
        grpcHost: parsed.hostname,
        grpcPort: 50051,
        grpcSecure: false,
        headers: additionalHeaders,
      });
    }

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
    return conditions.length ? Filters.and(...conditions) : undefined;
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
