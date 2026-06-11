import { Client, ClientConfig, query } from "topk-js";
import {
  field,
  filter as topkFilter,
  fn,
  match,
  not,
  select,
} from "topk-js/query";
import { f32Vector, keywordIndex, text, vectorIndex } from "topk-js/schema";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
import { VectorStore } from "./base";

const METRIC_MAP: Record<string, string> = {
  cosine: "cosine",
  euclidean: "euclidean",
  dot: "dot_product",
};

const MIGRATIONS_COLLECTION_NAME = "memory_migrations";

// All fields Mem0 expects in the payload
// See: mem0-ts/src/oss/src/memory/index.ts (excludedKeys)
const MEM0_FIELDS = [
  "data",
  "hash",
  "createdAt",
  "updatedAt",
  "textLemmatized",
  "attributedTo",
  "user_id",
  "agent_id",
  "run_id",
  "actor_id",
  "role",
];

function generateRandomUserId(): string {
  return (
    Math.random().toString(36).substring(2, 15) +
    Math.random().toString(36).substring(2, 15)
  );
}

interface TopKConfig extends VectorStoreConfig {
  apiKey?: string;
  region?: string;
  host?: string;
  https?: boolean;
  collectionName: string;
  embeddingModelDims?: number;
  distanceMetric?: string;
  batchSize?: number;
  partition?: string;
}

export class TopK implements VectorStore {
  private client: Client;
  private collectionName: string;
  private partition?: string;
  private embeddingModelDims: number;
  private distanceMetric: string;
  private batchSize: number;
  private _initPromise?: Promise<void>;
  private _cachedUserId?: string;
  private _lastWriteLsn?: string;

  constructor(config: TopKConfig) {
    const apiKey = config.apiKey || process.env.TOPK_API_KEY;
    if (!apiKey)
      throw new Error("TopK API key must be provided or set via TOPK_API_KEY");

    const region = config.region || process.env.TOPK_REGION;
    if (!region)
      throw new Error("TopK region must be provided or set via TOPK_REGION");

    const host = config.host || process.env.TOPK_HOST;
    const httpsEnv = process.env.TOPK_HTTPS;
    const https =
      config.https !== undefined
        ? config.https
        : httpsEnv !== undefined
          ? httpsEnv.toLowerCase() !== "false" &&
            httpsEnv !== "0" &&
            httpsEnv !== "no"
          : true;

    const clientConfig: ClientConfig = { apiKey, region, https };
    if (host) clientConfig.host = host;

    this.client = new Client(clientConfig);
    this.collectionName = config.collectionName;
    this.partition = config.partition;
    this.embeddingModelDims =
      config.embeddingModelDims || config.dimension || 1536;
    this.distanceMetric = config.distanceMetric || "cosine";
    this.batchSize = config.batchSize || 100;
    this.initialize().catch(console.error);
  }

  private col() {
    return this.client.collection(this.collectionName, this.partition);
  }

  private topkMetric(): string {
    return METRIC_MAP[this.distanceMetric] || "cosine";
  }

  private toSimilarity(raw: number): number {
    // fn.vectorDistance returns: cosine similarity (higher=better), euclidean distance (lower=better), dot product (higher=better)
    if (this.topkMetric() === "euclidean") return 1 / (1 + raw);
    return raw; // cosine or dot_product: already higher = better
  }

  private searchAsc(): boolean {
    return this.topkMetric() === "euclidean";
  }

  private convertFilters(filters: SearchFilters): query.LogicalExpression {
    const conditions = Object.entries(filters).flatMap(([key, value]) => {
      if (
        typeof value === "object" &&
        value !== null &&
        !Array.isArray(value)
      ) {
        return Object.entries(value as Record<string, any>).map(([op, val]) => {
          if (op === "eq") return field(key).eq(val);
          if (op === "ne") return field(key).ne(val);
          if (op === "gt") return field(key).gt(val);
          if (op === "gte") return field(key).gte(val);
          if (op === "lt") return field(key).lt(val);
          if (op === "lte") return field(key).lte(val);
          if (op === "in") return field(key).in(val);
          if (op === "nin") return not(field(key).in(val));
          if (op === "contains") return field(key).contains(val);
          throw new Error(`Unsupported filter operator: '${op}'`);
        });
      }
      return [field(key).eq(value as string | number | boolean | undefined)];
    });
    if (!conditions.length)
      throw new Error("convertFilters called with empty filters");
    return conditions.length === 1
      ? conditions[0]
      : conditions.reduce((a, b) => a.and(b));
  }

  private payloadFrom(doc: Record<string, any>): Record<string, any> {
    return Object.fromEntries(
      Object.entries(doc).filter(
        ([k]) => !["_id", "vector", "score"].includes(k),
      ),
    );
  }

  /**
   * Fields to request from a query. TopK's select() has no wildcard, so we
   * whitelist Mem0's payload fields plus any filter keys — custom metadata is
   * returned only when it is also used as a filter key.
   */
  private selectFields(filters?: SearchFilters): Record<string, any> {
    const exprs: Record<string, any> = {};
    for (const f of MEM0_FIELDS) exprs[f] = field(f);
    for (const k of Object.keys(filters ?? {})) {
      if (!(k in exprs) && !["score", "vector", "_id"].includes(k)) {
        exprs[k] = field(k);
      }
    }
    return exprs;
  }

  private async ensureCollection(
    name: string,
    dims: number,
    metric: string,
  ): Promise<void> {
    try {
      await this.client.collections().create(name, {
        vector: f32Vector({ dimension: dims }).index(
          vectorIndex({ metric: (METRIC_MAP[metric] || "cosine") as any }),
        ),
        textLemmatized: text().index(keywordIndex()),
      });
    } catch (e: any) {
      if (!e?.message?.includes("already exists")) throw e;
    }
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this.ensureCollection(
        this.collectionName,
        this.embeddingModelDims,
        this.distanceMetric,
      ).catch((e) => {
        // Clear the memoized promise so a later call can retry instead of
        // replaying the same cached rejection forever.
        this._initPromise = undefined;
        throw e;
      });
    }
    return this._initPromise;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    for (let i = 0; i < vectors.length; i += this.batchSize) {
      const batch = vectors.slice(i, i + this.batchSize).map((vec, j) => ({
        _id: ids[i + j],
        vector: vec,
        ...(payloads?.[i + j] || {}),
      }));
      const lsn = await this.col().upsert(batch);
      if (lsn) this._lastWriteLsn = lsn;
    }
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    let q = select({
      ...this.selectFields(filters),
      score: fn.vectorDistance("vector", query),
    });
    if (filters && Object.keys(filters).length > 0)
      q = q.filter(this.convertFilters(filters));
    const hits = await this.col().query(
      q.topk(field("score"), topK, this.searchAsc()),
      { lsn: this._lastWriteLsn },
    );
    return hits.map((h) => ({
      id: String(h._id),
      score: this.toSimilarity(h.score as number),
      payload: this.payloadFrom(h),
    }));
  }

  async keywordSearch(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    let q = topkFilter(match(query, { field: "textLemmatized" })).select({
      ...this.selectFields(filters),
      score: fn.bm25Score(),
    });
    if (filters && Object.keys(filters).length > 0)
      q = q.filter(this.convertFilters(filters));
    const hits = await this.col().query(q.topk(field("score"), topK, false), {
      lsn: this._lastWriteLsn,
    });
    // BM25 scores are already higher = better; Mem0 core normalizes them itself.
    return hits.map((h) => ({
      id: String(h._id),
      score: h.score as number,
      payload: this.payloadFrom(h),
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    const results = await this.col().get([vectorId], undefined, {
      lsn: this._lastWriteLsn,
    });
    const doc = results?.[vectorId];
    if (!doc) return null;
    return {
      id: vectorId,
      payload: this.payloadFrom(doc as Record<string, any>),
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    const doc: Record<string, any> = { _id: vectorId };
    if (vector) doc.vector = vector;
    if (payload) Object.assign(doc, payload);
    const lsn = await this.col().upsert([doc]);
    if (lsn) this._lastWriteLsn = lsn;
  }

  async delete(vectorId: string): Promise<void> {
    const lsn = await this.col().delete([vectorId]);
    if (lsn) this._lastWriteLsn = lsn;
  }

  async deleteCol(): Promise<void> {
    try {
      if (this.partition) {
        await this.col().deletePartition(this.partition);
      } else {
        await this.client.collections().delete(this.collectionName);
      }
    } catch (e: any) {
      if (!e?.message?.includes("not found")) throw e;
    }
    this._lastWriteLsn = undefined;
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    let q = select(this.selectFields(filters));
    if (filters && Object.keys(filters).length > 0)
      q = q.filter(this.convertFilters(filters));
    const hits = await this.col().query(q.limit(topK), {
      lsn: this._lastWriteLsn,
    });
    const items: VectorStoreResult[] = hits.map((h) => ({
      id: String(h._id),
      payload: this.payloadFrom(h),
    }));
    return [items, items.length];
  }

  private async ensureMigrationsCollection(): Promise<void> {
    try {
      await this.client.collections().create(MIGRATIONS_COLLECTION_NAME, {
        user_id: text().required(),
      });
    } catch (e: any) {
      if (!e?.message?.includes("already exists")) throw e;
    }
  }

  async getUserId(): Promise<string> {
    if (this._cachedUserId) return this._cachedUserId;
    await this.ensureMigrationsCollection();
    const results = await this.client
      .collection(MIGRATIONS_COLLECTION_NAME)
      .get(["user_id_record"]);
    const doc = results?.["user_id_record"] as Record<string, any> | undefined;
    if (doc?.user_id) {
      this._cachedUserId = doc.user_id as string;
      return this._cachedUserId;
    }
    const userId = generateRandomUserId();
    await this.client
      .collection(MIGRATIONS_COLLECTION_NAME)
      .upsert([{ _id: "user_id_record", user_id: userId }]);
    this._cachedUserId = userId;
    return userId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.ensureMigrationsCollection();
    await this.client
      .collection(MIGRATIONS_COLLECTION_NAME)
      .upsert([{ _id: "user_id_record", user_id: userId }]);
    this._cachedUserId = userId;
  }
}
