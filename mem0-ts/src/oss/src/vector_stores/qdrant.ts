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
  private _initPromise?: Promise<void>;

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
    scoreThreshold?: number,
  ): Promise<VectorStoreResult[]> {
    const queryFilter = this.createFilter(filters);
    const searchParams: Record<string, any> = {
      vector: query,
      filter: queryFilter,
      limit,
    };
    if (scoreThreshold != null) {
      searchParams.score_threshold = scoreThreshold;
    }
    const results = await this.client.search(this.collectionName, searchParams);

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
      // Ensure collection exists (idempotent — handles race conditions)
      await this.ensureCollection("memory_migrations", 1);

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

  private async ensureCollection(name: string, size: number): Promise<void> {
    try {
      await this.client.createCollection(name, {
        vectors: {
          size,
          distance: "Cosine",
        },
      });
    } catch (error: any) {
      if (
        error?.status === 409 ||
        error?.status === 401 ||
        error?.status === 403
      ) {
        // Collection already exists — verify configuration for the main collection
        if (name === this.collectionName) {
          try {
            const collectionInfo = await this.client.getCollection(name);
            const vectorConfig = collectionInfo.config?.params?.vectors;

            if (vectorConfig && vectorConfig.size !== size) {
              throw new Error(
                `Collection ${name} exists but has wrong vector size. ` +
                  `Expected: ${size}, got: ${vectorConfig.size}`,
              );
            }
          } catch (verifyError: any) {
            // Re-throw dimension mismatch errors
            if (verifyError?.message?.includes("wrong vector size")) {
              throw verifyError;
            }
            // Transient errors (e.g. 500 while collection is being committed)
            // are non-fatal — the collection exists per the 409.
            console.warn(
              `Collection '${name}' exists (409) but dimension verification failed: ${verifyError?.message || verifyError}. Proceeding anyway.`,
            );
          }
        }
        // Otherwise collection exists and is fine — proceed
      } else {
        throw error;
      }
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
      await this.ensureCollection("memory_migrations", 1);
    } catch (error) {
      console.error("Error initializing Qdrant:", error);
      throw error;
    }
  }
}
