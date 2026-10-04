import type {
  GetOutputVector,
  ListOutputVector,
  QueryOutputVector,
  VectorData,
} from "@aws-sdk/client-s3vectors";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

const MIGRATION_INDEX_NAME = "memory_migrations";
const MIGRATION_VECTOR_KEY = "mem0-user";
const DEFAULT_PAGE_SIZE = 500;
const ALWAYS_FALSE_FILTER_KEY = "$alwaysFalse";

type S3Filter = Record<string, any>;

interface S3VectorsConfig extends VectorStoreConfig {
  vectorBucketName: string;
  collectionName: string;
  embeddingModelDims?: number;
  dimension?: number;
  distanceMetric?: "cosine" | "euclidean";
  region?: string;
  regionName?: string;
  client?: S3VectorsClientLike;
  /** Pre-configured S3 Vectors client options (typed as `any` to keep the
   *  optional SDK's types out of the published type declarations). */
  clientConfig?: any;
}

interface S3VectorsClientLike {
  send(command: any): Promise<any>;
}

export class S3Vectors implements VectorStore {
  private readonly config: S3VectorsConfig;
  private readonly vectorBucketName: string;
  private readonly collectionName: string;
  private readonly dimension: number;
  private readonly distanceMetric: "cosine" | "euclidean";
  private client?: S3VectorsClientLike;
  private clientPromise?: Promise<S3VectorsClientLike>;
  private sdkPromise?: Promise<any>;
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

    this.config = config;
    this.vectorBucketName = config.vectorBucketName;
    this.collectionName = config.collectionName;
    this.dimension = dimension;
    this.distanceMetric = config.distanceMetric || "cosine";

    void this.initialize().catch(console.error);
  }

  /**
   * Lazily import the optional `@aws-sdk/client-s3vectors` peer so consumers
   * who never use the S3 Vectors store don't need it installed.
   */
  private getSdk(): Promise<any> {
    if (!this.sdkPromise) {
      this.sdkPromise = import("@aws-sdk/client-s3vectors").catch(() => {
        throw new Error(
          "The '@aws-sdk/client-s3vectors' package is required to use the S3 Vectors store. Install it with: npm install @aws-sdk/client-s3vectors",
        );
      });
    }
    return this.sdkPromise;
  }

  /** Lazily construct (or reuse) the S3 Vectors client. */
  private async getClient(): Promise<S3VectorsClientLike> {
    if (this.client) return this.client;
    if (!this.clientPromise) {
      this.clientPromise = this.createClient();
    }
    this.client = await this.clientPromise;
    return this.client;
  }

  private async createClient(): Promise<S3VectorsClientLike> {
    const config = this.config;
    if (config.client) {
      return config.client;
    }

    const sdk = await this.getSdk();
    return new sdk.S3VectorsClient({
      ...(config.clientConfig || {}),
      ...(config.region || config.regionName
        ? { region: config.region || config.regionName }
        : {}),
    });
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

    const sdk = await this.getSdk();
    const client = await this.getClient();
    await client.send(
      new sdk.PutVectorsCommand({
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
    if (filter && this.isAlwaysFalseFilter(filter)) {
      return [];
    }
    const sdk = await this.getSdk();
    const client = await this.getClient();
    const response = await client.send(
      new sdk.QueryVectorsCommand({
        vectorBucketName: this.vectorBucketName,
        indexName: this.collectionName,
        queryVector: this.toVectorData(query),
        topK,
        filter,
        returnMetadata: true,
        returnDistance: true,
      }),
    );

    const responseDistanceMetric =
      response.distanceMetric || this.distanceMetric;
    return (response.vectors || [])
      .map((vector: QueryOutputVector) =>
        this.normalizeQueryVector(vector, responseDistanceMetric),
      )
      .slice(0, topK);
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();

    const sdk = await this.getSdk();
    const client = await this.getClient();
    try {
      const response = await client.send(
        new sdk.GetVectorsCommand({
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

    const sdk = await this.getSdk();
    const client = await this.getClient();
    await client.send(
      new sdk.PutVectorsCommand({
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

    const sdk = await this.getSdk();
    const client = await this.getClient();
    await client.send(
      new sdk.DeleteVectorsCommand({
        vectorBucketName: this.vectorBucketName,
        indexName: this.collectionName,
        keys: [vectorId],
      }),
    );
  }

  async deleteCol(): Promise<void> {
    await this.initialize();

    const sdk = await this.getSdk();
    const client = await this.getClient();
    try {
      await client.send(
        new sdk.DeleteIndexCommand({
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
    let nextToken: string | undefined;
    const sdk = await this.getSdk();
    const client = await this.getClient();

    // Stop paginating once we have topK matches. Both callers of list()
    // discard the count, so scanning the whole index just to total every
    // match is wasted round-trips (O(index size) on getAll/deleteAll).
    // Return the page length like qdrant does.
    do {
      const response = await client.send(
        new sdk.ListVectorsCommand({
          vectorBucketName: this.vectorBucketName,
          indexName: this.collectionName,
          maxResults: DEFAULT_PAGE_SIZE,
          nextToken,
          returnMetadata: true,
        }),
      );

      for (const vector of response.vectors || []) {
        if (results.length >= topK) {
          break;
        }
        const normalized = this.normalizeListedVector(vector);
        if (filter && !this.matchesFilter(normalized.payload, filter)) {
          continue;
        }
        results.push(normalized);
      }

      nextToken = response.nextToken;
    } while (nextToken && results.length < topK);

    return [results, results.length];
  }

  async getUserId(): Promise<string> {
    await this.initialize();
    if (this.cachedUserId) {
      return this.cachedUserId;
    }

    await this.ensureMigrationIndex();

    const sdk = await this.getSdk();
    const client = await this.getClient();
    const response = await client.send(
      new sdk.GetVectorsCommand({
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

    const sdk = await this.getSdk();
    const client = await this.getClient();
    await client.send(
      new sdk.PutVectorsCommand({
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
    const sdk = await this.getSdk();
    const client = await this.getClient();
    try {
      await client.send(
        new sdk.GetVectorBucketCommand({
          vectorBucketName: this.vectorBucketName,
        }),
      );
    } catch (error) {
      if (!this.isNotFound(error)) {
        throw error;
      }

      try {
        await client.send(
          new sdk.CreateVectorBucketCommand({
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
    distanceMetric: "cosine" | "euclidean",
  ): Promise<void> {
    const sdk = await this.getSdk();
    const client = await this.getClient();
    try {
      await client.send(
        new sdk.GetIndexCommand({
          vectorBucketName: this.vectorBucketName,
          indexName,
        }),
      );
    } catch (error) {
      if (!this.isNotFound(error)) {
        throw error;
      }

      try {
        await client.send(
          new sdk.CreateIndexCommand({
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
    const sdk = await this.getSdk();
    const client = await this.getClient();
    const response = await client.send(
      new sdk.GetVectorsCommand({
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
    const normalized = this.convertFilterNode(filters);
    return this.isNoOpFilter(normalized) ? undefined : normalized;
  }

  private convertFilterNode(node: Record<string, any>): S3Filter {
    const clauses: S3Filter[] = [];

    for (const [key, value] of Object.entries(node)) {
      if (key === "$and" || key === "$or") {
        if (!Array.isArray(value) || value.length === 0) {
          throw new Error(`${key} filter requires a non-empty list`);
        }
        const normalizedEntries = value.map((entry) =>
          this.convertFilterNode(entry),
        );
        const entries = normalizedEntries.filter(
          (entry) => !this.isNoOpFilter(entry),
        );
        if (key === "$and") {
          if (entries.some((entry) => this.isAlwaysFalseFilter(entry))) {
            return { [ALWAYS_FALSE_FILTER_KEY]: true };
          }
          if (entries.length === 0) {
            continue;
          }
        } else {
          if (normalizedEntries.some((entry) => this.isNoOpFilter(entry))) {
            continue;
          }
          const viableEntries = entries.filter(
            (entry) => !this.isAlwaysFalseFilter(entry),
          );
          if (viableEntries.length === 0) {
            return { [ALWAYS_FALSE_FILTER_KEY]: true };
          }
          clauses.push(
            viableEntries.length === 1
              ? viableEntries[0]
              : { [key]: viableEntries },
          );
          continue;
        }
        clauses.push(entries.length === 1 ? entries[0] : { [key]: entries });
        continue;
      }

      if (key === "$not") {
        if (!Array.isArray(value) || value.length === 0) {
          throw new Error("$not filter requires a non-empty list");
        }

        const normalizedEntries = value.map((entry) =>
          this.convertFilterNode(entry),
        );
        if (normalizedEntries.some((entry) => this.isNoOpFilter(entry))) {
          return { [ALWAYS_FALSE_FILTER_KEY]: true };
        }
        const negated = normalizedEntries.filter(
          (entry) => !this.isAlwaysFalseFilter(entry),
        );
        if (negated.length === 0) {
          continue;
        }
        const negatedFilters = negated.map((entry) => this.negateFilter(entry));
        clauses.push(
          negatedFilters.length === 1
            ? negatedFilters[0]
            : { $and: negatedFilters },
        );
        continue;
      }

      const fieldFilter = this.convertFieldFilter(key, value);
      if (this.isAlwaysFalseFilter(fieldFilter)) {
        return fieldFilter;
      }
      if (this.isNoOpFilter(fieldFilter)) {
        continue;
      }
      clauses.push(fieldFilter);
    }

    if (clauses.some((entry) => this.isAlwaysFalseFilter(entry))) {
      return { [ALWAYS_FALSE_FILTER_KEY]: true };
    }
    if (clauses.length === 1) {
      return clauses[0];
    }
    if (clauses.length === 0) {
      return {};
    }

    return { $and: clauses };
  }

  private convertFieldFilter(key: string, value: any): S3Filter {
    if (value === "*") {
      return { [key]: { $exists: true } };
    }

    if (Array.isArray(value)) {
      if (value.length === 0) {
        return { [ALWAYS_FALSE_FILTER_KEY]: true };
      }
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
          if (!Array.isArray(operand) || operand.length === 0) {
            return { [ALWAYS_FALSE_FILTER_KEY]: true };
          }
          operators.$in = operand;
          break;
        case "nin":
          if (!Array.isArray(operand) || operand.length === 0) {
            break;
          }
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

    if (Object.keys(operators).length === 0) {
      return {};
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
    if (this.isAlwaysFalseFilter(filter)) {
      return false;
    }
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
          return true;
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

  private normalizeQueryVector(
    vector: QueryOutputVector,
    distanceMetric: "cosine" | "euclidean",
  ): VectorStoreResult {
    return {
      id: String(vector.key),
      payload: this.normalizeMetadata(vector.metadata),
      score: this.normalizeScore(vector.distance, distanceMetric),
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

  private normalizeScore(
    distance?: number,
    distanceMetric: "cosine" | "euclidean" = this.distanceMetric,
  ): number | undefined {
    if (distance === undefined || distance === null) {
      return undefined;
    }
    if (!Number.isFinite(distance)) {
      return undefined;
    }
    if (distanceMetric === "euclidean") {
      return 1 / (1 + distance);
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

  private isAlwaysFalseFilter(filter: S3Filter): boolean {
    return filter[ALWAYS_FALSE_FILTER_KEY] === true;
  }

  private isNoOpFilter(filter: S3Filter): boolean {
    return Object.keys(filter).length === 0;
  }
}
