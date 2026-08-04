import fs from "fs";
import os from "os";
import path from "path";
import { randomUUID } from "crypto";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

type DistanceStrategy = "euclidean" | "inner_product" | "cosine";

interface FaissSearchResult {
  labels: ArrayLike<number | bigint>;
  distances: ArrayLike<number>;
}

export interface FaissIndexLike {
  add(vector: number[] | Float32Array): void | Promise<void>;
  search(
    vector: number[] | Float32Array,
    topK: number,
  ): FaissSearchResult | Promise<FaissSearchResult>;
  write?(filePath: string): void | Promise<void>;
  toBuffer?(): Buffer | Uint8Array | ArrayBuffer;
}

export interface FaissIndexConstructor {
  new (dimension: number): FaissIndexLike;
}

export interface FaissBinding {
  IndexFlatL2: FaissIndexConstructor;
  IndexFlatIP: FaissIndexConstructor;
}

export interface FAISSConfig extends VectorStoreConfig {
  collectionName?: string;
  path?: string;
  distanceStrategy?: DistanceStrategy;
  normalizeL2?: boolean;
  embeddingModelDims?: number;
  binding?: FaissBinding;
  faissLib?: FaissBinding;
}

interface StoredRecord {
  id: string;
  vector: number[];
  payload: Record<string, any>;
}

interface PersistedState {
  collectionName: string;
  distanceStrategy: DistanceStrategy;
  normalizeL2: boolean;
  embeddingModelDims: number;
  userId: string;
  records: StoredRecord[];
}

const CAMEL_TO_SNAKE: Record<string, string> = {
  userId: "user_id",
  agentId: "agent_id",
  runId: "run_id",
};

const LOGICAL_KEYS = new Set(["AND", "OR", "NOT", "$and", "$or", "$not"]);
const FILTER_OPERATORS = new Set([
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
]);

function cloneValue<T>(value: T): T {
  if (typeof structuredClone === "function") {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
}

function l2Normalize(vector: number[]): number[] {
  const norm = Math.sqrt(vector.reduce((sum, value) => sum + value * value, 0));
  if (norm === 0) return [...vector];
  return vector.map((value) => value / norm);
}

function normalizePayload(payload: Record<string, any>): Record<string, any> {
  const normalized = cloneValue(payload);
  for (const [camel, snake] of Object.entries(CAMEL_TO_SNAKE)) {
    if (camel in normalized && !(snake in normalized)) {
      normalized[snake] = normalized[camel];
      delete normalized[camel];
    }
  }
  return normalized;
}

function normalizeFieldKey(key: string): string {
  return CAMEL_TO_SNAKE[key] || key;
}

function cloneRecord(record: StoredRecord): StoredRecord {
  return {
    id: record.id,
    vector: [...record.vector],
    payload: normalizePayload(record.payload),
  };
}

export class FAISSDB implements VectorStore {
  private readonly collectionName: string;
  private readonly distanceStrategy: DistanceStrategy;
  private readonly normalizeL2: boolean;
  private readonly dimension: number;
  private readonly basePath: string;
  private readonly indexPath: string;
  private readonly metadataPath: string;
  private readonly binding: FaissBinding;
  private readonly indexCtor: FaissIndexConstructor;
  private index: FaissIndexLike;
  private records: StoredRecord[] = [];
  private userId = "";
  private initPromise?: Promise<void>;

  constructor(config: FAISSConfig) {
    this.collectionName = config.collectionName || "mem0";
    this.distanceStrategy = this.normalizeDistanceStrategy(
      config.distanceStrategy || "euclidean",
    );
    this.normalizeL2 = config.normalizeL2 ?? false;
    this.dimension = Math.floor(
      config.embeddingModelDims ?? config.dimension ?? 1536,
    );
    if (this.dimension <= 0) {
      throw new Error("FAISS embeddingModelDims must be a positive integer");
    }

    this.basePath = path.resolve(
      config.path ||
        config.dbPath ||
        path.join(os.tmpdir(), "faiss", this.collectionName),
    );
    this.indexPath = path.join(this.basePath, `${this.collectionName}.faiss`);
    this.metadataPath = path.join(this.basePath, `${this.collectionName}.json`);
    this.binding = config.binding || config.faissLib || this.loadFaissBinding();
    this.indexCtor = this.resolveIndexCtor();
    this.index = this.createIndex();

    this.initialize().catch(console.error);
  }

  private normalizeDistanceStrategy(strategy: string): DistanceStrategy {
    const value = strategy.toLowerCase();
    if (
      value !== "euclidean" &&
      value !== "inner_product" &&
      value !== "cosine"
    ) {
      throw new Error(
        `Unsupported FAISS distance strategy: ${strategy}. Use euclidean, inner_product, or cosine.`,
      );
    }
    return value;
  }

  private loadFaissBinding(): FaissBinding {
    try {
      // Lazy native resolution keeps the package importable without faiss-node.
      return require("faiss-node") as FaissBinding;
    } catch {
      throw new Error(
        "FAISS provider requires the optional faiss-node dependency. Install it with `pnpm add faiss-node` and try again.",
      );
    }
  }

  private resolveIndexCtor(): FaissIndexConstructor {
    return this.distanceStrategy === "inner_product" ||
      this.distanceStrategy === "cosine"
      ? this.binding.IndexFlatIP
      : this.binding.IndexFlatL2;
  }

  private createIndex(): FaissIndexLike {
    return new this.indexCtor(this.dimension);
  }

  private prepareVector(vector: number[]): number[] {
    if (this.distanceStrategy === "cosine") {
      return l2Normalize(vector);
    }
    if (this.distanceStrategy === "euclidean" && this.normalizeL2) {
      return l2Normalize(vector);
    }
    return [...vector];
  }

  private validateVector(vector: number[], context: string): void {
    if (vector.length !== this.dimension) {
      throw new Error(
        `${context} dimension mismatch. Expected ${this.dimension}, got ${vector.length}`,
      );
    }
  }

  private recordIndex(vectorId: string): number {
    return this.records.findIndex((record) => record.id === vectorId);
  }

  private normalizeFilters(
    filters?: SearchFilters,
  ): Record<string, any> | undefined {
    if (!filters || Object.keys(filters).length === 0) {
      return undefined;
    }

    const normalized: Record<string, any> = {};
    for (const [key, value] of Object.entries(filters)) {
      const normalizedKey = normalizeFieldKey(key);
      if (!(normalizedKey in normalized)) {
        normalized[normalizedKey] = value;
      }
    }
    return normalized;
  }

  private matchesFieldCondition(payloadValue: any, value: any): boolean {
    if (value === "*") return true;
    if (Array.isArray(value)) {
      return value.some((entry) => entry === payloadValue);
    }
    if (typeof value !== "object" || value === null) {
      return payloadValue === value;
    }

    const operators = Object.entries(value);
    if (operators.length === 0) return true;
    return operators.every(([operator, operand]) =>
      this.matchesOperator(payloadValue, operator, operand),
    );
  }

  private matchesOperator(
    payloadValue: any,
    operator: string,
    operand: any,
  ): boolean {
    if (!FILTER_OPERATORS.has(operator)) {
      throw new Error(`Unsupported filter operator: ${operator}`);
    }

    switch (operator) {
      case "eq":
        return payloadValue === operand;
      case "ne":
        return payloadValue !== operand;
      case "gt":
        return payloadValue > operand;
      case "gte":
        return payloadValue >= operand;
      case "lt":
        return payloadValue < operand;
      case "lte":
        return payloadValue <= operand;
      case "in":
        return (
          Array.isArray(operand) &&
          operand.some((entry) => entry === payloadValue)
        );
      case "nin":
        return (
          !Array.isArray(operand) ||
          !operand.some((entry) => entry === payloadValue)
        );
      case "contains":
        return (
          typeof payloadValue === "string" &&
          payloadValue.includes(String(operand))
        );
      case "icontains":
        return (
          typeof payloadValue === "string" &&
          payloadValue.toLowerCase().includes(String(operand).toLowerCase())
        );
      default:
        return false;
    }
  }

  private matchesFilters(
    payload: Record<string, any>,
    filters?: SearchFilters,
  ): boolean {
    const normalized = this.normalizeFilters(filters);
    if (!normalized) return true;

    for (const [key, value] of Object.entries(normalized)) {
      if (LOGICAL_KEYS.has(key)) {
        if (!Array.isArray(value)) {
          throw new Error(`${key} filter value must be an array.`);
        }

        if (key === "AND" || key === "$and") {
          if (
            !value.every((subFilter) => this.matchesFilters(payload, subFilter))
          ) {
            return false;
          }
          continue;
        }

        if (key === "OR" || key === "$or") {
          if (
            !value.some((subFilter) => this.matchesFilters(payload, subFilter))
          ) {
            return false;
          }
          continue;
        }

        if (key === "NOT" || key === "$not") {
          if (
            !value.every(
              (subFilter) => !this.matchesFilters(payload, subFilter),
            )
          ) {
            return false;
          }
          continue;
        }
      }

      if (!this.matchesFieldCondition(payload[key], value)) {
        return false;
      }
    }

    return true;
  }

  private buildPersistedState(): PersistedState {
    return {
      collectionName: this.collectionName,
      distanceStrategy: this.distanceStrategy,
      normalizeL2: this.normalizeL2,
      embeddingModelDims: this.dimension,
      userId: this.userId,
      records: this.records.map(cloneRecord),
    };
  }

  private readPersistedState(): PersistedState | null {
    if (!fs.existsSync(this.metadataPath)) {
      return null;
    }

    const parsed = JSON.parse(fs.readFileSync(this.metadataPath, "utf8")) as
      | Partial<PersistedState>
      | undefined;

    return {
      collectionName: parsed?.collectionName || this.collectionName,
      distanceStrategy: this.distanceStrategy,
      normalizeL2: this.normalizeL2,
      embeddingModelDims: this.dimension,
      userId: parsed?.userId || "",
      records: Array.isArray(parsed?.records)
        ? parsed!.records.map((record: any) => ({
            id: String(record.id),
            vector: Array.isArray(record.vector)
              ? record.vector.map((value: any) => Number(value))
              : [],
            payload: normalizePayload(record.payload || {}),
          }))
        : [],
    };
  }

  private async persistState(): Promise<void> {
    fs.mkdirSync(this.basePath, { recursive: true });
    fs.writeFileSync(
      this.metadataPath,
      JSON.stringify(this.buildPersistedState(), null, 2),
      "utf8",
    );

    if (typeof this.index.write === "function") {
      await Promise.resolve(this.index.write(this.indexPath));
      return;
    }

    if (typeof this.index.toBuffer === "function") {
      const buffer = this.index.toBuffer();
      fs.writeFileSync(this.indexPath, Buffer.from(buffer));
    }
  }

  private async rebuildIndexFromRecords(): Promise<void> {
    this.index = this.createIndex();

    for (const record of this.records) {
      await Promise.resolve(this.index.add(this.prepareVector(record.vector)));
    }

    await this.persistState();
  }

  async initialize(): Promise<void> {
    if (!this.initPromise) {
      this.initPromise = this.doInitialize();
    }
    return this.initPromise;
  }

  private async doInitialize(): Promise<void> {
    fs.mkdirSync(this.basePath, { recursive: true });
    const persisted = this.readPersistedState();

    if (!persisted) {
      this.records = [];
      this.userId = "";
      this.index = this.createIndex();
      await this.persistState();
      return;
    }

    this.records = persisted.records.map(cloneRecord);
    this.userId = persisted.userId;
    await this.rebuildIndexFromRecords();
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();

    if (vectors.length !== ids.length || vectors.length !== payloads.length) {
      throw new Error("Vectors, ids, and payloads must have the same length");
    }

    for (let i = 0; i < vectors.length; i += 1) {
      this.validateVector(vectors[i], "Vector");
      const record = {
        id: ids[i],
        vector: [...vectors[i]],
        payload: normalizePayload(payloads[i] || {}),
      };
      const existingIndex = this.recordIndex(record.id);
      if (existingIndex >= 0) {
        this.records[existingIndex] = record;
      } else {
        this.records.push(record);
      }
    }

    await this.rebuildIndexFromRecords();
  }

  async search(
    query: number[],
    topK: number = 10,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();
    this.validateVector(query, "Query");

    if (this.records.length === 0) {
      return [];
    }

    const searchVector = this.prepareVector(query);
    const searchTopK = filters
      ? this.records.length
      : Math.min(topK, this.records.length);
    const rawResults = await Promise.resolve(
      this.index.search(searchVector, Math.max(searchTopK, 1)),
    );

    const results: VectorStoreResult[] = [];
    for (let i = 0; i < rawResults.labels.length; i += 1) {
      const rawLabel = rawResults.labels[i];
      const label =
        typeof rawLabel === "bigint" ? Number(rawLabel) : Number(rawLabel);
      if (label < 0) continue;
      const record = this.records[label];
      if (!record) continue;
      if (!this.matchesFilters(record.payload, filters)) continue;

      const rawScore = Number(rawResults.distances[i]);
      const score =
        this.distanceStrategy === "euclidean" ? 1 / (1 + rawScore) : rawScore;

      results.push({
        id: record.id,
        payload: normalizePayload(record.payload),
        score,
      });

      if (results.length >= topK) {
        break;
      }
    }

    return results;
  }

  async keywordSearch(): Promise<null> {
    return null;
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();
    const record = this.records[this.recordIndex(vectorId)];
    if (!record) return null;

    return {
      id: record.id,
      payload: normalizePayload(record.payload),
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();
    this.validateVector(vector, "Vector");

    const existingIndex = this.recordIndex(vectorId);
    if (existingIndex < 0) {
      throw new Error(`Vector ${vectorId} not found`);
    }

    this.records[existingIndex] = {
      id: vectorId,
      vector: [...vector],
      payload: normalizePayload(payload || {}),
    };

    await this.rebuildIndexFromRecords();
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();
    const nextRecords = this.records.filter((record) => record.id !== vectorId);
    if (nextRecords.length === this.records.length) {
      return;
    }

    this.records = nextRecords;
    await this.rebuildIndexFromRecords();
  }

  async deleteCol(): Promise<void> {
    await this.initialize();
    this.records = [];
    this.userId = "";
    this.index = this.createIndex();

    if (fs.existsSync(this.metadataPath)) {
      fs.rmSync(this.metadataPath, { force: true });
    }
    if (fs.existsSync(this.indexPath)) {
      fs.rmSync(this.indexPath, { force: true });
    }
    await this.persistState();
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();

    const matches = this.records
      .filter((record) => this.matchesFilters(record.payload, filters))
      .map((record) => ({
        id: record.id,
        payload: normalizePayload(record.payload),
      }));

    return [matches.slice(0, topK), matches.length];
  }

  async getUserId(): Promise<string> {
    await this.initialize();
    if (!this.userId) {
      this.userId = randomUUID();
      await this.persistState();
    }
    return this.userId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();
    this.userId = userId;
    await this.persistState();
  }
}
