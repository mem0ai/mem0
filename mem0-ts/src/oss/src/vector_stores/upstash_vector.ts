import { Index, QueryResult, Vector } from "@upstash/vector";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface UpstashVectorConfig extends VectorStoreConfig {
  collectionName: string;
  url?: string;
  token?: string;
  client?: Index<Record<string, unknown>>;
  enable_embeddings?: boolean;
}

type UpstashMetadata = Record<string, unknown>;

export class UpstashVector implements VectorStore {
  private readonly client: Index<UpstashMetadata>;
  private readonly collectionName: string;
  private readonly enableEmbeddings: boolean;

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
    this.enableEmbeddings = config.enable_embeddings ?? false;
  }

  async initialize(): Promise<void> {
    return;
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    if (this.enableEmbeddings) {
      const upsertData = vectors.map((_, idx) => {
        const metadata = payloads[idx] ?? {};
        if (metadata.data === undefined || metadata.data === null) {
          throw new Error(
            "When embeddings are enabled, all payloads must contain a 'data' field.",
          );
        }

        return {
          id: ids[idx],
          data: String(metadata.data),
          metadata,
        };
      });

      await this.client.upsert(upsertData, { namespace: this.collectionName });
      return;
    }

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
    query: number[] | string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const filter = this.convertFilters(filters);
    const queryParams = this.enableEmbeddings
      ? {
          data: String(query),
          topK,
          filter,
          includeMetadata: true,
        }
      : {
          vector: query as number[],
          topK,
          filter,
          includeMetadata: true,
        };

    const response = await this.client.query<UpstashMetadata>(queryParams, {
      namespace: this.collectionName,
    });

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
    if (this.enableEmbeddings) {
      if (payload.data === undefined || payload.data === null) {
        throw new Error(
          "When embeddings are enabled, payload must contain a 'data' field.",
        );
      }

      await this.client.update(
        {
          id: vectorId,
          data: String(payload.data),
        },
        { namespace: this.collectionName },
      );
    } else {
      await this.client.update(
        {
          id: vectorId,
          vector,
        },
        { namespace: this.collectionName },
      );
    }

    await this.client.update<UpstashMetadata>(
      {
        id: vectorId,
        metadata: payload,
        metadataUpdateMode: "OVERWRITE",
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
    } while (cursor !== "0" && results.length < topK);

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
