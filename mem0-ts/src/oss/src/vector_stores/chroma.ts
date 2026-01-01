import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

/**
 * Try to import ChromaDB client.
 * This is a peer dependency - users must install chromadb.
 */
let ChromaClient: any;
let CloudClient: any;

try {
  const chromadb = require("chromadb");
  ChromaClient = chromadb.ChromaClient;
  CloudClient = chromadb.CloudClient;
} catch {
  // Will throw at runtime if Chroma is used without the SDK installed
}

/**
 * Configuration options for ChromaDB vector store.
 */
export interface ChromaConfig extends VectorStoreConfig {
  /** Name of the collection. Defaults to "mem0" */
  collectionName?: string;
  /** Existing ChromaDB client instance */
  client?: any;
  /** Host address for ChromaDB server */
  host?: string;
  /** Port for ChromaDB server */
  port?: number;
  /** Path for local ChromaDB database */
  path?: string;
  /** ChromaDB Cloud API key */
  apiKey?: string;
  /** ChromaDB Cloud tenant ID */
  tenant?: string;
  /** ChromaDB Cloud database name. Defaults to "mem0" */
  database?: string;
}

/**
 * ChromaDB vector store implementation.
 *
 * ChromaDB is an open-source embedding database.
 * Requires chromadb as a peer dependency.
 *
 * @example
 * ```typescript
 * // Local persistent storage
 * const store = new Chroma({
 *   collectionName: "memories",
 *   path: "./chroma-data",
 * });
 *
 * // Server connection
 * const store = new Chroma({
 *   collectionName: "memories",
 *   host: "localhost",
 *   port: 8000,
 * });
 *
 * // Cloud connection
 * const store = new Chroma({
 *   collectionName: "memories",
 *   apiKey: "your-api-key",
 *   tenant: "your-tenant",
 * });
 *
 * await store.initialize();
 * ```
 */
export class Chroma implements VectorStore {
  private client: any;
  private collection: any;
  private readonly collectionName: string;
  private readonly config: ChromaConfig;
  private userId: string = "";

  constructor(config: ChromaConfig) {
    if (!ChromaClient && !CloudClient) {
      throw new Error(
        "The 'chromadb' package is required. " +
          "Please install it using 'npm install chromadb'.",
      );
    }

    this.collectionName = config.collectionName || "mem0";
    this.config = config;

    if (config.client) {
      this.client = config.client;
    } else if (config.apiKey && config.tenant) {
      // Initialize ChromaDB Cloud client
      if (!CloudClient) {
        throw new Error(
          "CloudClient not available. Please ensure 'chromadb' package is installed correctly.",
        );
      }
      this.client = new CloudClient({
        apiKey: config.apiKey,
        tenant: config.tenant,
        database: config.database || "mem0",
      });
    } else if (config.host && config.port) {
      // Initialize server client
      this.client = new ChromaClient({
        path: `http://${config.host}:${config.port}`,
      });
    } else {
      // Initialize local client
      const clientConfig: Record<string, any> = {};
      if (config.path) {
        clientConfig.path = config.path;
      }
      this.client = new ChromaClient(clientConfig);
    }
  }

  /**
   * Initialize the vector store by ensuring collection exists.
   */
  async initialize(): Promise<void> {
    this.collection = await this.client.getOrCreateCollection({
      name: this.collectionName,
    });
  }

  /**
   * Insert vectors into the collection.
   */
  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.ensureCollection();

    // ChromaDB requires metadata values to be string, number, or boolean
    const sanitizedMetadatas = payloads.map((payload) =>
      this.sanitizeMetadata(payload),
    );

    await this.collection.add({
      ids,
      embeddings: vectors,
      metadatas: sanitizedMetadatas,
    });
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
    await this.ensureCollection();

    const queryParams: Record<string, any> = {
      queryEmbeddings: [query],
      nResults: limit,
    };

    if (filters && Object.keys(filters).length > 0) {
      queryParams.where = this._generateWhereClause(filters);
    }

    const results = await this.collection.query(queryParams);
    return this._parseOutput(results);
  }

  /**
   * Get a vector by ID.
   */
  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.ensureCollection();

    try {
      const results = await this.collection.get({
        ids: [vectorId],
      });

      if (!results.ids || results.ids.length === 0) {
        return null;
      }

      const metadata = results.metadatas?.[0] || {};
      return {
        id: vectorId,
        payload: metadata,
      };
    } catch {
      return null;
    }
  }

  /**
   * Update a vector by ID.
   */
  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.ensureCollection();

    const sanitizedMetadata = this.sanitizeMetadata(payload);

    await this.collection.update({
      ids: [vectorId],
      embeddings: [vector],
      metadatas: [sanitizedMetadata],
    });
  }

  /**
   * Delete a vector by ID.
   */
  async delete(vectorId: string): Promise<void> {
    await this.ensureCollection();
    await this.collection.delete({
      ids: [vectorId],
    });
  }

  /**
   * Delete the entire collection.
   */
  async deleteCol(): Promise<void> {
    await this.client.deleteCollection({ name: this.collectionName });
    this.collection = null;
  }

  /**
   * List vectors in the collection.
   *
   * @param filters - Optional metadata filters
   * @param limit - Maximum number of results to return
   * @returns Tuple of [results, count]
   */
  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.ensureCollection();

    const getParams: Record<string, any> = {
      limit,
    };

    if (filters && Object.keys(filters).length > 0) {
      getParams.where = this._generateWhereClause(filters);
    }

    const results = await this.collection.get(getParams);

    const vectorResults: VectorStoreResult[] = [];
    const ids = results.ids || [];
    const metadatas = results.metadatas || [];

    for (let i = 0; i < ids.length; i++) {
      vectorResults.push({
        id: ids[i],
        payload: metadatas[i] || {},
      });
    }

    return [vectorResults, vectorResults.length];
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
   * Ensure collection is initialized.
   */
  private async ensureCollection(): Promise<void> {
    if (!this.collection) {
      await this.initialize();
    }
  }

  /**
   * Sanitize metadata for ChromaDB.
   * ChromaDB only accepts string, number, or boolean values.
   */
  private sanitizeMetadata(metadata: Record<string, any>): Record<string, any> {
    const sanitized: Record<string, any> = {};

    for (const [key, value] of Object.entries(metadata)) {
      if (value === null || value === undefined) {
        continue;
      }

      if (
        typeof value === "string" ||
        typeof value === "number" ||
        typeof value === "boolean"
      ) {
        sanitized[key] = value;
      } else if (Array.isArray(value)) {
        // Convert arrays to JSON string
        sanitized[key] = JSON.stringify(value);
      } else if (typeof value === "object") {
        // Convert objects to JSON string
        sanitized[key] = JSON.stringify(value);
      } else {
        // Convert other types to string
        sanitized[key] = String(value);
      }
    }

    return sanitized;
  }

  /**
   * Parse ChromaDB output to VectorStoreResult format.
   */
  private _parseOutput(data: Record<string, any>): VectorStoreResult[] {
    const ids = this.extractFirstLevel(data.ids);
    const distances = this.extractFirstLevel(data.distances);
    const metadatas = this.extractFirstLevel(data.metadatas);

    const results: VectorStoreResult[] = [];

    for (let i = 0; i < ids.length; i++) {
      const distance = distances?.[i] ?? null;
      // Convert distance to similarity score (ChromaDB returns L2 distance by default)
      // Lower distance = higher similarity, so we invert it
      const score =
        distance !== null ? this.distanceToScore(distance) : undefined;

      results.push({
        id: ids[i],
        payload: metadatas?.[i] || {},
        score,
      });
    }

    return results;
  }

  /**
   * Extract first level from nested arrays.
   * ChromaDB returns results as nested arrays for batch queries.
   */
  private extractFirstLevel(value: any): any[] {
    if (!value) return [];
    if (Array.isArray(value) && value.length > 0 && Array.isArray(value[0])) {
      return value[0];
    }
    return value;
  }

  /**
   * Convert distance to similarity score.
   * Score = 1 / (1 + distance) for monotonic transformation.
   */
  private distanceToScore(distance: number): number {
    return 1 / (1 + distance);
  }

  /**
   * Generate a properly formatted where clause for ChromaDB.
   *
   * ChromaDB supports these operators:
   * - $eq: equal to
   * - $ne: not equal to
   * - $gt: greater than
   * - $gte: greater than or equal to
   * - $lt: less than
   * - $lte: less than or equal to
   * - $in: in a list of values
   * - $nin: not in a list of values
   * - $and: logical AND
   * - $or: logical OR
   */
  private _generateWhereClause(
    where: Record<string, any>,
  ): Record<string, any> {
    if (!where || Object.keys(where).length === 0) {
      return {};
    }

    const processedFilters: Record<string, any>[] = [];

    for (const [key, value] of Object.entries(where)) {
      if (value === undefined || value === null) {
        continue;
      }

      // Handle special operators
      if (key === "$or") {
        const orConditions: Record<string, any>[] = [];
        for (const condition of value as Record<string, any>[]) {
          for (const [subKey, subValue] of Object.entries(condition)) {
            const converted = this.convertCondition(subKey, subValue);
            if (converted) {
              orConditions.push(converted);
            }
          }
        }
        if (orConditions.length > 1) {
          processedFilters.push({ $or: orConditions });
        } else if (orConditions.length === 1) {
          processedFilters.push(orConditions[0]);
        }
        continue;
      }

      if (key === "$and") {
        const andConditions: Record<string, any>[] = [];
        for (const condition of value as Record<string, any>[]) {
          for (const [subKey, subValue] of Object.entries(condition)) {
            const converted = this.convertCondition(subKey, subValue);
            if (converted) {
              andConditions.push(converted);
            }
          }
        }
        if (andConditions.length > 1) {
          processedFilters.push({ $and: andConditions });
        } else if (andConditions.length === 1) {
          processedFilters.push(andConditions[0]);
        }
        continue;
      }

      // Regular condition
      const converted = this.convertCondition(key, value);
      if (converted) {
        if (Array.isArray(converted)) {
          processedFilters.push(...converted);
        } else {
          processedFilters.push(converted);
        }
      }
    }

    if (processedFilters.length === 0) {
      return {};
    } else if (processedFilters.length === 1) {
      return processedFilters[0];
    } else {
      return { $and: processedFilters };
    }
  }

  /**
   * Convert a single filter condition to ChromaDB format.
   * Returns an array of conditions when multiple operators are used on the same field.
   */
  private convertCondition(
    key: string,
    value: any,
  ): Record<string, any> | Record<string, any>[] | null {
    // Handle wildcard - skip this filter
    if (value === "*") {
      return null;
    }

    // Handle comparison operators
    if (typeof value === "object" && value !== null && !Array.isArray(value)) {
      const conditions: Record<string, any>[] = [];

      for (const [op, val] of Object.entries(value)) {
        switch (op) {
          case "eq":
          case "$eq":
            conditions.push({ [key]: { $eq: val } });
            break;
          case "ne":
          case "$ne":
            conditions.push({ [key]: { $ne: val } });
            break;
          case "gt":
          case "$gt":
            conditions.push({ [key]: { $gt: val } });
            break;
          case "gte":
          case "$gte":
            conditions.push({ [key]: { $gte: val } });
            break;
          case "lt":
          case "$lt":
            conditions.push({ [key]: { $lt: val } });
            break;
          case "lte":
          case "$lte":
            conditions.push({ [key]: { $lte: val } });
            break;
          case "in":
          case "$in":
            conditions.push({ [key]: { $in: val } });
            break;
          case "nin":
          case "$nin":
            conditions.push({ [key]: { $nin: val } });
            break;
          default:
            conditions.push({ [key]: { $eq: val } });
        }
      }

      if (conditions.length === 0) {
        return null;
      } else if (conditions.length === 1) {
        return conditions[0];
      } else {
        return conditions;
      }
    }

    return { [key]: { $eq: value } };
  }
}
