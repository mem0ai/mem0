import {
  ChromaClient,
  CloudClient,
  type ChromaClientArgs,
  type Collection,
  type Metadata,
  type Where,
} from "chromadb";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface ChromaConfig extends VectorStoreConfig {
  client?: ChromaClient;
  host?: string;
  port?: number;
  path?: string;
  api_key?: string;
  apiKey?: string;
  tenant?: string;
  database?: string;
  ssl?: boolean;
  headers?: Record<string, string>;
  fetchOptions?: RequestInit;
  collectionName: string;
}

const USER_ID_COLLECTION_NAME = "memory_migrations";

export class ChromaDB implements VectorStore {
  private client: ChromaClient;
  private collection?: Collection;
  private userIdCollection?: Collection;
  private readonly collectionName: string;
  private _initPromise?: Promise<void>;

  constructor(config: ChromaConfig) {
    if (config.client) {
      this.client = config.client;
    } else if ((config.api_key || config.apiKey) && config.tenant) {
      this.client = new CloudClient({
        apiKey: config.api_key || config.apiKey,
        tenant: config.tenant,
        database: config.database || "mem0",
        host: config.host,
        port: config.port,
        fetchOptions: config.fetchOptions,
      });
    } else {
      const clientArgs: Partial<ChromaClientArgs> = {};

      if (config.host) {
        clientArgs.host = config.host;
      }
      if (config.port) {
        clientArgs.port = config.port;
      }
      if (config.path) {
        clientArgs.path = config.path;
      }
      if (config.ssl !== undefined) {
        clientArgs.ssl = config.ssl;
      }
      if (config.tenant) {
        clientArgs.tenant = config.tenant;
      }
      if (config.database) {
        clientArgs.database = config.database;
      }
      if (config.headers) {
        clientArgs.headers = config.headers;
      }
      if (config.fetchOptions) {
        clientArgs.fetchOptions = config.fetchOptions;
      }

      this.client = new ChromaClient(clientArgs);
    }

    this.collectionName = config.collectionName;
    this.initialize().catch((err) => {
      console.error("Failed to initialize ChromaDB:", err);
      throw err;
    });
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    this.collection = await this.createCol(this.collectionName);
    this.userIdCollection = await this.createCol(USER_ID_COLLECTION_NAME);
  }

  private async getCollection(): Promise<Collection> {
    await this.initialize();
    if (!this.collection) {
      throw new Error(
        `Chroma collection '${this.collectionName}' is not initialized`,
      );
    }
    return this.collection;
  }

  private async getUserIdCollection(): Promise<Collection> {
    await this.initialize();
    if (!this.userIdCollection) {
      throw new Error(
        `Chroma collection '${USER_ID_COLLECTION_NAME}' is not initialized`,
      );
    }
    return this.userIdCollection;
  }

  private async createCol(name: string): Promise<Collection> {
    return this.client.getOrCreateCollection({
      name,
      embeddingFunction: null,
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
      metadatas: payloads.map((payload) => (payload || {}) as Metadata),
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
    const where = filters ? ChromaDB.generateWhereClause(filters) : undefined;
    const results = await collection.query({
      queryEmbeddings: [query],
      nResults: topK,
      where,
    });

    return this.parseQueryResults(results);
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const collection = await this.getCollection();
    const result = await collection.get({
      ids: [vectorId],
      include: ["metadatas"],
    });

    const parsed = this.parseGetResults(result);
    return parsed[0] || null;
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
      metadatas: [(payload || {}) as Metadata],
    });
  }

  async delete(vectorId: string): Promise<void> {
    const collection = await this.getCollection();
    await collection.delete({ ids: [vectorId] });
  }

  async deleteCol(): Promise<void> {
    try {
      await this.client.deleteCollection({ name: this.collectionName });
    } catch (error: any) {
      if (!ChromaDB.isNotFoundError(error)) {
        throw error;
      }
    } finally {
      this.collection = undefined;
      this._initPromise = undefined;
    }
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const collection = await this.getCollection();
    const where = filters ? ChromaDB.generateWhereClause(filters) : undefined;
    const result = await collection.get({
      where,
      limit: topK,
      include: ["metadatas"],
    });
    const parsed = this.parseGetResults(result);

    return [parsed, parsed.length];
  }

  async reset(): Promise<void> {
    await this.deleteCol();
    await this.initialize();
  }

  async listCols(): Promise<Collection[]> {
    return this.client.listCollections();
  }

  async colInfo(): Promise<Collection> {
    return this.client.getCollection({ name: this.collectionName });
  }

  async getUserId(): Promise<string> {
    const collection = await this.getUserIdCollection();
    const result = await collection.get({
      limit: 1,
      include: ["metadatas"],
    });
    const parsed = this.parseGetResults(result);
    const existingUserId = parsed[0]?.payload?.user_id;

    if (typeof existingUserId === "string" && existingUserId.length > 0) {
      return existingUserId;
    }

    const randomUserId = this.generateUserId();
    await this.setUserId(randomUserId);
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    const collection = await this.getUserIdCollection();
    const existing = await collection.get({
      limit: 100,
      include: ["metadatas"],
    });

    if (existing.ids.length > 0) {
      await collection.delete({ ids: existing.ids });
    }

    await collection.add({
      ids: [this.generateUserId()],
      embeddings: [[0]],
      metadatas: [{ user_id: userId }],
    });
  }

  private parseQueryResults(data: any): VectorStoreResult[] {
    const ids = this.firstQueryResultArray<string>(data.ids);
    const distances = this.firstQueryResultArray<number | null>(data.distances);
    const metadatas = this.firstQueryResultArray<Record<string, any> | null>(
      data.metadatas,
    );
    const maxLength = Math.max(ids.length, distances.length, metadatas.length);
    const results: VectorStoreResult[] = [];

    for (let idx = 0; idx < maxLength; idx++) {
      const id = ids[idx];
      if (!id) {
        continue;
      }

      const distance = distances[idx];
      results.push({
        id,
        payload: metadatas[idx] || {},
        score:
          typeof distance === "number" ? 1.0 / (1.0 + distance) : undefined,
      });
    }

    return results;
  }

  private parseGetResults(data: any): VectorStoreResult[] {
    const ids: string[] = Array.isArray(data.ids) ? data.ids : [];
    const metadatas: (Record<string, any> | null)[] = Array.isArray(
      data.metadatas,
    )
      ? data.metadatas
      : [];

    return ids.map((id, idx) => ({
      id,
      payload: metadatas[idx] || {},
    }));
  }

  private firstQueryResultArray<T>(value: unknown): T[] {
    if (!Array.isArray(value)) {
      return [];
    }
    if (Array.isArray(value[0])) {
      return value[0] as T[];
    }
    return value as T[];
  }

  private generateUserId(): string {
    return (
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15)
    );
  }

  private static isNotFoundError(error: any): boolean {
    return (
      error?.name === "ChromaNotFoundError" ||
      error?.message?.toLowerCase().includes("not found")
    );
  }

  private static generateWhereClause(
    filters: SearchFilters,
  ): Where | undefined {
    if (!filters || Object.keys(filters).length === 0) {
      return undefined;
    }

    const processedFilters: Where[] = [];

    for (const [key, value] of Object.entries(filters)) {
      if (key === "$and") {
        const andConditions = ChromaDB.convertLogicalConditions(value);
        if (andConditions.length > 1) {
          processedFilters.push({ $and: andConditions } as Where);
        } else if (andConditions.length === 1) {
          processedFilters.push(andConditions[0]);
        }
      } else if (key === "$or") {
        const orConditions = ChromaDB.convertLogicalConditions(value);
        if (orConditions.length > 1) {
          processedFilters.push({ $or: orConditions } as Where);
        } else if (orConditions.length === 1) {
          processedFilters.push(orConditions[0]);
        }
      } else if (key === "$not") {
        const negated = ChromaDB.convertNotConditions(value);
        if (negated.length > 1) {
          processedFilters.push({ $and: negated } as Where);
        } else if (negated.length === 1) {
          processedFilters.push(negated[0]);
        }
      } else {
        const converted = ChromaDB.convertCondition(key, value);
        if (converted) {
          processedFilters.push(converted);
        }
      }
    }

    if (processedFilters.length === 0) {
      return undefined;
    }
    if (processedFilters.length === 1) {
      return processedFilters[0];
    }
    return { $and: processedFilters } as Where;
  }

  private static convertLogicalConditions(value: any): Where[] {
    if (!Array.isArray(value)) {
      return [];
    }

    return value
      .map((condition) => ChromaDB.generateWhereClause(condition))
      .filter((condition): condition is Where => Boolean(condition));
  }

  private static convertNotConditions(value: any): Where[] {
    if (!Array.isArray(value)) {
      return [];
    }

    const negated: Where[] = [];
    const negateOperator: Record<string, string> = {
      eq: "$ne",
      ne: "$eq",
      gt: "$lte",
      gte: "$lt",
      lt: "$gte",
      lte: "$gt",
      in: "$nin",
      nin: "$in",
    };

    for (const condition of value) {
      const negatedFields: Where[] = [];

      for (const [key, subValue] of Object.entries(condition || {})) {
        if (
          typeof subValue === "object" &&
          subValue !== null &&
          !Array.isArray(subValue)
        ) {
          for (const [operator, operatorValue] of Object.entries(subValue)) {
            const negatedOperator = negateOperator[operator];
            if (negatedOperator) {
              negatedFields.push({
                [key]: { [negatedOperator]: operatorValue },
              } as Where);
            }
          }
        } else if (subValue !== "*") {
          negatedFields.push({ [key]: { $ne: subValue } } as Where);
        }
      }

      if (negatedFields.length > 1) {
        negated.push({ $or: negatedFields } as Where);
      } else if (negatedFields.length === 1) {
        negated.push(negatedFields[0]);
      }
    }

    return negated;
  }

  private static convertCondition(key: string, value: any): Where | undefined {
    if (value === "*") {
      return undefined;
    }

    if (Array.isArray(value)) {
      return { [key]: { $in: value } } as Where;
    }

    if (typeof value === "object" && value !== null) {
      const condition: Record<string, any> = {};
      const operatorMap: Record<string, string> = {
        eq: "$eq",
        ne: "$ne",
        gt: "$gt",
        gte: "$gte",
        lt: "$lt",
        lte: "$lte",
        in: "$in",
        nin: "$nin",
      };

      for (const [operator, operatorValue] of Object.entries(value)) {
        const chromaOperator = operatorMap[operator] || "$eq";
        condition[chromaOperator] = operatorValue;
      }

      return { [key]: condition } as Where;
    }

    return { [key]: { $eq: value } } as Where;
  }
}
