import type { ChromaClient as ChromaClientType, Collection } from "chromadb";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

const MIGRATIONS_COLLECTION = "__mem0_migrations__";
const MIGRATIONS_RECORD_ID = "mem0-user-id";

interface ChromaDBConfig extends VectorStoreConfig {
  collectionName?: string;
  client?: ChromaClientType;
  host?: string;
  port?: number;
  ssl?: boolean;
  path?: string;
  apiKey?: string;
  tenant?: string;
  database?: string;
  headers?: Record<string, string>;
  fetchOptions?: RequestInit;
  embeddingModelDims?: number;
}

export class ChromaDB implements VectorStore {
  private client: ChromaClientType;
  private collection?: Collection;
  private migrationsCollection?: Collection;
  private readonly collectionName: string;
  private readonly dimension: number;
  private _initPromise?: Promise<void>;

  constructor(config: ChromaDBConfig) {
    const { ChromaClient, CloudClient } = this.loadChroma();

    if (config.client) {
      this.client = config.client;
    } else if (config.apiKey) {
      this.client = new CloudClient({
        apiKey: config.apiKey,
        tenant: config.tenant,
        database: config.database || "mem0",
        ...(config.host ? { host: config.host } : {}),
        ...(config.port ? { port: config.port } : {}),
        ...(config.fetchOptions ? { fetchOptions: config.fetchOptions } : {}),
      });
    } else {
      this.client = new ChromaClient({
        ...(config.host ? { host: config.host } : {}),
        ...(config.port ? { port: config.port } : {}),
        ...(config.ssl !== undefined ? { ssl: config.ssl } : {}),
        ...(config.path ? { path: config.path } : {}),
        ...(config.tenant ? { tenant: config.tenant } : {}),
        ...(config.database ? { database: config.database } : {}),
        ...(config.headers ? { headers: config.headers } : {}),
        ...(config.fetchOptions ? { fetchOptions: config.fetchOptions } : {}),
      });
    }

    this.collectionName = config.collectionName || "memories";
    this.dimension = config.embeddingModelDims || config.dimension || 1536;
    this.initialize().catch(console.error);
  }

  private loadChroma(): typeof import("chromadb") {
    try {
      return require("chromadb");
    } catch (error) {
      throw new Error(
        "The 'chromadb' package is required for the Chroma vector store. Install it with `pnpm add chromadb`.",
      );
    }
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    this.collection = await this.client.getOrCreateCollection({
      name: this.collectionName,
      embeddingFunction: null,
    });
    this.migrationsCollection = await this.client.getOrCreateCollection({
      name: MIGRATIONS_COLLECTION,
      embeddingFunction: null,
    });
  }

  private async getCollection(): Promise<Collection> {
    await this.initialize();
    return this.collection!;
  }

  private async getMigrationsCollection(): Promise<Collection> {
    await this.initialize();
    return this.migrationsCollection!;
  }

  private createFilter(
    filters?: SearchFilters,
  ): Record<string, any> | undefined {
    if (!filters || Object.keys(filters).length === 0) return undefined;

    const clauses: Record<string, any>[] = [];

    for (const [rawKey, value] of Object.entries(filters)) {
      if (value === undefined || value === null || value === "*") continue;

      const keyMap: Record<string, string> = {
        $and: "AND",
        $or: "OR",
        $not: "NOT",
      };
      const key = keyMap[rawKey] || rawKey;

      if (key === "AND" || key === "OR") {
        if (!Array.isArray(value)) {
          throw new Error(
            `${key} filter value must be a list of filter dicts, got ${typeof value}`,
          );
        }
        const subFilters = value
          .map((sub) => this.createFilter(sub))
          .filter(Boolean) as Record<string, any>[];
        if (subFilters.length === 1) {
          clauses.push(subFilters[0]);
        } else if (subFilters.length > 1) {
          clauses.push({ [key === "AND" ? "$and" : "$or"]: subFilters });
        }
        continue;
      }

      if (key === "NOT") {
        if (!Array.isArray(value)) {
          throw new Error(
            `NOT filter value must be a list of filter dicts, got ${typeof value}`,
          );
        }
        for (const sub of value) {
          const negated = this.createNegatedFilter(sub);
          if (negated) clauses.push(negated);
        }
        continue;
      }

      clauses.push(this.createFieldFilter(key, value));
    }

    if (clauses.length === 0) return undefined;
    if (clauses.length === 1) return clauses[0];
    return { $and: clauses };
  }

  private createFieldFilter(key: string, value: any): Record<string, any> {
    if (Array.isArray(value)) {
      return { [key]: { $in: value } };
    }

    if (typeof value === "object" && value !== null) {
      const chromaOps: Record<string, any> = {};
      for (const [op, opValue] of Object.entries(value)) {
        switch (op) {
          case "eq":
            chromaOps.$eq = opValue;
            break;
          case "ne":
            chromaOps.$ne = opValue;
            break;
          case "gt":
            chromaOps.$gt = opValue;
            break;
          case "gte":
            chromaOps.$gte = opValue;
            break;
          case "lt":
            chromaOps.$lt = opValue;
            break;
          case "lte":
            chromaOps.$lte = opValue;
            break;
          case "in":
            chromaOps.$in = opValue;
            break;
          case "nin":
            chromaOps.$nin = opValue;
            break;
          case "contains":
          case "icontains":
            console.warn(
              `Filter operator '${op}' is not supported by Chroma metadata filters; using equality.`,
            );
            chromaOps.$eq = opValue;
            break;
          default:
            throw new Error(`Unsupported filter operator '${op}' for Chroma`);
        }
      }
      return { [key]: chromaOps };
    }

    return { [key]: { $eq: value } };
  }

  private createNegatedFilter(
    filters: SearchFilters,
  ): Record<string, any> | undefined {
    const clauses: Record<string, any>[] = [];
    const negateOp: Record<string, string> = {
      eq: "$ne",
      ne: "$eq",
      gt: "$lte",
      gte: "$lt",
      lt: "$gte",
      lte: "$gt",
      in: "$nin",
      nin: "$in",
    };

    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null || value === "*") continue;
      if (typeof value === "object" && !Array.isArray(value)) {
        for (const [op, opValue] of Object.entries(value)) {
          const negated = negateOp[op];
          if (negated) {
            clauses.push({ [key]: { [negated]: opValue } });
          }
        }
      } else {
        clauses.push({ [key]: { $ne: value } });
      }
    }

    if (clauses.length === 0) return undefined;
    if (clauses.length === 1) return clauses[0];
    return { $or: clauses };
  }

  private parseResults(data: Record<string, any>): VectorStoreResult[] {
    const flatten = (value: any): any[] => {
      if (!Array.isArray(value)) return [];
      return Array.isArray(value[0]) ? value[0] : value;
    };

    const ids = flatten(data.ids);
    const distances = flatten(data.distances);
    const metadatas = flatten(data.metadatas);

    return ids.map((id, index) => {
      const rawDistance = distances[index];
      return {
        id: String(id),
        payload: (metadatas[index] as Record<string, any>) || {},
        ...(rawDistance !== undefined && rawDistance !== null
          ? { score: 1 / (1 + rawDistance) }
          : {}),
      };
    });
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
      metadatas: payloads,
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
    const where = this.createFilter(filters);
    const response = await collection.query({
      queryEmbeddings: [query],
      nResults: topK,
      ...(where ? { where } : {}),
      include: ["metadatas", "distances"],
    });
    return this.parseResults(response as Record<string, any>);
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const collection = await this.getCollection();
    const response = await collection.get({
      ids: [vectorId],
      include: ["metadatas"],
    });
    const results = this.parseResults(response as Record<string, any>);
    return results[0] || null;
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const collection = await this.getCollection();
    await collection.update({
      ids: [vectorId],
      embeddings: [vector],
      metadatas: [payload],
    });
  }

  async delete(vectorId: string): Promise<void> {
    const collection = await this.getCollection();
    await collection.delete({ ids: [vectorId] });
  }

  async deleteCol(): Promise<void> {
    if (this._initPromise) {
      await this._initPromise.catch(() => {});
    }
    await this.client.deleteCollection({ name: this.collectionName });
    this.collection = await this.client.getOrCreateCollection({
      name: this.collectionName,
      embeddingFunction: null,
    });
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const collection = await this.getCollection();
    const where = this.createFilter(filters);
    const response = await collection.get({
      ...(where ? { where } : {}),
      limit: topK,
      include: ["metadatas"],
    });
    const results = this.parseResults(response as Record<string, any>);
    return [results, results.length];
  }

  async getUserId(): Promise<string> {
    const collection = await this.getMigrationsCollection();
    const response = await collection.get({
      ids: [MIGRATIONS_RECORD_ID],
      include: ["metadatas"],
    });
    const existing = this.parseResults(response as Record<string, any>)[0];
    if (existing?.payload?.user_id) {
      return existing.payload.user_id as string;
    }

    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await collection.upsert({
      ids: [MIGRATIONS_RECORD_ID],
      embeddings: [new Array(this.dimension).fill(0)],
      metadatas: [{ user_id: randomUserId }],
    });
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    const collection = await this.getMigrationsCollection();
    await collection.upsert({
      ids: [MIGRATIONS_RECORD_ID],
      embeddings: [new Array(this.dimension).fill(0)],
      metadatas: [{ user_id: userId }],
    });
  }
}
