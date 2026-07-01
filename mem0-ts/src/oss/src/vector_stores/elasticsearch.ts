import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface ElasticsearchConfig extends VectorStoreConfig {
  host?: string;
  port?: number;
  user?: string;
  username?: string;
  password?: string;
  apiKey?: string;
  collectionName: string;
  embeddingModelDims?: number;
  dimension?: number;
  scheme?: "http" | "https";
  autoCreateIndex?: boolean;
  customSearchQuery?: (
    query: number[],
    limit: number,
    filters?: SearchFilters,
  ) => Record<string, any>;
}

type RequestOptions = {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
};

export class ElasticsearchDB implements VectorStore {
  private readonly collectionName: string;
  private readonly dimension: number;
  private readonly baseUrl: string;
  private readonly user?: string;
  private readonly password?: string;
  private readonly apiKey?: string;
  private readonly autoCreateIndex: boolean;
  private readonly customSearchQuery?: ElasticsearchConfig["customSearchQuery"];
  private _initPromise?: Promise<void>;

  constructor(config: ElasticsearchConfig) {
    this.collectionName = config.collectionName || "memories";
    this.dimension =
      config.dimension ||
      config.embeddingModelDims ||
      config.embedding_model_dims ||
      1536;
    this.user = config.user || config.username;
    this.password = config.password;
    this.apiKey = config.apiKey || config.api_key;
    this.autoCreateIndex =
      config.autoCreateIndex ?? config.auto_create_index ?? true;
    this.customSearchQuery =
      config.customSearchQuery || config.custom_search_query;
    this.baseUrl = this.buildBaseUrl(config);

    this.initialize().catch(console.error);
  }

  private buildBaseUrl(config: ElasticsearchConfig): string {
    const host = config.host || "localhost";
    const hasScheme = host.startsWith("http://") || host.startsWith("https://");
    const scheme = hasScheme ? "" : `${config.scheme || "http"}://`;
    const hostWithoutScheme = host.replace(/^https?:\/\//, "");
    const hasPort = /:\d+$/.test(hostWithoutScheme);
    const port = config.port && !hasPort ? `:${config.port}` : "";
    return `${scheme}${host}${port}`.replace(/\/$/, "");
  }

  private headers(extra: Record<string, string> = {}): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...extra,
    };

    if (this.apiKey) {
      headers.Authorization = `ApiKey ${this.apiKey}`;
    } else if (this.user || this.password) {
      headers.Authorization = `Basic ${Buffer.from(
        `${this.user || ""}:${this.password || ""}`,
      ).toString("base64")}`;
    }

    return headers;
  }

  private async request(path: string, options: RequestOptions = {}): Promise<any> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers: this.headers(options.headers || {}),
    });
    const text = await response.text();

    if (!response.ok) {
      throw new Error(`Elasticsearch ${response.status}: ${text}`);
    }

    return text ? JSON.parse(text) : {};
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this.doInitialize();
    }
    return this._initPromise;
  }

  private async doInitialize(): Promise<void> {
    if (this.autoCreateIndex) {
      await this.ensureCollection(this.collectionName, this.dimension);
      await this.ensureCollection("memory_migrations", 1, false);
    }
  }

  private async indexExists(name: string): Promise<boolean> {
    const response = await fetch(`${this.baseUrl}/${encodeURIComponent(name)}`, {
      method: "HEAD",
      headers: this.headers(),
    });

    if (response.status === 200) return true;
    if (response.status === 404) return false;
    throw new Error(`Elasticsearch HEAD ${name} failed with ${response.status}`);
  }

  private async ensureCollection(
    name: string,
    dimension: number,
    withVector: boolean = true,
  ): Promise<void> {
    if (await this.indexExists(name)) return;

    const properties: Record<string, any> = withVector
      ? {
          vector: {
            type: "dense_vector",
            dims: dimension,
            index: true,
            similarity: "cosine",
          },
          payload: { type: "object", enabled: true },
          user_id: { type: "keyword" },
          agent_id: { type: "keyword" },
          run_id: { type: "keyword" },
        }
      : { user_id: { type: "keyword" } };

    await this.request(`/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify({ mappings: { properties } }),
    });
  }

  private filterClauses(filters?: SearchFilters): Record<string, any>[] {
    if (!filters) return [];

    return Object.entries(filters).flatMap(([key, value]) => {
      if (value === undefined || value === null || value === "*") return [];
      if (["user_id", "agent_id", "run_id"].includes(key)) {
        return [{ term: { [key]: value } }];
      }
      return [{ term: { [`payload.${key}.keyword`]: value } }];
    });
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();

    const body =
      vectors
        .flatMap((vector, index) => {
          const payload = payloads[index] || {};
          return [
            JSON.stringify({
              index: { _index: this.collectionName, _id: ids[index] },
            }),
            JSON.stringify({
              vector,
              payload,
              user_id: payload.user_id,
              agent_id: payload.agent_id,
              run_id: payload.run_id,
            }),
          ];
        })
        .join("\n") + "\n";

    const response = await fetch(`${this.baseUrl}/_bulk?refresh=true`, {
      method: "POST",
      headers: this.headers({ "Content-Type": "application/x-ndjson" }),
      body,
    });
    const result = await response.json();

    if (!response.ok || result.errors) {
      throw new Error(`Elasticsearch bulk insert failed: ${JSON.stringify(result)}`);
    }
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();

    const filter = this.filterClauses(filters);
    const body = this.customSearchQuery
      ? this.customSearchQuery(query, topK, filters)
      : {
          size: topK,
          knn: {
            field: "vector",
            query_vector: query,
            k: topK,
            num_candidates: Math.max(100, topK * 10),
            ...(filter.length > 0 ? { filter } : {}),
          },
        };

    const result = await this.request(
      `/${encodeURIComponent(this.collectionName)}/_search`,
      { method: "POST", body: JSON.stringify(body) },
    );

    return (result.hits?.hits || []).map((hit: any) => ({
      id: hit._id,
      payload: hit._source?.payload || {},
      score: hit._score,
    }));
  }

  async keywordSearch(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    await this.initialize();

    const filter = this.filterClauses(filters);
    const body = {
      size: topK,
      query: {
        bool: {
          must: [{ match: { "payload.textLemmatized": query } }, ...filter],
        },
      },
    };

    const result = await this.request(
      `/${encodeURIComponent(this.collectionName)}/_search`,
      { method: "POST", body: JSON.stringify(body) },
    );

    return (result.hits?.hits || []).map((hit: any) => ({
      id: hit._id,
      payload: hit._source?.payload || {},
      score: hit._score,
    }));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();

    try {
      const result = await this.request(
        `/${encodeURIComponent(this.collectionName)}/_doc/${encodeURIComponent(vectorId)}`,
      );
      return { id: vectorId, payload: result._source?.payload || {} };
    } catch (error) {
      if (String(error).includes("Elasticsearch 404")) return null;
      throw error;
    }
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();

    await this.request(
      `/${encodeURIComponent(this.collectionName)}/_doc/${encodeURIComponent(vectorId)}?refresh=true`,
      {
        method: "PUT",
        body: JSON.stringify({
          vector,
          payload,
          user_id: payload.user_id,
          agent_id: payload.agent_id,
          run_id: payload.run_id,
        }),
      },
    );
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();
    await this.request(
      `/${encodeURIComponent(this.collectionName)}/_doc/${encodeURIComponent(vectorId)}?refresh=true`,
      { method: "DELETE" },
    );
  }

  async deleteCol(): Promise<void> {
    await this.request(`/${encodeURIComponent(this.collectionName)}`, {
      method: "DELETE",
    });
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();

    const filter = this.filterClauses(filters);
    const body = {
      size: topK,
      query: filter.length > 0 ? { bool: { filter } } : { match_all: {} },
    };
    const result = await this.request(
      `/${encodeURIComponent(this.collectionName)}/_search`,
      { method: "POST", body: JSON.stringify(body) },
    );
    const rows = (result.hits?.hits || []).map((hit: any) => ({
      id: hit._id,
      payload: hit._source?.payload || {},
    }));
    return [rows, result.hits?.total?.value ?? rows.length];
  }

  private generateUUID(): string {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      const v = c === "x" ? r : (r & 0x3) | 0x8;
      return v.toString(16);
    });
  }

  async getUserId(): Promise<string> {
    await this.ensureCollection("memory_migrations", 1, false);

    const result = await this.request("/memory_migrations/_search", {
      method: "POST",
      body: JSON.stringify({ size: 1, query: { match_all: {} } }),
    });
    const hit = result.hits?.hits?.[0];
    if (hit?._source?.user_id) return hit._source.user_id;

    const userId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);
    await this.request(`/memory_migrations/_doc/${this.generateUUID()}?refresh=true`, {
      method: "PUT",
      body: JSON.stringify({ user_id: userId }),
    });
    return userId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.ensureCollection("memory_migrations", 1, false);
    await this.request("/memory_migrations/_delete_by_query?refresh=true", {
      method: "POST",
      body: JSON.stringify({ query: { match_all: {} } }),
    });
    await this.request(`/memory_migrations/_doc/${this.generateUUID()}?refresh=true`, {
      method: "PUT",
      body: JSON.stringify({ user_id: userId }),
    });
  }
}
