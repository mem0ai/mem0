import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

/**
 * Try to import Pinecone client.
 * This is a peer dependency - users must install @pinecone-database/pinecone.
 */
let PineconeClient: any;

try {
  const pinecone = require("@pinecone-database/pinecone");
  PineconeClient = pinecone.Pinecone;
} catch {
  // Will throw at runtime if Pinecone is used without the SDK installed
}

/**
 * Serverless deployment configuration for Pinecone.
 */
export interface PineconeServerlessConfig {
  /** Cloud provider: "aws" | "gcp" | "azure" */
  cloud: string;
  /** Region for the serverless deployment (e.g., "us-east-1") */
  region: string;
}

/**
 * Pod-based deployment configuration for Pinecone.
 */
export interface PineconePodConfig {
  /** Environment for pod deployment */
  environment: string;
  /** Pod type (e.g., "p1.x1", "s1.x1") */
  podType?: string;
  /** Number of pods */
  pods?: number;
  /** Number of replicas */
  replicas?: number;
  /** Shards per pod */
  shards?: number;
}

/**
 * Configuration options for Pinecone vector store.
 */
export interface PineconeConfig extends VectorStoreConfig {
  /** Pinecone API key */
  apiKey?: string;
  /** Pinecone environment (legacy, for pod-based deployments) */
  environment?: string;
  /** Name of the index (collection). Defaults to "mem0" */
  collectionName?: string;
  /** Dimension of the embedding vectors */
  embeddingModelDims: number;
  /** Distance metric for similarity search. Defaults to "cosine" */
  metric?: "cosine" | "euclidean" | "dotproduct";
  /** Configuration for serverless deployment */
  serverlessConfig?: PineconeServerlessConfig;
  /** Configuration for pod-based deployment */
  podConfig?: PineconePodConfig;
  /** Namespace for isolating vectors within an index */
  namespace?: string;
  /** Batch size for upsert operations. Defaults to 100 */
  batchSize?: number;
  /** Extra parameters to pass to Pinecone client */
  extraParams?: Record<string, any>;
}

/**
 * Pinecone vector store implementation.
 *
 * Pinecone is a managed vector database for machine learning applications.
 * Requires @pinecone-database/pinecone as a peer dependency.
 *
 * @example
 * ```typescript
 * const store = new Pinecone({
 *   apiKey: "your-api-key",
 *   collectionName: "memories",
 *   embeddingModelDims: 1536,
 *   metric: "cosine",
 *   serverlessConfig: {
 *     cloud: "aws",
 *     region: "us-east-1",
 *   },
 * });
 * await store.initialize();
 * ```
 */
export class Pinecone implements VectorStore {
  private client: any;
  private index: any;
  private collectionName: string;
  private embeddingModelDims: number;
  private metric: "cosine" | "euclidean" | "dotproduct";
  private serverlessConfig?: PineconeServerlessConfig;
  private podConfig?: PineconePodConfig;
  private namespace?: string;
  private batchSize: number;
  private userId: string = "";

  constructor(config: PineconeConfig) {
    if (!PineconeClient) {
      throw new Error(
        "The '@pinecone-database/pinecone' package is required. " +
          "Please install it using 'npm install @pinecone-database/pinecone'.",
      );
    }

    if (!config.embeddingModelDims) {
      throw new Error("embeddingModelDims is required for Pinecone");
    }

    const apiKey = config.apiKey || process.env.PINECONE_API_KEY;
    if (!apiKey) {
      throw new Error(
        "Pinecone API key must be provided either in config or as PINECONE_API_KEY environment variable",
      );
    }

    this.collectionName = config.collectionName || "mem0";
    this.embeddingModelDims = config.embeddingModelDims;
    this.metric = config.metric || "cosine";
    this.serverlessConfig = config.serverlessConfig;
    this.podConfig = config.podConfig;
    this.namespace = config.namespace;
    this.batchSize = config.batchSize || 100;

    const clientParams: Record<string, any> = {
      apiKey,
      ...config.extraParams,
    };

    this.client = new PineconeClient(clientParams);
  }

  /**
   * Initialize the vector store by ensuring the index exists.
   */
  async initialize(): Promise<void> {
    await this.ensureIndexExists();
    this.index = this.client.index(this.collectionName);
  }

  /**
   * Ensure the Pinecone index exists, creating it if necessary.
   */
  private async ensureIndexExists(): Promise<void> {
    const existingIndexes = await this.client.listIndexes();
    const indexNames =
      existingIndexes.indexes?.map((idx: any) => idx.name) || [];

    if (indexNames.includes(this.collectionName)) {
      return;
    }

    console.log(`Index '${this.collectionName}' not found. Creating it.`);

    let spec: Record<string, any>;

    if (this.serverlessConfig) {
      spec = {
        serverless: {
          cloud: this.serverlessConfig.cloud,
          region: this.serverlessConfig.region,
        },
      };
    } else if (this.podConfig) {
      spec = {
        pod: {
          environment: this.podConfig.environment,
          podType: this.podConfig.podType || "p1.x1",
          pods: this.podConfig.pods || 1,
          replicas: this.podConfig.replicas || 1,
          shards: this.podConfig.shards || 1,
        },
      };
    } else {
      // Default to serverless AWS us-east-1
      spec = {
        serverless: {
          cloud: "aws",
          region: "us-east-1",
        },
      };
    }

    await this.client.createIndex({
      name: this.collectionName,
      dimension: this.embeddingModelDims,
      metric: this.metric,
      spec,
    });

    // Wait for index to be ready
    await this.waitForIndexReady();

    console.log(`Index '${this.collectionName}' created.`);
  }

  /**
   * Wait for the index to be ready after creation.
   */
  private async waitForIndexReady(maxWaitMs: number = 60000): Promise<void> {
    const startTime = Date.now();
    const pollIntervalMs = 1000;

    while (Date.now() - startTime < maxWaitMs) {
      const description = await this.client.describeIndex(this.collectionName);
      if (description.status?.ready) {
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, pollIntervalMs));
    }

    throw new Error(
      `Index '${this.collectionName}' did not become ready within ${maxWaitMs}ms`,
    );
  }

  /**
   * Insert vectors into the index.
   */
  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const items: any[] = [];

    for (let i = 0; i < vectors.length; i++) {
      items.push({
        id: ids[i],
        values: vectors[i],
        metadata: payloads[i] || {},
      });

      // Batch upsert when we reach batch size
      if (items.length >= this.batchSize) {
        await this.upsertBatch(items);
        items.length = 0;
      }
    }

    // Upsert remaining items
    if (items.length > 0) {
      await this.upsertBatch(items);
    }
  }

  /**
   * Upsert a batch of vectors to the index.
   */
  private async upsertBatch(items: any[]): Promise<void> {
    const targetIndex = this.namespace
      ? this.index.namespace(this.namespace)
      : this.index;
    await targetIndex.upsert(items);
  }

  /**
   * Search for similar vectors.
   *
   * @param query - Query vector
   * @param limit - Maximum number of results to return
   * @param filters - Optional metadata filters
   * @returns Array of results sorted by similarity score (descending)
   */
  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const queryParams: Record<string, any> = {
      vector: query,
      topK: limit,
      includeMetadata: true,
      includeValues: false,
    };

    if (filters && Object.keys(filters).length > 0) {
      queryParams.filter = this.transformFilters(filters);
    }

    const targetIndex = this.namespace
      ? this.index.namespace(this.namespace)
      : this.index;

    const response = await targetIndex.query(queryParams);
    const matches = response.matches || [];

    return matches.map((match: any) => ({
      id: match.id,
      payload: match.metadata || {},
      score: match.score,
    }));
  }

  /**
   * Get a vector by ID.
   */
  async get(vectorId: string): Promise<VectorStoreResult | null> {
    try {
      const targetIndex = this.namespace
        ? this.index.namespace(this.namespace)
        : this.index;

      const response = await targetIndex.fetch([vectorId]);

      if (!response.records || !response.records[vectorId]) {
        return null;
      }

      const record = response.records[vectorId];
      return {
        id: vectorId,
        payload: record.metadata || {},
      };
    } catch (error: any) {
      // Return null if not found
      if (error?.message?.includes("not found")) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Update a vector by ID.
   * Pinecone uses upsert for updates (overwrite).
   */
  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.insert([vector], [vectorId], [payload]);
  }

  /**
   * Delete a vector by ID.
   */
  async delete(vectorId: string): Promise<void> {
    const targetIndex = this.namespace
      ? this.index.namespace(this.namespace)
      : this.index;

    await targetIndex.deleteOne(vectorId);
  }

  /**
   * Delete the entire index.
   */
  async deleteCol(): Promise<void> {
    try {
      await this.client.deleteIndex(this.collectionName);
      console.log(`Index '${this.collectionName}' deleted successfully.`);
    } catch (error: any) {
      console.error(`Error deleting index '${this.collectionName}':`, error);
      throw error;
    }
  }

  /**
   * List vectors in the index.
   *
   * Note: Pinecone doesn't have a direct list operation.
   * This uses a zero-vector query to approximate listing.
   */
  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    // Pinecone doesn't have a direct list operation
    // We use a zero vector query with high topK to approximate listing
    const zeroVector = new Array(this.embeddingModelDims).fill(0);

    const queryParams: Record<string, any> = {
      vector: zeroVector,
      topK: limit,
      includeMetadata: true,
      includeValues: false,
    };

    if (filters && Object.keys(filters).length > 0) {
      queryParams.filter = this.transformFilters(filters);
    }

    const targetIndex = this.namespace
      ? this.index.namespace(this.namespace)
      : this.index;

    const response = await targetIndex.query(queryParams);
    const matches = response.matches || [];

    const results = matches.map((match: any) => ({
      id: match.id,
      payload: match.metadata || {},
    }));

    return [results, results.length];
  }

  /**
   * Get the current user ID.
   */
  async getUserId(): Promise<string> {
    return this.userId;
  }

  /**
   * Set the user ID.
   */
  async setUserId(userId: string): Promise<void> {
    this.userId = userId;
  }

  /**
   * Transform SearchFilters to Pinecone filter format.
   */
  private transformFilters(filters: SearchFilters): Record<string, any> {
    const pineconeFilter: Record<string, any> = {};

    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null) {
        continue;
      }

      if (
        typeof value === "object" &&
        value !== null &&
        "gte" in value &&
        "lte" in value
      ) {
        // Range filter
        pineconeFilter[key] = {
          $gte: value.gte,
          $lte: value.lte,
        };
      } else {
        // Equality filter
        pineconeFilter[key] = { $eq: value };
      }
    }

    return pineconeFilter;
  }

  /**
   * Get index statistics.
   */
  async getStats(): Promise<Record<string, any>> {
    const targetIndex = this.namespace
      ? this.index.namespace(this.namespace)
      : this.index;

    return await targetIndex.describeIndexStats();
  }

  /**
   * Get the number of vectors in the index.
   */
  async count(): Promise<number> {
    const stats = await this.getStats();

    if (this.namespace && stats.namespaces) {
      const namespaceStats = stats.namespaces[this.namespace];
      return namespaceStats?.vectorCount || 0;
    }

    return stats.totalVectorCount || 0;
  }
}
