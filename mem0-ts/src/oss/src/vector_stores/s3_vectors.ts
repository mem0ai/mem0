import {
  CreateIndexCommand,
  CreateVectorBucketCommand,
  DeleteIndexCommand,
  DeleteVectorsCommand,
  GetIndexCommand,
  GetVectorBucketCommand,
  GetVectorsCommand,
  ListVectorsCommand,
  PutVectorsCommand,
  QueryVectorsCommand,
  S3VectorsClient,
  type DistanceMetric,
  type GetOutputVector,
  type ListOutputVector,
  type QueryOutputVector,
  type S3VectorsClientConfig,
  type VectorData,
} from "@aws-sdk/client-s3vectors";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

const MIGRATION_INDEX_NAME = "memory_migrations";
const MIGRATION_VECTOR_KEY = "mem0-user";
const DEFAULT_PAGE_SIZE = 500;

type S3Filter = Record<string, any>;

interface S3VectorsConfig extends VectorStoreConfig {
  vectorBucketName: string;
  collectionName: string;
  embeddingModelDims?: number;
  dimension?: number;
  distanceMetric?: DistanceMetric | "cosine" | "euclidean";
  region?: string;
  regionName?: string;
  client?: S3VectorsClientLike;
  clientConfig?: S3VectorsClientConfig;
}

interface S3VectorsClientLike {
  send(command: any): Promise<any>;
}

export class S3Vectors implements VectorStore {
  private readonly client: S3VectorsClientLike;
  private readonly vectorBucketName: string;
  private readonly collectionName: string;
  private readonly dimension: number;
  private readonly distanceMetric: DistanceMetric | "cosine" | "euclidean";
  private _initPromise?: Promise<void>;
  private cachedUserId?: string;

  constructor(config: S3VectorsConfig) {
    if (!config.vectorBucketName) {
      throw new Error("vectorBucketName is required");
    }
    if (!config.collectionName) {
      throw new Error("collectionName is required");
    }

    const dimension = config.embeddingModelDims ?? config.dimension;
    if (!dimension || dimension < 1) {
      throw new Error("embeddingModelDims or dimension is required");
    }

    this.vectorBucketName = config.vectorBucketName;
    this.collectionName = config.collectionName;
    this.dimension = dimension;
    this.distanceMetric = config.distanceMetric || "cosine";
    this.client =
      config.client ||
      new S3VectorsClient({
        ...(config.clientConfig || {}),
        ...(config.region || config.regionName
          ? { region: config.region || config.regionName }
          : {}),
      });

    void this.initialize().catch(console.error);
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    await this.ensureBucketExists();
    await this.ensureIndexExists(
      this.collectionName,
      this.dimension,
      this.distanceMetric,
    );
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();
    this.assertBatchDimensions(vectors, "Insert");

    await this.client.send(
      new PutVectorsCommand({
        vectorBucketName: this.vectorBucketName,
        indexName: this.collectionName,
        vectors: vectors.map((vector, index) => ({
          key: ids[index],
          data: this.toVectorData(vector),
          metadata: payloads[index] || {},
        })),
      }),
    );
  }

  async keywordSearch(): Promise<null> {
    return null;
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();
    this.assertVectorDimension(query, "Query");

    const filter = this.convertFilters(filters);
    const results: VectorStoreResult[] = [];
    let nextToken: string | undefined;

    do {
      const response = await this.client.send(
        new QueryVectorsCommand({
          vectorBucketName: this.vectorBucketName,
          indexName: this.collectionName,
          queryVector: this.toVectorData(query),
          topK,
          filter,
          returnMetadata: true,
          returnDistance: true,
          nextToken,
        }),
      );

      for (const vector of response.vectors || []) {
        results.push(this.normalizeQueryVector(vector));
        if (results.length >= topK) {
          return results.slice(0, topK);
        }
      }

      nextToken = response.nextToken;
    } while (nextToken);

    return results;
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();

    try {
      const response = await this.client.send(
        new GetVectorsCommand({
          vectorBucketName: this.vectorBucketName,
          indexName: this.collectionName,
          keys: [vectorId],
          returnMetadata: true,
        }),
      );

      const vector = response.vectors?.[0];
      if (!vector) {
        return null;
      }

      return this.normalizeStoredVector(vector);
    } catch (error) {
      if (this.isNotFound(error)) {
        return null;
      }
      throw error;
    }
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();

    let nextVector = vector;
    let nextPayload = payload || {};

    if (vector.length === 0 || !payload) {
      const existing = await this.fetchStoredVector(vectorId);
      if (!existing) {
        throw new Error(`Vector with ID ${vectorId} not found`);
      }
      nextVector = vector.length > 0 ? vector : existing.vector;
      nextPayload = payload || existing.payload;
    }

    this.assertVectorDimension(nextVector, "Vector");

    await this.client.send(
      new PutVectorsCommand({
        vectorBucketName: this.vectorBucketName,
        indexName: this.collectionName,
        vectors: [
          {
            key: vectorId,
            data: this.toVectorData(nextVector),
            metadata: nextPayload,
          },
        ],
      }),
    );
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();

    await this.client.send(
      new DeleteVectorsCommand({
        vectorBucketName: this.vectorBucketName,
        indexName: this.collectionName,
        keys: [vectorId],
      }),
    );
  }

  async deleteCol(): Promise<void> {
    await this.initialize();

    try {
      await this.client.send(
        new DeleteIndexCommand({
          vectorBucketName: this.vectorBucketName,
          indexName: this.collectionName,
        }),
      );
    } catch (error) {
      if (this.isNotFound(error)) {
        return;
      }
      throw error;
    }
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();

    const filter = this.convertFilters(filters);
    const results: VectorStoreResult[] = [];
    let total = 0;
    let nextToken: string | undefined;

    do {
      const response = await this.client.send(
        new ListVectorsCommand({
          vectorBucketName: this.vectorBucketName,
          indexName: this.collectionName,
          maxResults: DEFAULT_PAGE_SIZE,
          nextToken,
          returnMetadata: true,
        }),
      );

      for (const vector of response.vectors || []) {
        const normalized = this.normalizeListedVector(vector);
        if (filter && !this.matchesFilter(normalized.payload, filter)) {
          continue;
        }

        total += 1;
        if (results.length < topK) {
          results.push(normalized);
        }
      }

      nextToken = response.nextToken;
    } while (nextToken);

    return [results, total];
  }

  async getUserId(): Promise<string> {
    await this.initialize();
    if (this.cachedUserId) {
      return this.cachedUserId;
    }

    await this.ensureMigrationIndex();

    const response = await this.client.send(
      new GetVectorsCommand({
        vectorBucketName: this.vectorBucketName,
        indexName: MIGRATION_INDEX_NAME,
        keys: [MIGRATION_VECTOR_KEY],
        returnMetadata: true,
      }),
    );

    const metadata = this.normalizeMetadata(response.vectors?.[0]?.metadata);
    const userId = metadata.user_id;
    if (typeof userId === "string" && userId.length > 0) {
      this.cachedUserId = userId;
      return userId;
    }

    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.setUserId(randomUserId);
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();
    await this.ensureMigrationIndex();

    await this.client.send(
      new PutVectorsCommand({
        vectorBucketName: this.vectorBucketName,
        indexName: MIGRATION_INDEX_NAME,
        vectors: [
          {
            key: MIGRATION_VECTOR_KEY,
            data: this.toVectorData([0]),
            metadata: { user_id: userId },
          },
        ],
      }),
    );

    this.cachedUserId = userId;
  }

  private async ensureBucketExists(): Promise<void> {
    try {
      await this.client.send(
        new GetVectorBucketCommand({
          vectorBucketName: this.vectorBucketName,
        }),
      );
    } catch (error) {
      if (!this.isNotFound(error)) {
        throw error;
      }

      try {
        await this.client.send(
          new CreateVectorBucketCommand({
            vectorBucketName: this.vectorBucketName,
          }),
        );
      } catch (createError) {
        if (!this.isConflict(createError)) {
          throw createError;
        }
      }
    }
  }

  private async ensureIndexExists(
    indexName: string,
    dimension: number,
    distanceMetric: DistanceMetric | "cosine" | "euclidean",
  ): Promise<void> {
    try {
      await this.client.send(
        new GetIndexCommand({
          vectorBucketName: this.vectorBucketName,
          indexName,
        }),
      );
    } catch (error) {
      if (!this.isNotFound(error)) {
        throw error;
      }

      try {
        await this.client.send(
          new CreateIndexCommand({
            vectorBucketName: this.vectorBucketName,
            indexName,
            dataType: "float32",
            dimension,
            distanceMetric,
          }),
        );
      } catch (createError) {
        if (!this.isConflict(createError)) {
          throw createError;
        }
      }
    }
  }

  private async ensureMigrationIndex(): Promise<void> {
    await this.ensureIndexExists(MIGRATION_INDEX_NAME, 1, "euclidean");
  }

  private async fetchStoredVector(
    vectorId: string,
  ): Promise<{ vector: number[]; payload: Record<string, any> } | null> {
    const response = await this.client.send(
      new GetVectorsCommand({
        vectorBucketName: this.vectorBucketName,
        indexName: this.collectionName,
        keys: [vectorId],
        returnData: true,
        returnMetadata: true,
      }),
    );

    const vector = response.vectors?.[0];
    const data = this.fromVectorData(vector?.data);
    if (!vector || !data) {
      return null;
    }

    return {
      vector: data,
      payload: this.normalizeMetadata(vector.metadata),
    };
  }

  private convertFilters(filters?: SearchFilters): S3Filter | undefined {
    if (!filters || Object.keys(filters).length === 0) {
      return undefined;
    }
    return this.convertFilterNode(filters);
  }

  private convertFilterNode(node: Record<string, any>): S3Filter {
    const clauses: S3Filter[] = [];

    for (const [key, value] of Object.entries(node)) {
      if (key === "$and" || key === "$or") {
        if (!Array.isArray(value) || value.length === 0) {
          throw new Error(`${key} filter requires a non-empty list`);
        }
        clauses.push({
          [key]: value.map((entry) => this.convertFilterNode(entry)),
        });
        continue;
      }

      if (key === "$not") {
        if (!Array.isArray(value) || value.length === 0) {
          throw new Error("$not filter requires a non-empty list");
        }

        const negated = value.map((entry) =>
          this.negateFilter(this.convertFilterNode(entry)),
        );
        clauses.push(negated.length === 1 ? negated[0] : { $and: negated });
        continue;
      }

      clauses.push(this.convertFieldFilter(key, value));
    }

    if (clauses.length === 1) {
      return clauses[0];
    }

    return { $and: clauses };
  }

  private convertFieldFilter(key: string, value: any): S3Filter {
    if (value === "*") {
      return { [key]: { $exists: true } };
    }

    if (Array.isArray(value)) {
      return { [key]: { $in: value } };
    }

    if (typeof value !== "object" || value === null) {
      return { [key]: { $eq: value } };
    }

    const operators: Record<string, any> = {};

    for (const [operator, operand] of Object.entries(value)) {
      switch (operator) {
        case "eq":
          operators.$eq = operand;
          break;
        case "ne":
          operators.$ne = operand;
          break;
        case "gt":
          operators.$gt = operand;
          break;
        case "gte":
          operators.$gte = operand;
          break;
        case "lt":
          operators.$lt = operand;
          break;
        case "lte":
          operators.$lte = operand;
          break;
        case "in":
          operators.$in = operand;
          break;
        case "nin":
          operators.$nin = operand;
          break;
        case "contains":
        case "icontains":
        case "startsWith":
          throw new Error(
            `S3 Vectors does not support '${operator}' metadata filters.`,
          );
        default:
          throw new Error(
            `Unsupported S3 Vectors filter operator: ${operator}`,
          );
      }
    }

    return { [key]: operators };
  }

  private negateFilter(filter: S3Filter): S3Filter {
    if (Array.isArray(filter.$and)) {
      return {
        $or: filter.$and.map((entry: S3Filter) => this.negateFilter(entry)),
      };
    }

    if (Array.isArray(filter.$or)) {
      return {
        $and: filter.$or.map((entry: S3Filter) => this.negateFilter(entry)),
      };
    }

    const entries = Object.entries(filter);
    if (entries.length !== 1) {
      throw new Error("S3 Vectors cannot negate this filter shape.");
    }

    const [key, rawValue] = entries[0];
    if (key.startsWith("$")) {
      throw new Error("S3 Vectors cannot negate this filter shape.");
    }

    const value =
      typeof rawValue === "object" && rawValue !== null
        ? rawValue
        : { $eq: rawValue };
    const negated: Record<string, any> = {};

    for (const [operator, operand] of Object.entries(value)) {
      switch (operator) {
        case "$eq":
          negated.$ne = operand;
          break;
        case "$ne":
          negated.$eq = operand;
          break;
        case "$gt":
          negated.$lte = operand;
          break;
        case "$gte":
          negated.$lt = operand;
          break;
        case "$lt":
          negated.$gte = operand;
          break;
        case "$lte":
          negated.$gt = operand;
          break;
        case "$in":
          negated.$nin = operand;
          break;
        case "$nin":
          negated.$in = operand;
          break;
        case "$exists":
          negated.$exists = !operand;
          break;
        default:
          throw new Error("S3 Vectors cannot negate this filter shape.");
      }
    }

    return { [key]: negated };
  }

  private matchesFilter(
    metadata: Record<string, any>,
    filter: S3Filter,
  ): boolean {
    if (Array.isArray(filter.$and)) {
      return filter.$and.every((entry: S3Filter) =>
        this.matchesFilter(metadata, entry),
      );
    }

    if (Array.isArray(filter.$or)) {
      return filter.$or.some((entry: S3Filter) =>
        this.matchesFilter(metadata, entry),
      );
    }

    return Object.entries(filter).every(([key, rawValue]) =>
      this.matchesFieldFilter(metadata[key], rawValue),
    );
  }

  private matchesFieldFilter(metadataValue: any, rawValue: any): boolean {
    const value =
      typeof rawValue === "object" && rawValue !== null
        ? rawValue
        : { $eq: rawValue };

    return Object.entries(value).every(([operator, operand]) =>
      this.evaluateOperator(metadataValue, operator, operand),
    );
  }

  private evaluateOperator(
    metadataValue: any,
    operator: string,
    operand: any,
  ): boolean {
    switch (operator) {
      case "$eq":
        if (Array.isArray(metadataValue)) {
          return metadataValue.some((entry) => entry === operand);
        }
        return metadataValue === operand;
      case "$ne":
        if (Array.isArray(metadataValue)) {
          return !metadataValue.some((entry) => entry === operand);
        }
        return metadataValue !== operand;
      case "$gt":
        return typeof metadataValue === "number" && metadataValue > operand;
      case "$gte":
        return typeof metadataValue === "number" && metadataValue >= operand;
      case "$lt":
        return typeof metadataValue === "number" && metadataValue < operand;
      case "$lte":
        return typeof metadataValue === "number" && metadataValue <= operand;
      case "$in":
        if (!Array.isArray(operand) || operand.length === 0) {
          return false;
        }
        if (Array.isArray(metadataValue)) {
          return metadataValue.some((entry) => operand.includes(entry));
        }
        return operand.includes(metadataValue);
      case "$nin":
        if (!Array.isArray(operand) || operand.length === 0) {
          return false;
        }
        if (Array.isArray(metadataValue)) {
          return metadataValue.every((entry) => !operand.includes(entry));
        }
        return !operand.includes(metadataValue);
      case "$exists":
        return operand
          ? metadataValue !== undefined
          : metadataValue === undefined;
      default:
        throw new Error(`Unsupported S3 Vectors filter operator: ${operator}`);
    }
  }

  private toVectorData(vector: number[]): VectorData {
    return { float32: vector };
  }

  private fromVectorData(data?: VectorData): number[] | undefined {
    if (!data || !("float32" in data) || !Array.isArray(data.float32)) {
      return undefined;
    }
    return data.float32;
  }

  private normalizeMetadata(metadata: any): Record<string, any> {
    if (metadata && typeof metadata === "object" && !Array.isArray(metadata)) {
      return { ...(metadata as Record<string, any>) };
    }
    return {};
  }

  private normalizeQueryVector(vector: QueryOutputVector): VectorStoreResult {
    return {
      id: String(vector.key),
      payload: this.normalizeMetadata(vector.metadata),
      score: this.normalizeScore(vector.distance),
    };
  }

  private normalizeStoredVector(
    vector: GetOutputVector | ListOutputVector,
  ): VectorStoreResult {
    return {
      id: String(vector.key),
      payload: this.normalizeMetadata(vector.metadata),
    };
  }

  private normalizeListedVector(vector: ListOutputVector): VectorStoreResult {
    return this.normalizeStoredVector(vector);
  }

  private normalizeScore(distance?: number): number | undefined {
    if (distance === undefined || distance === null) {
      return undefined;
    }
    if (!Number.isFinite(distance)) {
      return undefined;
    }
    return Math.max(0, Math.min(1, 1 - distance));
  }

  private assertVectorDimension(vector: number[], context: string): void {
    if (vector.length !== this.dimension) {
      throw new Error(
        `${context} dimension mismatch. Expected ${this.dimension}, got ${vector.length}`,
      );
    }
  }

  private assertBatchDimensions(vectors: number[][], context: string): void {
    for (const vector of vectors) {
      this.assertVectorDimension(vector, context);
    }
  }

  private isNotFound(error: any): boolean {
    return error?.name === "NotFoundException";
  }

  private isConflict(error: any): boolean {
    return error?.name === "ConflictException";
  }
}
