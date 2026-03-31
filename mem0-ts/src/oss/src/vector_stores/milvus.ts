import { MilvusClient, DataType } from "@zilliz/milvus2-sdk-node";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface MilvusConfig extends VectorStoreConfig {
  url?: string;
  token?: string;
  collectionName: string;
  embeddingModelDims?: number;
  dimension?: number;
  metricType?: string;
  dbName?: string;
  client?: MilvusClient;
}

const MIGRATION_COLLECTION = "memory_migrations";

export class MilvusDB implements VectorStore {
  private client: MilvusClient;
  private readonly collectionName: string;
  private readonly dimension: number;
  private readonly metricType: string;
  private _initPromise?: Promise<void>;

  constructor(config: MilvusConfig) {
    if (config.client) {
      this.client = config.client;
    } else {
      this.client = new MilvusClient({
        address: config.url || "localhost:19530",
        token: config.token,
        database: config.dbName,
      });
    }

    this.collectionName = config.collectionName;
    this.dimension = config.dimension || config.embeddingModelDims || 1536;
    this.metricType = config.metricType || "COSINE";
    this.initialize().catch(console.error);
  }

  private createFilter(filters?: SearchFilters): string | undefined {
    if (!filters) return undefined;

    const operands: string[] = [];
    for (const [key, value] of Object.entries(filters)) {
      if (typeof value === "string") {
        operands.push(`(metadata["${key}"] == "${value}")`);
      } else {
        operands.push(`(metadata["${key}"] == ${value})`);
      }
    }

    return operands.length ? operands.join(" and ") : undefined;
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

  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const queryFilter = this.createFilter(filters);

    const response = await this.client.search({
      collection_name: this.collectionName,
      data: [query],
      limit,
      filter: queryFilter || "",
      output_fields: ["*"],
    });

    if (!response.results || !response.results.length) {
      return [];
    }

    return response.results.map((hit: any) => ({
      id: String(hit.id),
      payload: hit.metadata || {},
      score: hit.score ?? hit.distance,
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const response = await this.client.get({
      collection_name: this.collectionName,
      ids: [vectorId],
      output_fields: ["metadata"],
    });

    if (!response.data || !response.data.length) return null;

    return {
      id: vectorId,
      payload: response.data[0].metadata || {},
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.client.upsert({
      collection_name: this.collectionName,
      data: [
        {
          id: vectorId,
          vectors: vector,
          metadata: payload,
        },
      ],
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
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const queryFilter = this.createFilter(filters);

    const response = await this.client.query({
      collection_name: this.collectionName,
      filter: queryFilter || "id != ''",
      limit,
      output_fields: ["id", "metadata"],
    });

    const results = (response.data || []).map((row: any) => ({
      id: String(row.id),
      payload: row.metadata || {},
    }));

    return [results, results.length];
  }

  private generateUUID(): string {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
      /[xy]/g,
      function (c) {
        const r = (Math.random() * 16) | 0;
        const v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      },
    );
  }

  async getUserId(): Promise<string> {
    try {
      await this.ensureCollection(MIGRATION_COLLECTION, 1);

      const response = await this.client.query({
        collection_name: MIGRATION_COLLECTION,
        filter: "id != ''",
        limit: 1,
        output_fields: ["metadata"],
      });

      if (response.data && response.data.length > 0) {
        return response.data[0].metadata?.user_id as string;
      }

      const randomUserId =
        Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15);

      await this.client.insert({
        collection_name: MIGRATION_COLLECTION,
        data: [
          {
            id: this.generateUUID(),
            vectors: [0],
            metadata: { user_id: randomUserId },
          },
        ],
      });

      return randomUserId;
    } catch (error) {
      console.error("Error getting user ID:", error);
      throw error;
    }
  }

  async setUserId(userId: string): Promise<void> {
    try {
      await this.ensureCollection(MIGRATION_COLLECTION, 1);

      const response = await this.client.query({
        collection_name: MIGRATION_COLLECTION,
        filter: "id != ''",
        limit: 1,
        output_fields: ["id"],
      });

      const pointId =
        response.data && response.data.length > 0
          ? response.data[0].id
          : this.generateUUID();

      await this.client.upsert({
        collection_name: MIGRATION_COLLECTION,
        data: [
          {
            id: pointId,
            vectors: [0],
            metadata: { user_id: userId },
          },
        ],
      });
    } catch (error) {
      console.error("Error setting user ID:", error);
      throw error;
    }
  }

  private async ensureCollection(
    name: string,
    vectorSize: number,
  ): Promise<void> {
    const hasCol = await this.client.hasCollection({
      collection_name: name,
    });

    if (hasCol.value) return;

    await this.client.createCollection({
      collection_name: name,
      fields: [
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
      ],
      index_params: [
        {
          field_name: "vectors",
          metric_type:
            name === this.collectionName ? this.metricType : "COSINE",
          index_type: "AUTOINDEX",
          index_name: "vector_index",
        },
      ],
      enable_dynamic_field: true,
    });
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    try {
      await this.ensureCollection(this.collectionName, this.dimension);
      await this.ensureCollection(MIGRATION_COLLECTION, 1);
    } catch (error) {
      console.error("Error initializing MilvusDB:", error);
      throw error;
    }
  }
}
