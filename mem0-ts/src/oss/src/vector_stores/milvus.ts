import { MilvusClient, DataType, FunctionType } from "@zilliz/milvus2-sdk-node";
import { v4 as uuidv4 } from "uuid";
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
  private _hasBm25Schema: boolean = false;

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
      const safeKey = String(key).replace(/"/g, '\\"');
      if (typeof value === "string") {
        const safeValue = value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
        operands.push(`(metadata["${safeKey}"] == "${safeValue}")`);
      } else {
        operands.push(`(metadata["${safeKey}"] == ${value})`);
      }
    }

    return operands.length ? operands.join(" and ") : undefined;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const data = vectors.map((vector, idx) => {
      const metadata = payloads[idx] || {};
      const record: Record<string, any> = {
        id: ids[idx],
        vectors: vector,
        metadata,
      };
      if (this._hasBm25Schema) {
        const text = metadata.textLemmatized || metadata.data || "";
        record.text = typeof text === "string" ? text.slice(0, 65535) : "";
      }
      return record;
    });

    await this.client.insert({
      collection_name: this.collectionName,
      data,
    });
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const queryFilter = this.createFilter(filters);

    const searchParams: Record<string, any> = {
      collection_name: this.collectionName,
      data: [query],
      limit: topK,
      filter: queryFilter,
      output_fields: ["*"],
    };

    if (this._hasBm25Schema) {
      searchParams.anns_field = "vectors";
    }

    const response = await this.client.search(searchParams as any);

    if (!response.results || !response.results.length) {
      return [];
    }

    return response.results.map((hit: any) => ({
      id: String(hit.id),
      payload: hit.metadata || {},
      score: hit.score ?? hit.distance,
    }));
  }

  async keywordSearch(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    if (!this._hasBm25Schema) {
      return null;
    }
    try {
      const queryFilter = this.createFilter(filters);
      const response = await this.client.search({
        collection_name: this.collectionName,
        data: [query],
        anns_field: "sparse",
        limit: topK,
        filter: queryFilter,
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
    } catch (error) {
      console.warn(
        `Keyword search not available for collection ${this.collectionName}:`,
        error,
      );
      return null;
    }
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
    const record: Record<string, any> = {
      id: vectorId,
      vectors: vector,
      metadata: payload,
    };

    if (this._hasBm25Schema) {
      const text = payload.textLemmatized || payload.data || "";
      record.text = typeof text === "string" ? text.slice(0, 65535) : "";
    }

    await this.client.upsert({
      collection_name: this.collectionName,
      data: [record],
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
    const queryFilter = this.createFilter(filters);

    const response = await this.client.query({
      collection_name: this.collectionName,
      filter: queryFilter || "id != ''",
      limit: topK,
      output_fields: ["id", "metadata"],
    });

    const results = (response.data || []).map((row: any) => ({
      id: String(row.id),
      payload: row.metadata || {},
    }));

    return [results, results.length];
  }

  async getUserId(): Promise<string> {
    try {
      await this.ensureCollection(MIGRATION_COLLECTION, 2);

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
            id: uuidv4(),
            vectors: [0, 0],
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
      await this.ensureCollection(MIGRATION_COLLECTION, 2);

      const response = await this.client.query({
        collection_name: MIGRATION_COLLECTION,
        filter: "id != ''",
        limit: 1,
        output_fields: ["id"],
      });

      const pointId =
        response.data && response.data.length > 0
          ? response.data[0].id
          : uuidv4();

      await this.client.upsert({
        collection_name: MIGRATION_COLLECTION,
        data: [
          {
            id: pointId,
            vectors: [0, 0],
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

    if (hasCol.value) {
      if (name === this.collectionName) {
        const desc = await this.client.describeCollection({
          collection_name: name,
        });
        const fieldNames = new Set(
          ((desc as any).fields || []).map((f: any) => f.name),
        );
        this._hasBm25Schema =
          fieldNames.has("text") && fieldNames.has("sparse");
        if (!this._hasBm25Schema) {
          console.warn(
            `Collection '${name}' predates v3 hybrid search (no 'text'/'sparse' fields). ` +
              "BM25 keyword scoring will be disabled for this collection; semantic search works normally. " +
              "To enable hybrid search, use a fresh collection.",
          );
        }
      }
      return;
    }

    const isMainCollection = name === this.collectionName;

    const fields: any[] = [
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

    const indexParams: any[] = [
      {
        field_name: "vectors",
        metric_type: isMainCollection ? this.metricType : "COSINE",
        index_type: "AUTOINDEX",
        index_name: "vector_index",
      },
    ];

    const functions: any[] = [];

    if (isMainCollection) {
      fields.push(
        {
          name: "text",
          data_type: DataType.VarChar,
          max_length: 65535,
          enable_analyzer: true,
        },
        { name: "sparse", data_type: DataType.SparseFloatVector },
      );
      indexParams.push({
        field_name: "sparse",
        index_type: "SPARSE_INVERTED_INDEX",
        metric_type: "BM25",
        index_name: "sparse_index",
      });
      functions.push({
        name: "bm25",
        type: FunctionType.BM25,
        input_field_names: ["text"],
        output_field_names: ["sparse"],
        params: {},
      });
    }

    await this.client.createCollection({
      collection_name: name,
      fields,
      functions: functions.length > 0 ? functions : undefined,
      index_params: indexParams,
      enable_dynamic_field: true,
    } as any);

    if (isMainCollection) {
      this._hasBm25Schema = true;
    }
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
      await this.ensureCollection(MIGRATION_COLLECTION, 2);
    } catch (error) {
      console.error("Error initializing MilvusDB:", error);
      throw error;
    }
  }
}
