import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

/**
 * Try to import AWS SDK S3Vectors client.
 * This is a peer dependency - users must install @aws-sdk/client-s3vectors.
 */
let S3VectorsClient: any;
let CreateVectorBucketCommand: any;
let GetVectorBucketCommand: any;
let CreateIndexCommand: any;
let GetIndexCommand: any;
let PutVectorsCommand: any;
let QueryVectorsCommand: any;
let GetVectorsCommand: any;
let DeleteVectorsCommand: any;
let ListVectorsCommand: any;
let DeleteIndexCommand: any;
let ListIndexesCommand: any;

try {
  const s3vectors = require("@aws-sdk/client-s3vectors");
  S3VectorsClient = s3vectors.S3VectorsClient;
  CreateVectorBucketCommand = s3vectors.CreateVectorBucketCommand;
  GetVectorBucketCommand = s3vectors.GetVectorBucketCommand;
  CreateIndexCommand = s3vectors.CreateIndexCommand;
  GetIndexCommand = s3vectors.GetIndexCommand;
  PutVectorsCommand = s3vectors.PutVectorsCommand;
  QueryVectorsCommand = s3vectors.QueryVectorsCommand;
  GetVectorsCommand = s3vectors.GetVectorsCommand;
  DeleteVectorsCommand = s3vectors.DeleteVectorsCommand;
  ListVectorsCommand = s3vectors.ListVectorsCommand;
  DeleteIndexCommand = s3vectors.DeleteIndexCommand;
  ListIndexesCommand = s3vectors.ListIndexesCommand;
} catch {
  // Will throw at runtime if S3Vectors is used without the SDK installed
}

/**
 * Configuration options for S3Vectors vector store.
 */
export interface S3VectorsConfig extends VectorStoreConfig {
  /** Name of the S3 Vector bucket */
  vectorBucketName: string;
  /** Name of the vector index (collection). Defaults to "mem0" */
  collectionName?: string;
  /** Dimension of the embedding vectors */
  embeddingModelDims: number;
  /** Distance metric for similarity search. Defaults to "cosine" */
  distanceMetric?: "cosine" | "euclidean";
  /** AWS region for the S3 Vectors client */
  region?: string;
  /** Optional explicit AWS credentials */
  credentials?: {
    accessKeyId: string;
    secretAccessKey: string;
  };
}

/**
 * S3Vectors vector store implementation.
 *
 * Amazon S3 Vectors is a fully managed vector database built into S3.
 * Requires @aws-sdk/client-s3vectors as a peer dependency.
 *
 * @example
 * ```typescript
 * const store = new S3Vectors({
 *   vectorBucketName: "my-vector-bucket",
 *   collectionName: "memories",
 *   embeddingModelDims: 1536,
 *   distanceMetric: "cosine",
 *   region: "us-east-1",
 * });
 * await store.initialize();
 * ```
 */
export class S3Vectors implements VectorStore {
  private client: any;
  private vectorBucketName: string;
  private collectionName: string;
  private embeddingModelDims: number;
  private distanceMetric: "cosine" | "euclidean";
  private userId: string = "";

  constructor(config: S3VectorsConfig) {
    if (!S3VectorsClient) {
      throw new Error(
        "The '@aws-sdk/client-s3vectors' package is required. " +
          "Please install it using 'npm install @aws-sdk/client-s3vectors'.",
      );
    }

    if (!config.vectorBucketName) {
      throw new Error("vectorBucketName is required for S3Vectors");
    }

    if (!config.embeddingModelDims) {
      throw new Error("embeddingModelDims is required for S3Vectors");
    }

    this.vectorBucketName = config.vectorBucketName;
    this.collectionName = config.collectionName || "mem0";
    this.embeddingModelDims = config.embeddingModelDims;
    this.distanceMetric = config.distanceMetric || "cosine";

    const clientConfig: any = {};
    if (config.region) {
      clientConfig.region = config.region;
    }
    if (config.credentials) {
      clientConfig.credentials = {
        accessKeyId: config.credentials.accessKeyId,
        secretAccessKey: config.credentials.secretAccessKey,
      };
    }

    this.client = new S3VectorsClient(clientConfig);
  }

  /**
   * Initialize the vector store by ensuring bucket and index exist.
   */
  async initialize(): Promise<void> {
    await this.ensureBucketExists();
    await this.ensureIndexExists();
  }

  /**
   * Ensure the vector bucket exists, creating it if necessary.
   */
  private async ensureBucketExists(): Promise<void> {
    try {
      await this.client.send(
        new GetVectorBucketCommand({
          vectorBucketName: this.vectorBucketName,
        }),
      );
    } catch (error: any) {
      if (
        error?.name === "NotFoundException" ||
        error?.$metadata?.httpStatusCode === 404
      ) {
        console.log(
          `Vector bucket '${this.vectorBucketName}' not found. Creating it.`,
        );
        await this.client.send(
          new CreateVectorBucketCommand({
            vectorBucketName: this.vectorBucketName,
          }),
        );
        console.log(`Vector bucket '${this.vectorBucketName}' created.`);
      } else {
        throw error;
      }
    }
  }

  /**
   * Ensure the vector index exists, creating it if necessary.
   */
  private async ensureIndexExists(): Promise<void> {
    try {
      await this.client.send(
        new GetIndexCommand({
          vectorBucketName: this.vectorBucketName,
          indexName: this.collectionName,
        }),
      );
    } catch (error: any) {
      if (
        error?.name === "NotFoundException" ||
        error?.$metadata?.httpStatusCode === 404
      ) {
        console.log(
          `Index '${this.collectionName}' not found in bucket '${this.vectorBucketName}'. Creating it.`,
        );
        await this.client.send(
          new CreateIndexCommand({
            vectorBucketName: this.vectorBucketName,
            indexName: this.collectionName,
            dataType: "float32",
            dimension: this.embeddingModelDims,
            distanceMetric: this.distanceMetric,
          }),
        );
        console.log(`Index '${this.collectionName}' created.`);
      } else {
        throw error;
      }
    }
  }

  /**
   * Insert vectors into the index.
   */
  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const vectorsToInsert = vectors.map((vec, i) => ({
      key: ids[i],
      data: { float32: vec },
      metadata: payloads[i] || {},
    }));

    await this.client.send(
      new PutVectorsCommand({
        vectorBucketName: this.vectorBucketName,
        indexName: this.collectionName,
        vectors: vectorsToInsert,
      }),
    );
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
    const params: any = {
      vectorBucketName: this.vectorBucketName,
      indexName: this.collectionName,
      queryVector: { float32: query },
      topK: limit,
      returnMetadata: true,
      returnDistance: true,
    };

    if (filters && Object.keys(filters).length > 0) {
      params.filter = this.transformFilters(filters);
    }

    const response = await this.client.send(new QueryVectorsCommand(params));
    const vectors = response.vectors || [];

    return vectors.map((v: any) => ({
      id: v.key,
      payload: this.parseMetadata(v.metadata),
      score: this.distanceToScore(v.distance ?? 0),
    }));
  }

  /**
   * Get a vector by ID.
   */
  async get(vectorId: string): Promise<VectorStoreResult | null> {
    try {
      const response = await this.client.send(
        new GetVectorsCommand({
          vectorBucketName: this.vectorBucketName,
          indexName: this.collectionName,
          keys: [vectorId],
          returnData: false,
          returnMetadata: true,
        }),
      );

      const vectors = response.vectors || [];
      if (vectors.length === 0) {
        return null;
      }

      const v = vectors[0];
      return {
        id: v.key,
        payload: this.parseMetadata(v.metadata),
      };
    } catch (error: any) {
      if (
        error?.name === "NotFoundException" ||
        error?.$metadata?.httpStatusCode === 404
      ) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Update a vector by ID.
   * S3 Vectors uses put_vectors for updates (overwrite).
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
    await this.client.send(
      new DeleteVectorsCommand({
        vectorBucketName: this.vectorBucketName,
        indexName: this.collectionName,
        keys: [vectorId],
      }),
    );
  }

  /**
   * Delete the entire collection (index).
   */
  async deleteCol(): Promise<void> {
    await this.client.send(
      new DeleteIndexCommand({
        vectorBucketName: this.vectorBucketName,
        indexName: this.collectionName,
      }),
    );
  }

  /**
   * List vectors in the index.
   *
   * Note: S3 Vectors list_vectors does not support metadata filtering.
   * Filters will be ignored with a warning.
   */
  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    if (filters && Object.keys(filters).length > 0) {
      console.warn(
        "S3 Vectors `list` does not support metadata filtering. Ignoring filters.",
      );
    }

    const params: any = {
      vectorBucketName: this.vectorBucketName,
      indexName: this.collectionName,
      returnData: false,
      returnMetadata: true,
      maxResults: limit,
    };

    const allVectors: any[] = [];
    let nextToken: string | undefined;

    do {
      if (nextToken) {
        params.nextToken = nextToken;
      }

      const response = await this.client.send(new ListVectorsCommand(params));
      const vectors = response.vectors || [];
      allVectors.push(...vectors);
      nextToken = response.nextToken;

      // Stop if we've reached the limit
      if (allVectors.length >= limit) {
        break;
      }
    } while (nextToken);

    const results = allVectors.slice(0, limit).map((v: any) => ({
      id: v.key,
      payload: this.parseMetadata(v.metadata),
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
   * Transform SearchFilters to S3 Vectors filter format.
   */
  private transformFilters(filters: SearchFilters): any {
    const conditions: any[] = [];

    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null) {
        conditions.push({
          [key]: { $eq: value },
        });
      }
    }

    if (conditions.length === 0) {
      return undefined;
    }

    if (conditions.length === 1) {
      return conditions[0];
    }

    return { $and: conditions };
  }

  /**
   * Parse metadata from response.
   * Handles both object and string (JSON) formats.
   */
  private parseMetadata(metadata: any): Record<string, any> {
    if (!metadata) {
      return {};
    }
    if (typeof metadata === "string") {
      try {
        return JSON.parse(metadata);
      } catch {
        console.warn("Failed to parse metadata as JSON");
        return {};
      }
    }
    return metadata;
  }

  /**
   * Convert distance to similarity score.
   * Score = 1 / (1 + distance) for monotonic transformation.
   */
  private distanceToScore(distance: number): number {
    return 1 / (1 + distance);
  }

  /**
   * Destroy the client and free resources.
   */
  async destroy(): Promise<void> {
    if (this.client?.destroy) {
      this.client.destroy();
    }
  }
}
