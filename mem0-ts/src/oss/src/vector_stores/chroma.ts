import type { ChromaClient, CloudClient } from "chromadb";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
import { loadPeer } from "../utils/load_peer";

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

    const sdk = await loadPeer(
      "chromadb",
      "Chroma vector store",
      () => import("chromadb"),
    );

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
  ): Array<Record<string, any>> {
    // Wildcard - ChromaDB has no direct wildcard, so skip this filter.
    if (value === "*") {
      return [];
    }

    if (Array.isArray(value)) {
      return [{ [key]: { $in: value } }];
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
      // ChromaDB allows exactly one operator per field expression, so each
      // operator becomes its own clause (combined with $and by the caller).
      // Previously each operator overwrote the last, silently dropping range
      // bounds. contains/icontains and unknown operators fall back to
      // equality.
      return Object.entries(value).map(([op, val]) => ({
        [key]: { [opMap[op] ?? "$eq"]: val },
      }));
    }

    return [{ [key]: { $eq: value } }];
  }

  /** Combine clauses under a logical operator, unwrapping singletons. */
  private static combineClauses(
    clauses: Array<Record<string, any>>,
    operator: "$and" | "$or",
  ): Record<string, any> | null {
    if (clauses.length === 0) {
      return null;
    }
    if (clauses.length === 1) {
      return clauses[0];
    }
    return { [operator]: clauses };
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
          const subClauses: Array<Record<string, any>> = [];
          for (const [subKey, subValue] of Object.entries(condition)) {
            subClauses.push(...ChromaDB.convertCondition(subKey, subValue));
          }
          // Multi-field conditions must be wrapped in $and — ChromaDB rejects
          // flat objects with more than one field per level.
          const combined = ChromaDB.combineClauses(subClauses, "$and");
          if (combined) orConditions.push(combined);
        }
        const combinedOr = ChromaDB.combineClauses(orConditions, "$or");
        if (combinedOr) processed.push(combinedOr);
      } else if (key === "$not" || key === "NOT") {
        // De Morgan: NOT(a AND b) is (NOT a) OR (NOT b), so the negated fields
        // within one condition are combined with $or, and separate conditions
        // are combined with $and. This mirrors the Python SDK's ChromaDB port.
        const negatedPerGroup: any[] = [];
        for (const condition of value as any[]) {
          const negatedFields: Array<Record<string, any>> = [];
          for (const [subKey, subValue] of Object.entries(condition)) {
            if (subValue !== null && typeof subValue === "object") {
              for (const [op, val] of Object.entries(subValue as any)) {
                // Unknown operators mirror the positive-path equality
                // fallback as inequality (previously they were silently
                // dropped, which could erase the entire NOT clause).
                const neg = negateOp[op] ?? "ne";
                negatedFields.push(
                  ...ChromaDB.convertCondition(subKey, { [neg]: val }),
                );
              }
            } else {
              negatedFields.push(
                ...ChromaDB.convertCondition(subKey, { ne: subValue }),
              );
            }
          }
          const combined = ChromaDB.combineClauses(negatedFields, "$or");
          if (combined) negatedPerGroup.push(combined);
        }
        const combinedNot = ChromaDB.combineClauses(negatedPerGroup, "$and");
        if (combinedNot) processed.push(combinedNot);
      } else {
        const combined = ChromaDB.combineClauses(
          ChromaDB.convertCondition(key, value),
          "$and",
        );
        if (combined) processed.push(combined);
      }
    }

    return ChromaDB.combineClauses(processed, "$and") ?? undefined;
  }
}
