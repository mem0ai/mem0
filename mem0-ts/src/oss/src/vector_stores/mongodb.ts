import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

/**
 * Type-only imports for better IDE support and type safety.
 * These are peer dependencies - users must install mongodb.
 */
import type {
  MongoClient as MongoClientType,
  Db,
  Collection,
  Document,
} from "mongodb";

/**
 * Try to import MongoDB client.
 * This is a peer dependency - users must install mongodb.
 */
let MongoClient: typeof MongoClientType | undefined;

try {
  const mongodb = require("mongodb");
  MongoClient = mongodb.MongoClient;
} catch {
  // Will throw at runtime if MongoDB is used without the package installed
}

/**
 * Configuration options for MongoDB Atlas vector store.
 */
export interface MongoDBConfig extends VectorStoreConfig {
  /** MongoDB connection URI */
  mongoUri: string;
  /** Database name */
  dbName: string;
  /** Collection name for storing vectors */
  collectionName: string;
  /** Dimension of the embedding vectors */
  embeddingModelDims: number;
  /** Name of the vector search index. Defaults to "{collectionName}_vector_index" */
  indexName?: string;
  /** Similarity metric for vector search. Defaults to "cosine" */
  similarityMetric?: "cosine" | "euclidean" | "dotProduct";
  /** Multiplier for candidate pool size during search. Defaults to 10 (MongoDB recommends 10-20x limit) */
  numCandidatesMultiplier?: number;
}

/**
 * MongoDB Atlas vector store implementation.
 *
 * Uses MongoDB Atlas Vector Search for similarity queries.
 * Requires `mongodb` as a peer dependency.
 *
 * @example
 * ```typescript
 * const store = new MongoDB({
 *   mongoUri: "mongodb+srv://...",
 *   dbName: "memories",
 *   collectionName: "vectors",
 *   embeddingModelDims: 1536,
 * });
 * await store.initialize();
 * ```
 */
export class MongoDB implements VectorStore {
  private client: MongoClientType | null = null;
  private db: Db | null = null;
  private collection: Collection<Document> | null = null;
  private mongoUri: string;
  private dbName: string;
  private collectionName: string;
  private embeddingModelDims: number;
  private indexName: string;
  private similarityMetric: "cosine" | "euclidean" | "dotProduct";
  private numCandidatesMultiplier: number;
  private userId: string = "";

  constructor(config: MongoDBConfig) {
    if (!MongoClient) {
      throw new Error(
        "The 'mongodb' package is required. " +
          "Please install it using 'npm install mongodb'.",
      );
    }

    if (!config.mongoUri) {
      throw new Error("mongoUri is required for MongoDB");
    }

    if (!config.dbName) {
      throw new Error("dbName is required for MongoDB");
    }

    if (!config.collectionName) {
      throw new Error("collectionName is required for MongoDB");
    }

    if (!config.embeddingModelDims) {
      throw new Error("embeddingModelDims is required for MongoDB");
    }

    this.mongoUri = config.mongoUri;
    this.dbName = config.dbName;
    this.collectionName = config.collectionName;
    this.embeddingModelDims = config.embeddingModelDims;
    this.indexName =
      config.indexName || `${config.collectionName}_vector_index`;
    this.similarityMetric = config.similarityMetric || "cosine";
    this.numCandidatesMultiplier = config.numCandidatesMultiplier || 10;

    this.client = new MongoClient(this.mongoUri);
  }

  /**
   * Initialize the vector store by connecting and ensuring collection/index exist.
   */
  async initialize(): Promise<void> {
    if (!this.client) {
      throw new Error("MongoDB client not initialized");
    }
    await this.client.connect();
    this.db = this.client.db(this.dbName);
    this.collection = this.db.collection(this.collectionName);
    await this.ensureCollectionExists();
    await this.ensureIndexExists();
  }

  /**
   * Ensure the collection exists, creating it if necessary.
   */
  private async ensureCollectionExists(): Promise<void> {
    if (!this.db) {
      throw new Error("Database not initialized");
    }

    const collections = await this.db
      .listCollections({ name: this.collectionName })
      .toArray();
    if (collections.length === 0) {
      console.log(
        `Collection '${this.collectionName}' not found. Creating it.`,
      );
      await this.db.createCollection(this.collectionName);
      console.log(`Collection '${this.collectionName}' created.`);
    }
  }

  /**
   * Ensure the vector search index exists, creating it if necessary.
   */
  private async ensureIndexExists(): Promise<void> {
    if (!this.collection) {
      throw new Error("Collection not initialized");
    }

    try {
      const indexes = await this.collection
        .listSearchIndexes(this.indexName)
        .toArray();
      if (indexes.length > 0) {
        console.log(`Search index '${this.indexName}' already exists.`);
        return;
      }
    } catch (error: any) {
      if (error.message?.includes("no search indexes")) {
        // Expected when no indexes exist yet - continue to create
      } else {
        console.warn(
          `Warning: Could not list search indexes: ${error.message}. Attempting to create index.`,
        );
      }
    }

    try {
      // Create vector search index
      const indexDefinition = {
        name: this.indexName,
        definition: {
          mappings: {
            dynamic: true,
            fields: {
              embedding: {
                type: "knnVector",
                dimensions: this.embeddingModelDims,
                similarity: this.similarityMetric,
              },
            },
          },
        },
      };

      await this.collection.createSearchIndex(indexDefinition);
      console.log(`Search index '${this.indexName}' created.`);
    } catch (error: any) {
      // Index might already exist or creation might be in progress
      if (error.codeName === "IndexAlreadyExists" || error.code === 68) {
        console.log(`Search index '${this.indexName}' already exists.`);
      } else {
        throw error;
      }
    }
  }

  /**
   * Insert vectors into the collection.
   */
  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    if (!this.collection) {
      throw new Error("Collection not initialized");
    }

    const documents = vectors.map((vector, i) => ({
      _id: ids[i],
      embedding: vector,
      payload: payloads[i] || {},
    }));

    await this.collection.insertMany(documents);
  }

  /**
   * Search for similar vectors using $vectorSearch aggregation.
   *
   * @param query - Query vector
   * @param limit - Maximum number of results to return
   * @param filters - Optional metadata filters (applied as pre-filters in $vectorSearch)
   * @returns Array of results sorted by similarity score (descending)
   */
  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    if (!this.collection) {
      throw new Error("Collection not initialized");
    }

    const vectorSearchStage: any = {
      index: this.indexName,
      path: "embedding",
      queryVector: query,
      numCandidates: limit * this.numCandidatesMultiplier,
      limit: limit,
    };

    if (filters && Object.keys(filters).length > 0) {
      const filterQuery = this.buildFilterQuery(filters);
      if (Object.keys(filterQuery).length > 0) {
        vectorSearchStage.filter = filterQuery;
      }
    }

    const pipeline: any[] = [
      { $vectorSearch: vectorSearchStage },
      {
        $set: {
          score: { $meta: "vectorSearchScore" },
        },
      },
      {
        $project: {
          embedding: 0,
        },
      },
    ];

    const results = await this.collection.aggregate(pipeline).toArray();

    return results.map((doc: any) => ({
      id: String(doc._id),
      payload: doc.payload || {},
      score: doc.score,
    }));
  }

  /**
   * Get a vector by ID.
   */
  async get(vectorId: string): Promise<VectorStoreResult | null> {
    if (!this.collection) {
      throw new Error("Collection not initialized");
    }

    const doc = await this.collection.findOne({ _id: vectorId });

    if (!doc) {
      return null;
    }

    return {
      id: String(doc._id),
      payload: doc.payload || {},
    };
  }

  /**
   * Update a vector by ID.
   */
  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    if (!this.collection) {
      throw new Error("Collection not initialized");
    }

    const updateFields: Record<string, any> = {};

    if (vector) {
      updateFields.embedding = vector;
    }
    if (payload) {
      updateFields.payload = payload;
    }

    if (Object.keys(updateFields).length > 0) {
      await this.collection.updateOne(
        { _id: vectorId },
        { $set: updateFields },
      );
    }
  }

  /**
   * Delete a vector by ID.
   */
  async delete(vectorId: string): Promise<void> {
    if (!this.collection) {
      throw new Error("Collection not initialized");
    }
    await this.collection.deleteOne({ _id: vectorId });
  }

  /**
   * Delete the entire collection.
   */
  async deleteCol(): Promise<void> {
    if (!this.collection) {
      throw new Error("Collection not initialized");
    }
    await this.collection.drop();
  }

  /**
   * List vectors in the collection.
   *
   * @param filters - Optional metadata filters
   * @param limit - Maximum number of results to return
   * @returns Tuple of [results, count of returned results]
   * @note The count returned is the number of results in the response, not the total matching documents
   */
  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    if (!this.collection) {
      throw new Error("Collection not initialized");
    }

    let query: Record<string, any> = {};

    if (filters && Object.keys(filters).length > 0) {
      const filterConditions = this.buildFilterConditions(filters);
      if (filterConditions.length > 0) {
        query = { $and: filterConditions };
      }
    }

    const cursor = this.collection.find(query).limit(limit);
    const results: VectorStoreResult[] = [];

    for await (const doc of cursor) {
      results.push({
        id: String(doc._id),
        payload: doc.payload || {},
      });
    }

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
   * Build filter query for MongoDB $vectorSearch pre-filtering.
   * Filters are applied to the payload field.
   */
  private buildFilterQuery(filters: SearchFilters): Record<string, any> {
    const conditions: Record<string, any>[] = [];

    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null) {
        conditions.push({ [`payload.${key}`]: { $eq: value } });
      }
    }

    return conditions.length > 0 ? { $and: conditions } : {};
  }

  /**
   * Build filter conditions for MongoDB queries (used in list method).
   * Filters are applied to the payload field.
   */
  private buildFilterConditions(filters: SearchFilters): Record<string, any>[] {
    const conditions: Record<string, any>[] = [];

    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null) {
        conditions.push({ [`payload.${key}`]: value });
      }
    }

    return conditions;
  }

  /**
   * Close the MongoDB client connection.
   */
  async destroy(): Promise<void> {
    if (this.client) {
      await this.client.close();
    }
  }
}
