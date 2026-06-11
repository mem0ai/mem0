import { QdrantClient } from "@qdrant/js-client-rest";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
import * as fs from "fs";

interface QdrantConfig extends VectorStoreConfig {
  /**
   * Pre-configured QdrantClient instance. If using Qdrant Cloud, you must pass
   * `port` explicitly when constructing the client to avoid "Illegal host" errors
   * caused by a known upstream bug (qdrant/qdrant-js#59).
   *
   * @example
   * ```typescript
   * const client = new QdrantClient({
   *   url: "https://xxx.cloud.qdrant.io:6333",
   *   port: 6333,
   *   apiKey: "xxx",
   * });
   * ```
   */
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
  must?: (QdrantCondition | QdrantFilter)[];
  must_not?: (QdrantCondition | QdrantFilter)[];
  should?: (QdrantCondition | QdrantFilter)[];
}

interface QdrantCondition {
  key: string;
  match?: { value?: any; any?: any[]; except?: any[]; text?: string };
  range?: {
    gte?: number | string;
    gt?: number | string;
    lte?: number | string;
    lt?: number | string;
  };
}

// Normalize $and/$or/$not to AND/OR/NOT
const KEY_MAP: Record<string, string> = {
  $and: "AND",
  $or: "OR",
  $not: "NOT",
};

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
        // Workaround for qdrant/qdrant-js#59: explicitly pass port to avoid "Illegal host" error
        try {
          const parsedUrl = new URL(config.url);
          params.port = parsedUrl.port ? parseInt(parsedUrl.port, 10) : 6333;
        } catch (_) {
          params.port = 6333;
        }
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

  /**
   * Build a single field condition from a key-value filter pair.
   * Supports enhanced filter syntax with comparison operators.
   */
  private buildFieldCondition(key: string, value: any): QdrantCondition | null {
    // Handle non-dict values
    if (typeof value !== "object" || value === null) {
      // Wildcard: match any value - skip this filter
      if (value === "*") {
        return null;
      }
      // Simple equality
      return { key, match: { value } };
    }

    // Handle array shorthand: {"field": ["a", "b"]} treated as "in" operator
    if (Array.isArray(value)) {
      return { key, match: { any: value } };
    }

    const ops = Object.keys(value);
    const rangeOps = ["gt", "gte", "lt", "lte"];
    const hasRangeOps = ops.some((op) => rangeOps.includes(op));
    const nonRangeOps = ops.filter((op) => !rangeOps.includes(op));

    // Handle range operators
    if (hasRangeOps) {
      if (nonRangeOps.length > 0) {
        throw new Error(
          `Cannot mix range operators (${ops.filter((o) => rangeOps.includes(o)).join(", ")}) ` +
            `with non-range operators (${nonRangeOps.join(", ")}) for field '${key}'. ` +
            `Use AND to combine them as separate conditions.`,
        );
      }
      const range: Record<string, number | string> = {};
      for (const op of rangeOps) {
        if (op in value) {
          range[op] = value[op];
        }
      }
      return { key, range };
    }

    // Handle comparison operators
    if ("eq" in value) {
      return { key, match: { value: value.eq } };
    }
    if ("ne" in value) {
      return { key, match: { except: [value.ne] } };
    }
    if ("in" in value) {
      return { key, match: { any: value.in } };
    }
    if ("nin" in value) {
      return { key, match: { except: value.nin } };
    }
    if ("contains" in value || "icontains" in value) {
      const text = value.contains || value.icontains;
      return { key, match: { text } };
    }

    // Unknown operator - treat as nested object for simple match
    const supportedOps = [
      "eq",
      "ne",
      "gt",
      "gte",
      "lt",
      "lte",
      "in",
      "nin",
      "contains",
      "icontains",
    ];
    throw new Error(
      `Unsupported filter operator(s) for field '${key}': ${ops.join(", ")}. ` +
        `Supported operators: ${supportedOps.join(", ")}`,
    );
  }

  /**
   * Create a Filter object from the provided filters.
   * Supports logical operators (AND, OR, NOT) and comparison operators.
   */
  private createFilter(filters?: SearchFilters): QdrantFilter | undefined {
    if (!filters || Object.keys(filters).length === 0) return undefined;

    // Normalize $or/$not/$and → OR/NOT/AND and deduplicate
    const normalized: Record<string, any> = {};
    for (const [key, value] of Object.entries(filters)) {
      const normKey = KEY_MAP[key] || key;
      if (!(normKey in normalized)) {
        normalized[normKey] = value;
      }
    }

    const must: (QdrantCondition | QdrantFilter)[] = [];
    const should: (QdrantCondition | QdrantFilter)[] = [];
    const mustNot: (QdrantCondition | QdrantFilter)[] = [];

    for (const [key, value] of Object.entries(normalized)) {
      // Handle logical operators
      if (key === "AND" || key === "OR" || key === "NOT") {
        if (!Array.isArray(value)) {
          throw new Error(
            `${key} filter value must be a list of filter dicts, got ${typeof value}`,
          );
        }
        for (let i = 0; i < value.length; i++) {
          const item = value[i];
          if (
            typeof item !== "object" ||
            item === null ||
            Array.isArray(item)
          ) {
            throw new Error(
              `${key} filter list item at index ${i} must be a dict, got ${typeof item}`,
            );
          }
        }

        if (key === "AND") {
          for (const sub of value) {
            const built = this.createFilter(sub);
            if (built) {
              must.push(built);
            }
          }
        } else if (key === "OR") {
          for (const sub of value) {
            const built = this.createFilter(sub);
            if (built) {
              should.push(built);
            }
          }
        } else if (key === "NOT") {
          for (const sub of value) {
            const built = this.createFilter(sub);
            if (built) {
              mustNot.push(built);
            }
          }
        }
      } else {
        // Regular field condition
        const condition = this.buildFieldCondition(key, value);
        if (condition !== null) {
          must.push(condition);
        }
      }
    }

    if (must.length === 0 && should.length === 0 && mustNot.length === 0) {
      return undefined;
    }

    return {
      must: must.length > 0 ? must : undefined,
      should: should.length > 0 ? should : undefined,
      must_not: mustNot.length > 0 ? mustNot : undefined,
    };
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

  async keywordSearch(): Promise<null> {
    return null;
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const queryFilter = this.createFilter(filters);
    const results = await this.client.search(this.collectionName, {
      vector: query,
      filter: queryFilter,
      limit: topK,
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
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const scrollRequest = {
      limit: topK,
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
