import { MongoClient, Collection, Db } from "mongodb";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

export interface MongoDBConfig extends VectorStoreConfig {
  url?: string;
  dbName?: string;
  collectionName?: string;
  embeddingModelDims?: number;
  dimension?: number;
  client?: MongoClient;
}

export class MongoDB implements VectorStore {
  private client: MongoClient;
  private db: Db;
  private collection!: Collection;
  private readonly collectionName: string;
  private readonly dbName: string;
  private readonly embeddingModelDims: number;
  private readonly indexName: string;
  private _initPromise?: Promise<void>;

  constructor(config: MongoDBConfig) {
    this.collectionName = config.collectionName || "mem0_vectors";
    this.dbName = config.dbName || "mem0_db";
    this.embeddingModelDims =
      config.embeddingModelDims || config.dimension || 1536;
    this.indexName = `${this.collectionName}_vector_index`;

    if (config.client) {
      this.client = config.client;
    } else {
      const url = config.url || "mongodb://localhost:27017";
      this.client = new MongoClient(url, { appName: "Mem0" });
    }

    this.db = this.client.db(this.dbName);
    this.initialize().catch(console.error);
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    try {
      const collections = await this.db
        .listCollections({ name: this.collectionName })
        .toArray();
      if (collections.length === 0) {
        this.collection = this.db.collection(this.collectionName);
        await this.collection.insertOne({ _id: 0 as any, placeholder: true });
        await this.collection.deleteOne({ _id: 0 as any });
      } else {
        this.collection = this.db.collection(this.collectionName);
      }

      // Create Vector Search Index
      try {
        let foundIndex = false;
        try {
          const indexes = await this.collection.listSearchIndexes().toArray();
          foundIndex = indexes.some((idx) => idx.name === this.indexName);
        } catch (e) {
          // listSearchIndexes might not be supported/available on non-Atlas or legacy clusters
        }

        if (!foundIndex) {
          await this.collection.createSearchIndex({
            name: this.indexName,
            type: "vectorSearch",
            definition: {
              fields: [
                {
                  type: "vector",
                  path: "embedding",
                  numDimensions: this.embeddingModelDims,
                  similarity: "cosine",
                },
              ],
            },
          });
        }
      } catch (e: any) {
        console.warn(
          `Could not verify or create vector search index: ${e.message}`,
        );
      }

      // Create Text Search Index for keywordSearch
      const textIndexName = `${this.collectionName}_text_search_index`;
      try {
        let foundTextIndex = false;
        try {
          const indexes = await this.collection.listSearchIndexes().toArray();
          foundTextIndex = indexes.some((idx) => idx.name === textIndexName);
        } catch (e) {
          // ignore
        }

        if (!foundTextIndex) {
          await this.collection.createSearchIndex({
            name: textIndexName,
            definition: {
              mappings: {
                dynamic: false,
                fields: {
                  payload: {
                    type: "document",
                    fields: {
                      data: { type: "string" },
                      text_lemmatized: { type: "string" },
                    },
                  },
                },
              },
            },
          });
        }
      } catch (e: any) {
        console.warn(
          `Could not create text search index '${textIndexName}': ${e.message}. ` +
            `Atlas Search may not be available. keywordSearch() will not work.`,
        );
      }
    } catch (error) {
      console.error("Error initializing MongoDB:", error);
      throw error;
    }
  }

  private validateFilterValue(key: string, value: any): void {
    if (typeof value === "object" && value !== null) {
      if (Array.isArray(value)) {
        for (const item of value) {
          if (
            typeof item === "object" &&
            item !== null &&
            !Array.isArray(item)
          ) {
            throw new Error(
              `Filter list for '${key}' contains an object, which may contain MongoDB query operators.`,
            );
          }
        }
      } else {
        throw new Error(
          `Filter value for '${key}' must be a scalar (string, number, boolean), not an object. Objects may contain MongoDB query operators.`,
        );
      }
    }
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();

    const documents = vectors.map((vector, idx) => ({
      _id: ids[idx] as any,
      embedding: vector,
      payload: payloads[idx] || {},
    }));

    try {
      await this.collection.insertMany(documents);
    } catch (error) {
      console.error("Error inserting data:", error);
      throw error;
    }
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();

    if (filters) {
      for (const [key, value] of Object.entries(filters)) {
        this.validateFilterValue(key, value);
      }
    }

    try {
      let foundIndex = false;
      try {
        const indexes = await this.collection.listSearchIndexes().toArray();
        foundIndex = indexes.some((idx) => idx.name === this.indexName);
      } catch (e) {
        // listSearchIndexes might not be supported/available on non-Atlas or legacy clusters
        foundIndex = true;
      }

      if (!foundIndex) {
        console.error(`Index '${this.indexName}' does not exist.`);
        return [];
      }

      const pipeline: any[] = [
        {
          $vectorSearch: {
            index: this.indexName,
            limit: topK,
            numCandidates: Math.min(topK * 20, 10000),
            queryVector: query,
            path: "embedding",
          },
        },
        { $set: { score: { $meta: "vectorSearchScore" } } },
        { $project: { embedding: 0 } },
      ];

      if (filters && Object.keys(filters).length > 0) {
        const filterConditions: any[] = [];
        for (const [key, value] of Object.entries(filters)) {
          filterConditions.push({ [`payload.${key}`]: value });
        }
        if (filterConditions.length > 0) {
          pipeline.splice(1, 0, { $match: { $and: filterConditions } });
        }
      }

      const results = await this.collection.aggregate(pipeline).toArray();

      return results.map((doc) => ({
        id: String(doc._id),
        score: doc.score,
        payload: doc.payload || {},
      }));
    } catch (error) {
      console.error("Error during vector search:", error);
      return [];
    }
  }

  async keywordSearch(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    await this.initialize();

    if (filters) {
      for (const [key, value] of Object.entries(filters)) {
        this.validateFilterValue(key, value);
      }
    }

    try {
      const textIndexName = `${this.collectionName}_text_search_index`;
      const pipeline: any[] = [
        {
          $search: {
            index: textIndexName,
            text: {
              query: query,
              path: ["payload.data", "payload.text_lemmatized"],
            },
          },
        },
        { $set: { score: { $meta: "searchScore" } } },
        { $project: { embedding: 0 } },
      ];

      if (filters && Object.keys(filters).length > 0) {
        const filterConditions: any[] = [];
        for (const [key, value] of Object.entries(filters)) {
          filterConditions.push({ [`payload.${key}`]: value });
        }
        if (filterConditions.length > 0) {
          pipeline.splice(1, 0, { $match: { $and: filterConditions } });
        }
      }

      pipeline.push({ $limit: topK });

      const results = await this.collection.aggregate(pipeline).toArray();

      return results.map((doc) => ({
        id: String(doc._id),
        score: doc.score,
        payload: doc.payload || {},
      }));
    } catch (error) {
      console.error("Error during keyword search:", error);
      return null;
    }
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();
    try {
      const doc = await this.collection.findOne({ _id: vectorId as any });
      if (doc) {
        return {
          id: String(doc._id),
          payload: doc.payload || {},
        };
      }
      return null;
    } catch (error) {
      console.error("Error retrieving document:", error);
      return null;
    }
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();
    const updateFields: any = {};
    if (vector) {
      updateFields.embedding = vector;
    }
    if (payload) {
      for (const [key, value] of Object.entries(payload)) {
        updateFields[`payload.${key}`] = value;
      }
    }

    if (Object.keys(updateFields).length > 0) {
      try {
        const result = await this.collection.updateOne(
          { _id: vectorId as any },
          { $set: updateFields },
        );
        if (result.matchedCount === 0) {
          console.warn(`No document found with ID '${vectorId}' to update.`);
        }
      } catch (error) {
        console.error("Error updating document:", error);
        throw error;
      }
    }
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();
    try {
      const result = await this.collection.deleteOne({ _id: vectorId as any });
      if (result.deletedCount === 0) {
        console.warn(`No document found with ID '${vectorId}' to delete.`);
      }
    } catch (error) {
      console.error("Error deleting document:", error);
      throw error;
    }
  }

  async deleteCol(): Promise<void> {
    await this.initialize();
    try {
      await this.collection.drop();
    } catch (error) {
      console.error("Error deleting collection:", error);
      throw error;
    }
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();

    if (filters) {
      for (const [key, value] of Object.entries(filters)) {
        this.validateFilterValue(key, value);
      }
    }

    try {
      let query: any = {};
      if (filters && Object.keys(filters).length > 0) {
        const filterConditions: any[] = [];
        for (const [key, value] of Object.entries(filters)) {
          filterConditions.push({ [`payload.${key}`]: value });
        }
        if (filterConditions.length > 0) {
          query = { $and: filterConditions };
        }
      }

      const results = await this.collection.find(query).limit(topK).toArray();

      const output = results.map((doc) => ({
        id: String(doc._id),
        payload: doc.payload || {},
      }));

      return [output, results.length];
    } catch (error) {
      console.error("Error listing documents:", error);
      return [[], 0];
    }
  }

  async getUserId(): Promise<string> {
    await this.initialize();
    try {
      const migrationsCol = this.db.collection("memory_migrations");
      const doc = await migrationsCol.findOne({});
      if (doc && doc.user_id) {
        return doc.user_id;
      }

      const randomUserId =
        Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15);

      await migrationsCol.updateOne(
        {},
        { $set: { user_id: randomUserId } },
        { upsert: true },
      );
      return randomUserId;
    } catch (error) {
      console.error("Error getting user ID:", error);
      throw error;
    }
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();
    try {
      const migrationsCol = this.db.collection("memory_migrations");
      await migrationsCol.updateOne(
        {},
        { $set: { user_id: userId } },
        { upsert: true },
      );
    } catch (error) {
      console.error("Error setting user ID:", error);
      throw error;
    }
  }

  async close(): Promise<void> {
    if (this.client) {
      await this.client.close();
    }
  }
}
