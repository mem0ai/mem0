import { ChromaClient, CloudClient, Collection } from "chromadb";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

const MIGRATIONS_COLLECTION = "__mem0_migrations__";
const MIGRATIONS_RECORD_ID = "mem0-user-id";

interface ChromaConfig extends VectorStoreConfig {
  /** Pre-configured ChromaClient (or CloudClient) instance. */
  client?: ChromaClient;
  /** Host address for a self-hosted Chroma server. Defaults to 'localhost'. */
  host?: string;
  /** Port for a self-hosted Chroma server. Defaults to 8000. */
  port?: number;
  /** Whether to use SSL/HTTPS when connecting to a self-hosted server. */
  ssl?: boolean;
  /** ChromaDB Cloud API key. */
  apiKey?: string;
  /** ChromaDB Cloud tenant ID. */
  tenant?: string;
  collectionName: string;
  embeddingModelDims?: number;
  dimension?: number;
}

type WhereClause = Record<string, any> | undefined;

// Normalize $and/$or keys and dedupe, mirroring the Qdrant provider's approach.
const KEY_MAP: Record<string, string> = {
  AND: "$and",
  OR: "$or",
};

export class ChromaDB implements VectorStore {
  private client: ChromaClient;
  private readonly collectionName: string;
  private readonly dimension: number;
  private collection?: Collection;
  private migrationsCollection?: Collection;
  private _initPromise?: Promise<void>;

  constructor(config: ChromaConfig) {
    if (config.client) {
      this.client = config.client;
    } else if (config.apiKey && config.tenant) {
      this.client = new CloudClient({
        apiKey: config.apiKey,
        tenant: config.tenant,
        database: "mem0",
      });
    } else {
      this.client = new ChromaClient({
        host: config.host,
        port: config.port,
        ssl: config.ssl,
      });
    }

    this.collectionName = config.collectionName;
    this.dimension = config.embeddingModelDims || config.dimension || 1536;

    this.initialize().catch(console.error);
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

  private zeroVector(): number[] {
    return new Array(this.dimension).fill(0);
  }

  /**
   * Build a Chroma `Where` clause from mem0's universal filter format.
   * Chroma has no native NOT operator, so `NOT` is implemented by negating
   * each nested condition's comparison operator, mirroring the Python provider.
   */
  private buildFieldCondition(
    key: string,
    value: any,
  ): Record<string, any> | null {
    if (value === "*") {
      return null;
    }
    if (typeof value !== "object" || value === null) {
      return { [key]: { $eq: value } };
    }
    if (Array.isArray(value)) {
      return { [key]: { $in: value } };
    }

    const operatorExpr: Record<string, any> = {};
    for (const [op, val] of Object.entries(value)) {
      switch (op) {
        case "eq":
          operatorExpr.$eq = val;
          break;
        case "ne":
          operatorExpr.$ne = val;
          break;
        case "gt":
          operatorExpr.$gt = val;
          break;
        case "gte":
          operatorExpr.$gte = val;
          break;
        case "lt":
          operatorExpr.$lt = val;
          break;
        case "lte":
          operatorExpr.$lte = val;
          break;
        case "in":
          operatorExpr.$in = val;
          break;
        case "nin":
          operatorExpr.$nin = val;
          break;
        case "contains":
        case "icontains":
          // ChromaDB metadata filters don't support substring match — fall back to equality.
          operatorExpr.$eq = val;
          break;
        default:
          operatorExpr.$eq = val;
      }
    }
    return { [key]: operatorExpr };
  }

  private negateOp(op: string): string | undefined {
    const negateMap: Record<string, string> = {
      eq: "ne",
      ne: "eq",
      gt: "lte",
      gte: "lt",
      lt: "gte",
      lte: "gt",
      in: "nin",
      nin: "in",
    };
    return negateMap[op];
  }

  private createFilter(filters?: SearchFilters): WhereClause {
    if (!filters || Object.keys(filters).length === 0) return undefined;

    const normalized: Record<string, any> = {};
    for (const [key, value] of Object.entries(filters)) {
      const normKey = KEY_MAP[key] || key;
      if (!(normKey in normalized)) {
        normalized[normKey] = value;
      }
    }

    const processedFilters: Record<string, any>[] = [];

    for (const [key, value] of Object.entries(normalized)) {
      if (key === "$or") {
        const orConditions: Record<string, any>[] = [];
        for (const condition of value as Record<string, any>[]) {
          const built = this.createFilter(condition);
          if (built) orConditions.push(built);
        }
        if (orConditions.length > 1) {
          processedFilters.push({ $or: orConditions });
        } else if (orConditions.length === 1) {
          processedFilters.push(orConditions[0]);
        }
      } else if (key === "$and") {
        const andConditions: Record<string, any>[] = [];
        for (const condition of value as Record<string, any>[]) {
          const built = this.createFilter(condition);
          if (built) andConditions.push(built);
        }
        if (andConditions.length > 1) {
          processedFilters.push({ $and: andConditions });
        } else if (andConditions.length === 1) {
          processedFilters.push(andConditions[0]);
        }
      } else if (key === "NOT" || key === "$not") {
        const negatedGroup: Record<string, any>[] = [];
        for (const condition of value as Record<string, any>[]) {
          const negatedFields: Record<string, any>[] = [];
          for (const [subKey, subValue] of Object.entries(condition)) {
            if (
              typeof subValue === "object" &&
              subValue !== null &&
              !Array.isArray(subValue)
            ) {
              for (const [op, val] of Object.entries(subValue)) {
                const neg = this.negateOp(op);
                if (neg) negatedFields.push({ [subKey]: { [`$${neg}`]: val } });
              }
            } else {
              negatedFields.push({ [subKey]: { $ne: subValue } });
            }
          }
          if (negatedFields.length > 1) {
            negatedGroup.push({ $or: negatedFields });
          } else if (negatedFields.length === 1) {
            negatedGroup.push(negatedFields[0]);
          }
        }
        if (negatedGroup.length > 1) {
          processedFilters.push({ $and: negatedGroup });
        } else if (negatedGroup.length === 1) {
          processedFilters.push(negatedGroup[0]);
        }
      } else {
        const converted = this.buildFieldCondition(key, value);
        if (converted) processedFilters.push(converted);
      }
    }

    if (processedFilters.length === 0) return undefined;
    if (processedFilters.length === 1) return processedFilters[0];
    return { $and: processedFilters };
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.collection!.add({
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
    const where = this.createFilter(filters);
    const results = await this.collection!.query({
      queryEmbeddings: [query],
      nResults: topK,
      where,
    });

    const ids = results.ids[0] || [];
    const distances = results.distances[0] || [];
    const metadatas = results.metadatas[0] || [];

    return ids.map((id, i) => {
      const distance = distances[i];
      const score = distance != null ? 1.0 / (1.0 + distance) : undefined;
      return {
        id,
        payload: metadatas[i] || {},
        score,
      };
    });
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const result = await this.collection!.get({ ids: [vectorId] });
    if (!result.ids.length) return null;
    return {
      id: result.ids[0],
      payload: result.metadatas[0] || {},
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.collection!.update({
      ids: [vectorId],
      embeddings: vector ? [vector] : undefined,
      metadatas: payload ? [payload] : undefined,
    });
  }

  async delete(vectorId: string): Promise<void> {
    await this.collection!.delete({ ids: [vectorId] });
  }

  async deleteCol(): Promise<void> {
    await this.client.deleteCollection({ name: this.collectionName });
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const where = this.createFilter(filters);
    const result = await this.collection!.get({ where, limit: topK });

    const results = result.ids.map((id, i) => ({
      id,
      payload: result.metadatas[i] || {},
    }));

    return [results, results.length];
  }

  async getUserId(): Promise<string> {
    const result = await this.migrationsCollection!.get({
      ids: [MIGRATIONS_RECORD_ID],
    });

    if (result.ids.length > 0) {
      return (result.metadatas[0] as Record<string, any> | null)
        ?.user_id as string;
    }

    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);

    await this.migrationsCollection!.add({
      ids: [MIGRATIONS_RECORD_ID],
      embeddings: [this.zeroVector()],
      metadatas: [{ user_id: randomUserId }],
    });

    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    const result = await this.migrationsCollection!.get({
      ids: [MIGRATIONS_RECORD_ID],
    });

    if (result.ids.length > 0) {
      await this.migrationsCollection!.update({
        ids: [MIGRATIONS_RECORD_ID],
        metadatas: [{ user_id: userId }],
      });
    } else {
      await this.migrationsCollection!.add({
        ids: [MIGRATIONS_RECORD_ID],
        embeddings: [this.zeroVector()],
        metadatas: [{ user_id: userId }],
      });
    }
  }
}
