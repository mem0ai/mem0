import { VectorStore } from "./base";
import { SearchFilters, VectorStoreResult } from "../types";
import { ValkeyConfig } from "../types/valkey";

interface ValkeyClient {
  call: (...args: (string | number | Buffer)[]) => Promise<unknown>;
  hset: (key: string, data: Record<string, string | Buffer>) => Promise<number>;
  hgetall: (key: string) => Promise<Record<string, string>>;
  exists: (key: string) => Promise<number>;
  del: (key: string) => Promise<number>;
  get: (key: string) => Promise<string | null>;
  set: (key: string, value: string) => Promise<"OK">;
  quit: () => Promise<"OK">;
  on: (event: string, listener: (...args: any[]) => void) => void;
}

/**
 * Escape Valkey Search TAG filter special characters.
 */
function escapeTagValue(value: unknown): string {
  return String(value).replace(
    /([,.<>{}\[\]"':;!@#$%^&*()\-+=~|/\\\s])/g,
    "\\$1",
  );
}

const EXCLUDED_KEYS = new Set([
  "user_id",
  "agent_id",
  "run_id",
  "hash",
  "data",
  "created_at",
  "updated_at",
]);

function toSnakeCase(obj: Record<string, any>): Record<string, any> {
  if (typeof obj !== "object" || obj === null) return obj;
  return Object.fromEntries(
    Object.entries(obj).map(([key, value]) => [
      key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`),
      value,
    ]),
  );
}

function toCamelCase(obj: Record<string, any>): Record<string, any> {
  if (typeof obj !== "object" || obj === null) return obj;
  return Object.fromEntries(
    Object.entries(obj).map(([key, value]) => [
      key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase()),
      value,
    ]),
  );
}

interface ValkeySearchDoc {
  memory_id?: string;
  hash?: string;
  memory?: string;
  created_at?: string;
  updated_at?: string;
  agent_id?: string;
  run_id?: string;
  user_id?: string;
  metadata?: string;
  vector_score?: string;
}

function parseFtSearchResults(result: unknown[]): {
  total: number;
  docs: ValkeySearchDoc[];
} {
  const total = Number(result[0]) || 0;
  const docs: ValkeySearchDoc[] = [];
  for (let i = 1; i < result.length; i += 2) {
    const fields = result[i + 1] as string[];
    const doc: ValkeySearchDoc = {};
    for (let j = 0; j < fields.length; j += 2) {
      const key = fields[j] as keyof ValkeySearchDoc;
      (doc as Record<string, string>)[key] = fields[j + 1] as string;
    }
    docs.push(doc);
  }
  return { total, docs };
}

function parseValkeyUrl(url: string): { host: string; port: number } {
  const normalized = url.replace(/^valkey:\/\//, "redis://");
  const parsed = new URL(normalized);
  return {
    host: parsed.hostname,
    port: parsed.port ? parseInt(parsed.port, 10) : 6379,
  };
}

function formatTimestamp(timestamp: number): string {
  return new Date(timestamp * 1000).toISOString();
}

async function loadIovalkey(): Promise<typeof import("iovalkey")> {
  try {
    return await import("iovalkey");
  } catch {
    throw new Error(
      "iovalkey is required for the Valkey vector store. Install it with: npm install iovalkey",
    );
  }
}

export class ValkeyDB implements VectorStore {
  private client!: ValkeyClient;
  private readonly collectionName: string;
  private readonly indexPrefix: string;
  private readonly embeddingModelDims: number;
  private readonly timezone: string;
  private readonly indexType: "hnsw" | "flat";
  private readonly hnswM: number;
  private readonly hnswEfConstruction: number;
  private readonly hnswEfRuntime: number;
  private readonly clusterMode: boolean;
  private readonly valkeyUrl: string;
  private _initPromise?: Promise<void>;

  constructor(config: ValkeyConfig) {
    this.collectionName = config.collectionName;
    this.indexPrefix = `mem0:${config.collectionName}`;
    this.embeddingModelDims = config.embeddingModelDims;
    this.timezone = config.timezone ?? "UTC";
    this.indexType = (config.indexType ?? "hnsw").toLowerCase() as
      | "hnsw"
      | "flat";
    this.hnswM = config.hnswM ?? 16;
    this.hnswEfConstruction = config.hnswEfConstruction ?? 200;
    this.hnswEfRuntime = config.hnswEfRuntime ?? 10;
    this.clusterMode = config.clusterMode ?? false;
    this.valkeyUrl = config.valkeyUrl;

    if (this.indexType !== "hnsw" && this.indexType !== "flat") {
      throw new Error(
        `Invalid indexType: ${config.indexType}. Must be 'hnsw' or 'flat'`,
      );
    }

    this.initialize().catch((err) => {
      console.error("Failed to initialize Valkey:", err);
      throw err;
    });
  }

  private buildIndexCreateCommand(
    collectionName: string,
    embeddingDims: number,
    distanceMetric: string,
    prefix: string,
  ): (string | number)[] {
    const vectorConfig =
      this.indexType === "hnsw"
        ? [
            "embedding",
            "VECTOR",
            "HNSW",
            "12",
            "TYPE",
            "FLOAT32",
            "DIM",
            String(embeddingDims),
            "DISTANCE_METRIC",
            distanceMetric,
            "M",
            String(this.hnswM),
            "EF_CONSTRUCTION",
            String(this.hnswEfConstruction),
            "EF_RUNTIME",
            String(this.hnswEfRuntime),
          ]
        : [
            "embedding",
            "VECTOR",
            "FLAT",
            "6",
            "TYPE",
            "FLOAT32",
            "DIM",
            String(embeddingDims),
            "DISTANCE_METRIC",
            distanceMetric,
          ];

    return [
      "FT.CREATE",
      collectionName,
      "ON",
      "HASH",
      "PREFIX",
      "1",
      prefix,
      "SCHEMA",
      "memory_id",
      "TAG",
      "hash",
      "TAG",
      "agent_id",
      "TAG",
      "run_id",
      "TAG",
      "user_id",
      "TAG",
      "memory",
      "TEXT",
      "metadata",
      "TAG",
      "created_at",
      "NUMERIC",
      "updated_at",
      "NUMERIC",
      ...vectorConfig,
    ];
  }

  private async ensureSearchModule(): Promise<void> {
    try {
      await this.client.call("FT._LIST");
    } catch (error: any) {
      const message = String(error?.message ?? error).toLowerCase();
      if (message.includes("unknown command")) {
        throw new Error(
          "Valkey search module is not available. Please ensure Valkey is running with the search module enabled.",
        );
      }
      throw error;
    }
  }

  private async createIndex(): Promise<void> {
    await this.ensureSearchModule();

    try {
      await this.client.call("FT.INFO", this.collectionName);
      return;
    } catch (error: any) {
      const message = String(error?.message ?? error).toLowerCase();
      if (
        !message.includes("not found") &&
        !message.includes("unknown index")
      ) {
        throw error;
      }
    }

    const cmd = this.buildIndexCreateCommand(
      this.collectionName,
      this.embeddingModelDims,
      "COSINE",
      this.indexPrefix,
    );
    await this.client.call(...cmd);
  }

  private async connectClient(): Promise<void> {
    const iovalkey = await loadIovalkey();
    const Valkey = iovalkey.default;

    if (this.clusterMode) {
      const { Cluster } = iovalkey;
      const { host, port } = parseValkeyUrl(this.valkeyUrl);
      this.client = new Cluster([{ host, port }]) as unknown as ValkeyClient;
    } else {
      this.client = new Valkey(this.valkeyUrl) as unknown as ValkeyClient;
    }

    this.client.on("error", (err) =>
      console.error("Valkey Client Error:", err),
    );
    this.client.on("connect", () => console.log("Valkey Client Connected"));
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }
    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    await this.connectClient();
    await this.createIndex();
  }

  private buildSearchQuery(knnPart: string, filters?: SearchFilters): string {
    const snakeFilters = filters ? toSnakeCase(filters) : undefined;
    if (
      !snakeFilters ||
      !Object.entries(snakeFilters).some(
        ([, value]) => value !== null && value !== undefined,
      )
    ) {
      return `*=>${knnPart}`;
    }

    const filterParts = Object.entries(snakeFilters)
      .filter(([, value]) => value !== null && value !== undefined)
      .map(([key, value]) => `@${key}:{${escapeTagValue(value)}}`);

    if (!filterParts.length) {
      return `*=>${knnPart}`;
    }

    return `${filterParts.join(" ")} =>${knnPart}`;
  }

  private docToResult(doc: ValkeySearchDoc): VectorStoreResult {
    const rawDistance = doc.vector_score ? Number(doc.vector_score) : undefined;
    const score =
      rawDistance !== undefined ? Math.max(0, 1 - rawDistance) : undefined;

    const resultPayload: Record<string, any> = {
      hash: doc.hash ?? "",
      data: doc.memory ?? "",
      created_at: doc.created_at
        ? formatTimestamp(Number(doc.created_at))
        : undefined,
    };

    if (doc.updated_at) {
      resultPayload.updated_at = formatTimestamp(Number(doc.updated_at));
    }
    if (doc.agent_id) resultPayload.agent_id = doc.agent_id;
    if (doc.run_id) resultPayload.run_id = doc.run_id;
    if (doc.user_id) resultPayload.user_id = doc.user_id;

    if (doc.metadata) {
      try {
        Object.assign(resultPayload, JSON.parse(doc.metadata));
      } catch {
        console.warn("Failed to parse Valkey metadata:", doc.metadata);
      }
    }

    return {
      id: doc.memory_id ?? "",
      payload: toCamelCase(resultPayload),
      score,
    };
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await Promise.all(
      vectors.map(async (vector, idx) => {
        const payload = toSnakeCase(payloads[idx] ?? {});
        const id = ids[idx];
        const key = `${this.indexPrefix}:${id}`;

        if (!payload.created_at) {
          payload.created_at = new Date().toISOString();
        }

        const hashData: Record<string, string | Buffer> = {
          memory_id: id,
          hash: payload.hash ?? `hash_${id}`,
          memory: payload.data ?? `data_${id}`,
          created_at: String(
            Math.floor(new Date(payload.created_at).getTime() / 1000),
          ),
          embedding: Buffer.from(new Float32Array(vector).buffer),
          metadata: JSON.stringify(
            Object.fromEntries(
              Object.entries(payload).filter(([k]) => !EXCLUDED_KEYS.has(k)),
            ),
          ),
        };

        for (const field of ["agent_id", "run_id", "user_id"]) {
          if (field in payload) {
            hashData[field] = String(payload[field]);
          }
        }

        await this.client.hset(key, hashData);
      }),
    );
  }

  async keywordSearch(): Promise<null> {
    return null;
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const vectorBytes = Buffer.from(new Float32Array(query).buffer);
    const knnPart =
      this.indexType === "hnsw"
        ? `[KNN ${topK} @embedding $vec_param EF_RUNTIME ${this.hnswEfRuntime} AS vector_score]`
        : `[KNN ${topK} @embedding $vec_param AS vector_score]`;

    const searchQuery = this.buildSearchQuery(knnPart, filters);
    const result = (await this.client.call(
      "FT.SEARCH",
      this.collectionName,
      searchQuery,
      "PARAMS",
      "2",
      "vec_param",
      vectorBytes,
      "RETURN",
      "10",
      "memory_id",
      "hash",
      "agent_id",
      "run_id",
      "user_id",
      "memory",
      "metadata",
      "created_at",
      "updated_at",
      "vector_score",
      "DIALECT",
      "2",
      "LIMIT",
      "0",
      String(topK),
    )) as unknown[];

    const { docs } = parseFtSearchResults(result);
    return docs.map((doc) => this.docToResult(doc));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const key = `${this.indexPrefix}:${vectorId}`;
    const exists = await this.client.exists(key);
    if (!exists) {
      return null;
    }

    const result = await this.client.hgetall(key);
    if (!Object.keys(result).length) {
      return null;
    }

    const doc: ValkeySearchDoc = {
      memory_id: result.memory_id,
      hash: result.hash,
      memory: result.memory,
      created_at: result.created_at,
      updated_at: result.updated_at,
      agent_id: result.agent_id,
      run_id: result.run_id,
      user_id: result.user_id,
      metadata: result.metadata,
    };

    return this.docToResult(doc);
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const snakePayload = toSnakeCase(payload);
    const key = `${this.indexPrefix}:${vectorId}`;

    if (!snakePayload.created_at) {
      snakePayload.created_at = new Date().toISOString();
    }

    const hashData: Record<string, string | Buffer> = {
      memory_id: vectorId,
      hash: snakePayload.hash ?? `hash_${vectorId}`,
      memory: snakePayload.data ?? `data_${vectorId}`,
      created_at: String(
        Math.floor(new Date(snakePayload.created_at).getTime() / 1000),
      ),
      embedding: Buffer.from(new Float32Array(vector).buffer),
      metadata: JSON.stringify(
        Object.fromEntries(
          Object.entries(snakePayload).filter(([k]) => !EXCLUDED_KEYS.has(k)),
        ),
      ),
    };

    if (snakePayload.updated_at) {
      hashData.updated_at = String(
        Math.floor(new Date(snakePayload.updated_at).getTime() / 1000),
      );
    }

    for (const field of ["agent_id", "run_id", "user_id"]) {
      if (field in snakePayload) {
        hashData[field] = String(snakePayload[field]);
      }
    }

    await this.client.hset(key, hashData);
  }

  async delete(vectorId: string): Promise<void> {
    const key = `${this.indexPrefix}:${vectorId}`;
    const exists = await this.client.exists(key);
    if (!exists) {
      console.warn(`Memory with ID ${vectorId} does not exist`);
      return;
    }
    await this.client.del(key);
  }

  async deleteCol(): Promise<void> {
    try {
      await this.client.call("FT.DROPINDEX", this.collectionName);
    } catch (error: any) {
      const message = String(error?.message ?? error);
      if (!message.includes("Unknown index name")) {
        throw error;
      }
    }
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const dummyVector = new Array(this.embeddingModelDims).fill(0);
    const results = await this.search(dummyVector, topK, filters);
    return [results, results.length];
  }

  async close(): Promise<void> {
    await this.client.quit();
  }

  async getUserId(): Promise<string> {
    const userId = await this.client.get("memory_migrations:1");
    if (userId) {
      return userId;
    }

    const randomUserId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.client.set("memory_migrations:1", randomUserId);
    return randomUserId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.client.set("memory_migrations:1", userId);
  }
}
