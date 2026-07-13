import type { ChromaClient, CloudClient } from "chromadb";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface ChromaConfig extends VectorStoreConfig {
  /** Pre-configured ChromaDB client instance. */
  client?: ChromaClient | CloudClient;
  collectionName: string;
  /** Host address for a ChromaDB server (defaults to the client default). */
  host?: string;
  /** Port for a ChromaDB server. */
  port?: number;
  /** Whether to use SSL when connecting to a ChromaDB server. */
  ssl?: boolean;
  /** Path for a local ChromaDB server. */
  path?: string;
  /** ChromaDB Cloud API key. */
  apiKey?: string;
  /** ChromaDB Cloud tenant ID. */
  tenant?: string;
  /** ChromaDB Cloud database name. */
  database?: string;
}

const MIGRATIONS_COLLECTION = "memory_migrations";

/**
 * ChromaDB vector store provider.
 *
 * Mirrors the Python SDK's `mem0.vector_stores.chroma.ChromaDB` behavior using
 * the `chromadb` v3 JavaScript client. Embeddings are always supplied by mem0,
 * so no embedding function is required on the collection.
 */
export class ChromaDB implements VectorStore {
  private clientInstance?: any;
  private clientPromise?: Promise<any>;
  private readonly config: ChromaConfig;
  private readonly collectionName: string;
  private collectionPromise?: Promise<any>;
  private migrationsPromise?: Promise<any>;

  constructor(config: ChromaConfig) {
    this.config = config;
    this.collectionName = config.collectionName;
    this.initialize().catch(console.error);
  }

  /**
   * Lazily construct (or reuse) the ChromaDB client, importing the optional
   * `chromadb` peer only when the store is first used so consumers that never
   * touch Chroma don't need it installed.
   */
  private async getClient(): Promise<any> {
    if (this.clientInstance) return this.clientInstance;
    if (!this.clientPromise) {
      this.clientPromise = this.createClient();
    }
    this.clientInstance = await this.clientPromise;
    return this.clientInstance;
  }

  private async createClient(): Promise<any> {
    const config = this.config;
    if (config.client) {
      return config.client;
    }

    let sdk: any;
    try {
      sdk = await import("chromadb");
    } catch {
      throw new Error(
        "The 'chromadb' package is required to use the Chroma vector store. Install it with: npm install chromadb",
      );
    }

    if (config.apiKey && config.tenant) {
      return new sdk.CloudClient({
        apiKey: config.apiKey,
        tenant: config.tenant,
        database: config.database || "mem0",
      } as any);
    }

    const params: Record<string, any> = {};
    if (config.host) params.host = config.host;
    if (config.port) params.port = config.port;
    if (config.ssl !== undefined) params.ssl = config.ssl;
    if (config.path) params.path = config.path;
    return new sdk.ChromaClient(params as any);
  }

  private async getCollection(): Promise<any> {
    if (!this.collectionPromise) {
      const client = await this.getClient();
      this.collectionPromise = client.getOrCreateCollection({
        name: this.collectionName,
        embeddingFunction: null,
      });
    }
    return this.collectionPromise;
  }

  private async getMigrationsCollection(): Promise<any> {
    if (!this.migrationsPromise) {
      const client = await this.getClient();
      this.migrationsPromise = client.getOrCreateCollection({
        name: MIGRATIONS_COLLECTION,
        embeddingFunction: null,
      });
    }
    return this.migrationsPromise;
  }

  private flatten(value: any): any[] {
    if (Array.isArray(value) && value.length > 0 && Array.isArray(value[0])) {
      return value[0];
    }
    return Array.isArray(value) ? value : [];
  }

  /** Parse a ChromaDB `get`/`query` response into VectorStoreResult objects. */
  private parseOutput(data: any): VectorStoreResult[] {
    const ids = this.flatten(data?.ids);
    const distances = this.flatten(data?.distances);
    const metadatas = this.flatten(data?.metadatas);

    const length = Math.max(ids.length, metadatas.length);
    const results: VectorStoreResult[] = [];

    for (let i = 0; i < length; i++) {
      const rawDistance = distances[i];
      const score =
        rawDistance !== undefined && rawDistance !== null
          ? 1.0 / (1.0 + rawDistance)
          : undefined;

      results.push({
        id: String(ids[i]),
        payload: (metadatas[i] as Record<string, any>) || {},
        score,
      });
    }

    return results;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const collection = await this.getCollection();
    await collection.add({
      ids,
      embeddings: vectors,
      metadatas: payloads as any,
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
    const collection = await this.getCollection();
    const where = ChromaDB.generateWhereClause(filters);
    const results = await collection.query({
      queryEmbeddings: [query],
      nResults: topK,
      where: where as any,
    });
    return this.parseOutput(results);
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const collection = await this.getCollection();
    const results = await collection.get({ ids: [vectorId] });
    const parsed = this.parseOutput(results);
    return parsed.length > 0 ? parsed[0] : null;
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const collection = await this.getCollection();
    await collection.update({
      ids: [vectorId],
      embeddings: vector ? [vector] : undefined,
      metadatas: payload ? [payload] : undefined,
    } as any);
  }

  async delete(vectorId: string): Promise<void> {
    const collection = await this.getCollection();
    await collection.delete({ ids: [vectorId] });
  }

  async deleteCol(): Promise<void> {
    const client = await this.getClient();
    await client.deleteCollection({ name: this.collectionName });
    this.collectionPromise = undefined;
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const collection = await this.getCollection();
    const where = ChromaDB.generateWhereClause(filters);
    const results = await collection.get({ where: where as any, limit: topK });
    const parsed = this.parseOutput(results);
    return [parsed, parsed.length];
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
    const collection = await this.getMigrationsCollection();
    const result = await collection.get({ limit: 1 });
    const ids = Array.isArray(result?.ids) ? result.ids : [];
    const metadatas = Array.isArray(result?.metadatas) ? result.metadatas : [];

    if (ids.length > 0 && metadatas[0]?.user_id) {
      return String(metadatas[0].user_id);
    }

    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);

    await collection.add({
      ids: [this.generateUUID()],
      embeddings: [[0]],
      metadatas: [{ user_id: randomUserId }] as any,
    });

    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    const collection = await this.getMigrationsCollection();
    const result = await collection.get({ limit: 1 });
    const ids = Array.isArray(result?.ids) ? result.ids : [];
    const pointId = ids.length > 0 ? String(ids[0]) : this.generateUUID();

    await collection.upsert({
      ids: [pointId],
      embeddings: [[0]],
      metadatas: [{ user_id: userId }] as any,
    });
  }

  async initialize(): Promise<void> {
    await this.getCollection();
    await this.getMigrationsCollection();
  }

  /** Convert a single field filter into a ChromaDB where condition. */
  private static convertCondition(
    key: string,
    value: any,
  ): Record<string, any> | null {
    // Wildcard - ChromaDB has no direct wildcard, so skip this filter.
    if (value === "*") {
      return null;
    }

    if (Array.isArray(value)) {
      return { [key]: { $in: value } };
    }

    if (value !== null && typeof value === "object") {
      const opMap: Record<string, string> = {
        eq: "$eq",
        ne: "$ne",
        gt: "$gt",
        gte: "$gte",
        lt: "$lt",
        lte: "$lte",
        in: "$in",
        nin: "$nin",
      };
      const condition: Record<string, any> = {};
      for (const [op, val] of Object.entries(value)) {
        if (op in opMap) {
          condition[key] = { [opMap[op]]: val };
        } else {
          // contains/icontains and unknown operators fall back to equality.
          condition[key] = { $eq: val };
        }
      }
      return condition;
    }

    return { [key]: { $eq: value } };
  }

  /**
   * Generate a properly formatted `where` clause for ChromaDB from mem0's
   * universal filter format. Supports comparison operators plus $or/$not.
   */
  static generateWhereClause(
    filters?: SearchFilters,
  ): Record<string, any> | undefined {
    if (!filters) {
      return undefined;
    }

    const negateOp: Record<string, string> = {
      eq: "ne",
      ne: "eq",
      gt: "lte",
      gte: "lt",
      lt: "gte",
      lte: "gt",
      in: "nin",
      nin: "in",
    };

    const processed: any[] = [];

    for (const [key, value] of Object.entries(filters)) {
      if (key === "$or" || key === "OR") {
        const orConditions: any[] = [];
        for (const condition of value as any[]) {
          const built: Record<string, any> = {};
          for (const [subKey, subValue] of Object.entries(condition)) {
            const converted = ChromaDB.convertCondition(subKey, subValue);
            if (converted) Object.assign(built, converted);
          }
          if (Object.keys(built).length > 0) orConditions.push(built);
        }
        if (orConditions.length > 1) {
          processed.push({ $or: orConditions });
        } else if (orConditions.length === 1) {
          processed.push(orConditions[0]);
        }
      } else if (key === "$not" || key === "NOT") {
        // De Morgan: NOT(a AND b) is (NOT a) OR (NOT b), so the negated fields
        // within one condition are combined with $or, and separate conditions
        // are combined with $and. This mirrors the Python SDK's ChromaDB port.
        const negatedPerGroup: any[] = [];
        for (const condition of value as any[]) {
          const negatedFields: any[] = [];
          for (const [subKey, subValue] of Object.entries(condition)) {
            if (subValue !== null && typeof subValue === "object") {
              for (const [op, val] of Object.entries(subValue as any)) {
                const neg = negateOp[op];
                if (neg) {
                  const converted = ChromaDB.convertCondition(subKey, {
                    [neg]: val,
                  });
                  if (converted) negatedFields.push(converted);
                }
              }
            } else {
              const converted = ChromaDB.convertCondition(subKey, {
                ne: subValue,
              });
              if (converted) negatedFields.push(converted);
            }
          }
          if (negatedFields.length > 1) {
            negatedPerGroup.push({ $or: negatedFields });
          } else if (negatedFields.length === 1) {
            negatedPerGroup.push(negatedFields[0]);
          }
        }
        if (negatedPerGroup.length > 1) {
          processed.push({ $and: negatedPerGroup });
        } else if (negatedPerGroup.length === 1) {
          processed.push(negatedPerGroup[0]);
        }
      } else {
        const converted = ChromaDB.convertCondition(key, value);
        if (converted) processed.push(converted);
      }
    }

    if (processed.length === 0) {
      return undefined;
    }
    if (processed.length === 1) {
      return processed[0];
    }
    return { $and: processed };
  }
}
