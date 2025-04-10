import { QdrantClient } from "@qdrant/js-client-rest";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
import * as fs from "fs";

interface QdrantConfig extends VectorStoreConfig {
  client?: QdrantClient;
  host?: string;
  port?: number;
  path?: string;
  url?: string;
  apiKey?: string;
  onDisk?: boolean;
  collectionName: string;
  embeddingModelDims: number;
  dimension?: number;
}

interface QdrantFilter {
  must?: QdrantCondition[];
  must_not?: QdrantCondition[];
  should?: QdrantCondition[];
}

interface QdrantCondition {
  key: string;
  match?: { value: any };
  range?: { gte?: number; gt?: number; lte?: number; lt?: number };
}

export class Qdrant implements VectorStore {
  private client: QdrantClient;
  private readonly collectionName: string;
  private dimension: number;

  constructor(config: QdrantConfig) {
    if (config.client) {
      this.client = config.client;
    } else {
      const params: Record<string, any> = {};
      if (config.apiKey) {
        params.apiKey = config.apiKey;
      }
      if (config.url) {
        params.url = config.url;
      }
      if (config.host && config.port) {
        params.host = config.host;
        params.port = config.port;
      }
      if (!Object.keys(params).length) {
        params.path = config.path;
        if (!config.onDisk && config.path) {
          if (
            fs.existsSync(config.path) &&
            fs.statSync(config.path).isDirectory()
          ) {
            fs.rmSync(config.path, { recursive: true });
          }
        }
      }

      this.client = new QdrantClient(params);
    }

    this.collectionName = config.collectionName;
    this.dimension = config.dimension || 1536; // Default OpenAI dimension
    this.initialize().catch(console.error);
  }

  private createFilter(filters?: SearchFilters): QdrantFilter | undefined {
    if (!filters) return undefined;

    const conditions: QdrantCondition[] = [];
    for (const [key, value] of Object.entries(filters)) {
      if (
        typeof value === "object" &&
        value !== null &&
        "gte" in value &&
        "lte" in value
      ) {
        conditions.push({
          key,
          range: {
            gte: value.gte,
            lte: value.lte,
          },
        });
      } else {
        conditions.push({
          key,
          match: {
            value,
          },
        });
      }
    }

    return conditions.length ? { must: conditions } : undefined;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const points = vectors.map((vector, idx) => ({
      id: ids[idx],
      vector: vector,
      payload: payloads[idx] || {},
    }));

    await this.client.upsert(this.collectionName, {
      points,
    });
  }

  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const queryFilter = this.createFilter(filters);
    const results = await this.client.search(this.collectionName, {
      vector: query,
      filter: queryFilter,
      limit,
    });

    return results.map((hit) => ({
      id: String(hit.id),
      payload: (hit.payload as Record<string, any>) || {},
      score: hit.score,
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const results = await this.client.retrieve(this.collectionName, {
      ids: [vectorId],
      with_payload: true,
    });

    if (!results.length) return null;

    return {
      id: vectorId,
      payload: results[0].payload || {},
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const point = {
      id: vectorId,
      vector: vector,
      payload,
    };

    await this.client.upsert(this.collectionName, {
      points: [point],
    });
  }

  async delete(vectorId: string): Promise<void> {
    await this.client.delete(this.collectionName, {
      points: [vectorId],
    });
  }

  async deleteCol(): Promise<void> {
    await this.client.deleteCollection(this.collectionName);
  }

  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const scrollRequest = {
      limit,
      filter: this.createFilter(filters),
      with_payload: true,
      with_vectors: false,
    };

    const response = await this.client.scroll(
      this.collectionName,
      scrollRequest,
    );

    const results = response.points.map((point) => ({
      id: String(point.id),
      payload: (point.payload as Record<string, any>) || {},
    }));

    return [results, response.points.length];
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
      // First check if the collection exists
      const collections = await this.client.getCollections();
      const userCollectionExists = collections.collections.some(
        (col: { name: string }) => col.name === "memory_migrations",
      );

      if (!userCollectionExists) {
        // Create the collection if it doesn't exist
        await this.client.createCollection("memory_migrations", {
          vectors: {
            size: 1,
            distance: "Cosine",
            on_disk: false,
          },
        });
      }

      // Now try to get the user ID
      const result = await this.client.scroll("memory_migrations", {
        limit: 1,
        with_payload: true,
      });

      if (result.points.length > 0) {
        return result.points[0].payload?.user_id as string;
      }

      // Generate a random user_id if none exists
      const randomUserId =
        Math.random().toString(36).substring(2, 15) +
        Math.random().toString(36).substring(2, 15);

      await this.client.upsert("memory_migrations", {
        points: [
          {
            id: this.generateUUID(),
            vector: [0],
            payload: { user_id: randomUserId },
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
      // Get existing point ID
      const result = await this.client.scroll("memory_migrations", {
        limit: 1,
        with_payload: true,
      });

      const pointId =
        result.points.length > 0 ? result.points[0].id : this.generateUUID();

      await this.client.upsert("memory_migrations", {
        points: [
          {
            id: pointId,
            vector: [0],
            payload: { user_id: userId },
          },
        ],
      });
    } catch (error) {
      console.error("Error setting user ID:", error);
      throw error;
    }
  }

  async initialize(): Promise<void> {
    try {
      // Create collection if it doesn't exist
      const collections = await this.client.getCollections();
      const exists = collections.collections.some(
        (c) => c.name === this.collectionName,
      );

      if (!exists) {
        try {
          await this.client.createCollection(this.collectionName, {
            vectors: {
              size: this.dimension,
              distance: "Cosine",
            },
          });
        } catch (error: any) {
          // Handle case where collection was created between our check and create
          if (error?.status === 409) {
            // Collection already exists - verify it has the correct configuration
            const collectionInfo = await this.client.getCollection(
              this.collectionName,
            );
            const vectorConfig = collectionInfo.config?.params?.vectors;

            if (!vectorConfig || vectorConfig.size !== this.dimension) {
              throw new Error(
                `Collection ${this.collectionName} exists but has wrong configuration. ` +
                  `Expected vector size: ${this.dimension}, got: ${vectorConfig?.size}`,
              );
            }
            // Collection exists with correct configuration - we can proceed
          } else {
            throw error;
          }
        }
      }

      // Create memory_migrations collection if it doesn't exist
      const userExists = collections.collections.some(
        (c) => c.name === "memory_migrations",
      );

      if (!userExists) {
        try {
          await this.client.createCollection("memory_migrations", {
            vectors: {
              size: 1, // Minimal size since we only store user_id
              distance: "Cosine",
            },
          });
        } catch (error: any) {
          // Handle case where collection was created between our check and create
          if (error?.status === 409) {
            // Collection already exists - we can proceed
          } else {
            throw error;
          }
        }
      }
    } catch (error) {
      console.error("Error initializing Qdrant:", error);
      throw error;
    }
  }
}
