import { Index, QueryResult, Vector } from "@upstash/vector";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface UpstashVectorConfig extends VectorStoreConfig {
  collectionName: string;
  url?: string;
  token?: string;
  client?: Index<Record<string, unknown>>;
}

type UpstashMetadata = Record<string, unknown>;

export class UpstashVector implements VectorStore {
  private readonly client: Index<UpstashMetadata>;
  private readonly collectionName: string;

  constructor(config: UpstashVectorConfig) {
    if (!config.collectionName) {
      throw new Error("collectionName is required for Upstash Vector.");
    }

    if (config.client) {
      this.client = config.client;
    } else if (config.url && config.token) {
      this.client = new Index({
        url: config.url,
        token: config.token,
      });
    } else {
      throw new Error("Either a client or url and token must be provided.");
    }

    this.collectionName = config.collectionName;
  }

  async initialize(): Promise<void> {
    return;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
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
    await this.client.delete(vectorId, { namespace: this.collectionName });
  }

  async deleteCol(): Promise<void> {
    await this.client.reset({ namespace: this.collectionName });
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
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

    const expressions = Object.entries(filters)
      .filter(([, value]) => value !== undefined && value !== null)
      .map(([key, value]) => `${key} = ${this.stringifyFilterValue(value)}`);

    return expressions.length > 0 ? expressions.join(" AND ") : undefined;
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

      return vector.metadata?.[key] === value;
    });
  }
}
