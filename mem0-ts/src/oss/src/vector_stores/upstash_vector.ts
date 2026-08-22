import type { Index, QueryResult, Vector } from "@upstash/vector";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";
import { loadPeer } from "../utils/load_peer";

interface UpstashVectorConfig extends VectorStoreConfig {
  collectionName: string;
  url?: string;
  token?: string;
  /** Pre-configured Upstash Vector client instance (typed as `any` to keep
   *  the optional driver's types out of the published type declarations). */
  client?: any;
}

type UpstashMetadata = Record<string, unknown>;

export class UpstashVector implements VectorStore {
  private client!: Index<UpstashMetadata>;
  private readonly config: UpstashVectorConfig;
  private readonly collectionName: string;

  constructor(config: UpstashVectorConfig) {
    if (!config.collectionName) {
      throw new Error("collectionName is required for Upstash Vector.");
    }
    if (!config.client && !(config.url && config.token)) {
      throw new Error("Either a client or url and token must be provided.");
    }

    this.config = config;
    this.collectionName = config.collectionName;
  }

  /**
   * Lazily construct (or reuse) the Upstash Vector client, importing the
   * optional `@upstash/vector` peer only when the store is first used so
   * consumers that never touch Upstash Vector don't need it installed.
   */
  private async ensureClient(): Promise<void> {
    if (this.client) return;

    const config = this.config;
    if (config.client) {
      this.client = config.client;
    } else {
      const sdk = await loadPeer(
        "@upstash/vector",
        "Upstash Vector store",
        () => import("@upstash/vector"),
      );
      this.client = new sdk.Index({
        url: config.url,
        token: config.token,
      });
    }
  }

  async initialize(): Promise<void> {
    await this.ensureClient();
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();
    const upsertData = vectors.map((vector, idx) => {
      return {
        id: ids[idx],
        vector,
        metadata: payloads[idx] ?? {},
      };
    });

    await this.client.upsert(upsertData, { namespace: this.collectionName });
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();
    const response = await this.client.query<UpstashMetadata>(
      {
        vector: query,
        topK,
        filter: this.convertFilters(filters),
        includeMetadata: true,
      },
      { namespace: this.collectionName },
    );

    return response.map((result) => this.parseResult(result));
  }

  async keywordSearch(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    await this.initialize();
    try {
      const response = await this.client.query<UpstashMetadata>(
        {
          data: query,
          topK,
          filter: this.convertFilters(filters),
          includeMetadata: true,
        },
        { namespace: this.collectionName },
      );

      return response.map((result) => this.parseResult(result));
    } catch (error) {
      console.error(`Error during keyword search for query '${query}':`, error);
      return null;
    }
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();
    const response = await this.client.fetch<UpstashMetadata>([vectorId], {
      includeMetadata: true,
      namespace: this.collectionName,
    });
    const vector = response[0];

    if (!vector) {
      return null;
    }

    return {
      id: String(vector.id),
      payload: (vector.metadata ?? {}) as Record<string, any>,
    };
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();
    // Upstash's `update` can't set the vector and metadata in one call (its
    // payload is a discriminated union of vector | data | metadata), so a
    // single `upsert` replaces both atomically, the same way insert() writes.
    await this.client.upsert(
      {
        id: vectorId,
        vector,
        metadata: payload,
      },
      { namespace: this.collectionName },
    );
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();
    await this.client.delete(vectorId, { namespace: this.collectionName });
  }

  async deleteCol(): Promise<void> {
    await this.initialize();
    await this.client.reset({ namespace: this.collectionName });
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();
    const results: VectorStoreResult[] = [];
    let cursor = "0";

    do {
      const response = await this.client.range<UpstashMetadata>(
        {
          cursor,
          limit: Math.min(100, topK - results.length),
          includeMetadata: true,
        },
        { namespace: this.collectionName },
      );

      for (const vector of response.vectors) {
        if (this.matchesFilters(vector, filters)) {
          results.push({
            id: String(vector.id),
            payload: (vector.metadata ?? {}) as Record<string, any>,
          });
        }

        if (results.length >= topK) {
          break;
        }
      }

      cursor = response.nextCursor;
      // Upstash returns an empty-string cursor once the scan is exhausted (it
      // never comes back as "0"), so "" is the termination sentinel. Checking
      // for "0" here would re-scan from the start and return duplicates.
    } while (cursor !== "" && results.length < topK);

    return [results, results.length];
  }

  async getUserId(): Promise<string> {
    return "anonymous-upstash-vector";
  }

  async setUserId(): Promise<void> {
    return;
  }

  async reset(): Promise<void> {
    await this.deleteCol();
  }

  private parseResult(result: QueryResult<UpstashMetadata>): VectorStoreResult {
    return {
      id: String(result.id),
      payload: (result.metadata ?? {}) as Record<string, any>,
      score: result.score,
    };
  }

  private stringifyFilterValue(value: unknown): string {
    if (typeof value === "string") {
      return JSON.stringify(value);
    }

    if (typeof value === "boolean") {
      return value ? "true" : "false";
    }

    return String(value);
  }

  private convertFilters(filters?: SearchFilters): string | undefined {
    if (!filters) {
      return undefined;
    }

    const clauses: string[] = [];
    for (const [key, value] of Object.entries(filters)) {
      if (value === undefined || value === null) continue;
      const clause = this.buildFilterClause(key, value);
      if (clause) clauses.push(clause);
    }
    return clauses.length > 0 ? clauses.join(" AND ") : undefined;
  }

  // mem0's universal comparison operators -> Upstash filter tokens.
  private static readonly COMPARATORS: Record<string, string> = {
    eq: "=",
    ne: "!=",
    gt: ">",
    gte: ">=",
    lt: "<",
    lte: "<=",
  };

  /**
   * Translate a single field condition into Upstash filter syntax. Handles the
   * operator dicts, "in" arrays and "*" wildcard that mem0 supports — the old
   * version only emitted `key = value`, so anything else serialized to
   * `key = [object Object]` and Upstash rejected the query.
   */
  private buildFilterClause(key: string, value: any): string | undefined {
    // "*" means "the field must exist".
    if (value === "*") return `HAS FIELD ${key}`;

    // Array shorthand -> IN.
    if (Array.isArray(value)) {
      return `${key} IN (${value.map((v) => this.stringifyFilterValue(v)).join(", ")})`;
    }

    // Operator dict, e.g. { gte: 18, lte: 65 } — apply EVERY operator (AND).
    if (typeof value === "object") {
      const parts: string[] = [];
      for (const [op, opValue] of Object.entries(value)) {
        const comparator = UpstashVector.COMPARATORS[op];
        if (comparator) {
          parts.push(
            `${key} ${comparator} ${this.stringifyFilterValue(opValue)}`,
          );
        } else if (op === "in" && Array.isArray(opValue)) {
          parts.push(
            `${key} IN (${opValue.map((v) => this.stringifyFilterValue(v)).join(", ")})`,
          );
        } else if (op === "nin" && Array.isArray(opValue)) {
          parts.push(
            `${key} NOT IN (${opValue.map((v) => this.stringifyFilterValue(v)).join(", ")})`,
          );
        } else {
          throw new Error(this.unsupportedOperatorMessage(op, key));
        }
      }
      return parts.length > 0 ? parts.join(" AND ") : undefined;
    }

    // Scalar equality.
    return `${key} = ${this.stringifyFilterValue(value)}`;
  }

  private unsupportedOperatorMessage(op: string, key: string): string {
    return (
      `Unsupported Upstash filter operator '${op}' for field '${key}'. ` +
      `Supported operators: ${Object.keys(UpstashVector.COMPARATORS).join(", ")}, in, nin.`
    );
  }

  private matchesFilters(
    vector: Vector<UpstashMetadata>,
    filters?: SearchFilters,
  ): boolean {
    if (!filters) {
      return true;
    }

    return Object.entries(filters).every(([key, value]) => {
      if (value === undefined || value === null) {
        return true;
      }
      return this.matchesFieldCondition(vector.metadata ?? {}, key, value);
    });
  }

  /** Client-side equivalent of buildFilterClause, applying every operator. */
  private matchesFieldCondition(
    metadata: Record<string, any>,
    key: string,
    value: any,
  ): boolean {
    const fieldValue = metadata[key];

    if (value === "*") return key in metadata;
    if (Array.isArray(value)) return value.includes(fieldValue);

    if (value && typeof value === "object") {
      return Object.entries(value).every(([op, opValue]) => {
        switch (op) {
          case "eq":
            return fieldValue === opValue;
          case "ne":
            return fieldValue !== opValue;
          case "gt":
            return fieldValue > (opValue as any);
          case "gte":
            return fieldValue >= (opValue as any);
          case "lt":
            return fieldValue < (opValue as any);
          case "lte":
            return fieldValue <= (opValue as any);
          case "in":
            return Array.isArray(opValue) && opValue.includes(fieldValue);
          case "nin":
            return !Array.isArray(opValue) || !opValue.includes(fieldValue);
          default:
            throw new Error(this.unsupportedOperatorMessage(op, key));
        }
      });
    }

    return fieldValue === value;
  }
}
