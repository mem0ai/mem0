import type { Client } from "@opensearch-project/opensearch";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

type OpenSearchAuth =
  | {
      username?: string;
      password?: string;
    }
  | {
      user?: string;
      password?: string;
    }
  | Record<string, any>;

interface OpenSearchConfig extends VectorStoreConfig {
  /** Pre-configured OpenSearch client instance (typed as `any` to keep the
   *  optional driver's types out of the published type declarations). */
  client?: any;
  host?: string;
  port?: number;
  httpAuth?: OpenSearchAuth | [string, string];
  user?: string;
  password?: string;
  useSSL?: boolean;
  verifyCerts?: boolean;
  collectionName: string;
  embeddingModelDims: number;
  autoRefresh?: boolean;
}

interface OpenSearchHit {
  _id?: string;
  _score?: number;
  _source?: {
    id?: string;
    vector_field?: number[];
    payload?: Record<string, any>;
  };
}

const KEY_MAP: Record<string, string> = {
  $and: "AND",
  $or: "OR",
  $not: "NOT",
};

function responseBody<T>(response: T | { body: T }): T {
  if (
    response &&
    typeof response === "object" &&
    "body" in response &&
    (response as { body: T }).body !== undefined
  ) {
    return (response as { body: T }).body;
  }

  return response as T;
}

function escapeWildcard(value: string): string {
  return value.replace(/([\\*?])/g, "\\$1");
}

export class OpenSearchDB implements VectorStore {
  private client!: Client;
  private readonly config: OpenSearchConfig;
  private readonly collectionName: string;
  private readonly embeddingModelDims: number;
  private readonly autoRefresh: boolean;
  private _initPromise?: Promise<void>;

  constructor(config: OpenSearchConfig) {
    this.config = config;
    this.collectionName = config.collectionName;
    this.embeddingModelDims = config.embeddingModelDims;
    this.autoRefresh = config.autoRefresh ?? false;

    this.initialize().catch(console.error);
  }

  // The client is created lazily on first initialize() so the optional
  // `@opensearch-project/opensearch` peer is only loaded when the store is
  // actually used.
  private async ensureClient(): Promise<void> {
    if (this.client) return;

    const config = this.config;
    if (config.client) {
      this.client = config.client;
    } else {
      const useSSL = config.useSSL ?? false;
      const host = config.host || "localhost";
      const port = config.port || 9200;
      const auth =
        config.httpAuth ||
        (config.user && config.password
          ? { username: config.user, password: config.password }
          : undefined);

      let sdk: any;
      try {
        sdk = await import("@opensearch-project/opensearch");
      } catch {
        throw new Error(
          "The '@opensearch-project/opensearch' package is required to use the OpenSearch vector store. Install it with: npm install @opensearch-project/opensearch",
        );
      }

      this.client = new sdk.Client({
        node: `${useSSL ? "https" : "http"}://${host}:${port}`,
        auth: this.normalizeAuth(auth),
        ssl: {
          // Default false to match the Python SDK: self-hosted OpenSearch
          // commonly uses self-signed certs, so verification is opt-in.
          rejectUnauthorized: config.verifyCerts ?? false,
        },
      });
    }
  }

  async initialize(): Promise<void> {
    if (!this._initPromise) {
      this._initPromise = this._doInitialize();
    }

    return this._initPromise;
  }

  private async _doInitialize(): Promise<void> {
    await this.ensureClient();
    await this.createCol(this.collectionName, this.embeddingModelDims);
    await this.ensureMigrationIndex();
  }

  private normalizeAuth(auth?: OpenSearchAuth | [string, string]): any {
    if (!auth) return undefined;

    if (Array.isArray(auth)) {
      return {
        username: auth[0],
        password: auth[1],
      };
    }

    if ("user" in auth && auth.user) {
      const { user, ...rest } = auth;
      return {
        ...rest,
        username: user,
      };
    }

    return auth;
  }

  private async indexExists(index: string): Promise<boolean> {
    const response = await this.client.indices.exists({ index });
    return Boolean(responseBody<boolean>(response));
  }

  private async createCol(name: string, vectorSize: number): Promise<void> {
    if (await this.indexExists(name)) return;

    await this.client.indices.create({
      index: name,
      body: {
        settings: {
          index: {
            knn: true,
          },
        },
        mappings: {
          properties: {
            vector_field: {
              type: "knn_vector",
              dimension: vectorSize,
              method: {
                engine: "nmslib",
                name: "hnsw",
                space_type: "cosinesimil",
              },
            },
            // payload is a dynamic object so that string sub-fields (user_id,
            // agent_id, run_id, and any user metadata) each get an automatic
            // `.keyword` sub-field, which the filter builder queries for exact
            // match term/terms clauses. Mapping these as explicit `keyword`
            // fields would remove the `.keyword` sub-field and make every
            // scoped filter silently match nothing.
            payload: { type: "object" },
            id: { type: "keyword" },
          },
        },
      },
    });
  }

  private async ensureMigrationIndex(): Promise<void> {
    if (await this.indexExists("memory_migrations")) return;

    await this.client.indices.create({
      index: "memory_migrations",
      body: {
        mappings: {
          properties: {
            user_id: { type: "keyword" },
          },
        },
      },
    });
  }

  private validateVector(vector: number[], index: number): void {
    if (!vector) {
      throw new Error(`Vector at index ${index} is null or undefined.`);
    }
    if (vector.length === 0) {
      throw new Error(
        `Vector at index ${index} is empty. Expected dimension ${this.embeddingModelDims}.`,
      );
    }
    if (vector.length !== this.embeddingModelDims) {
      throw new Error(
        `Vector at index ${index} has dimension ${vector.length}, but index ` +
          `'${this.collectionName}' expects dimension ${this.embeddingModelDims}.`,
      );
    }
  }

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    await this.initialize();
    vectors.forEach((vector, index) => this.validateVector(vector, index));

    const operations = vectors.flatMap((vector, index) => {
      const id = ids[index] || String(index);
      return [
        { index: { _index: this.collectionName, _id: id } },
        {
          vector_field: vector,
          payload: payloads[index] || {},
          id,
        },
      ];
    });

    if (operations.length === 0) return;

    const response = responseBody<{ errors?: boolean; items?: any[] }>(
      await this.client.bulk({
        refresh: this.autoRefresh,
        body: operations,
      }),
    );

    if (response.errors) {
      const failedItem = response.items?.find((item) => {
        const action = item.index || item.create || item.update || item.delete;
        return action?.error;
      });

      throw new Error(
        `OpenSearch bulk insert failed: ${JSON.stringify(failedItem)}`,
      );
    }
  }

  async keywordSearch(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    await this.initialize();
    const boolQuery: Record<string, any> = {
      should: [
        { match: { "payload.data": query } },
        { match: { "payload.text_lemmatized": query } },
      ],
      minimum_should_match: 1,
    };

    const filter = this.buildFilterClauses(filters);
    if (filter.length) {
      boolQuery.filter = filter;
    }

    const response = responseBody<{ hits: { hits: OpenSearchHit[] } }>(
      (await this.client.search({
        index: this.collectionName,
        body: {
          size: topK,
          query: { bool: boolQuery },
        },
      })) as any,
    );

    return response.hits.hits.map((hit) => this.hitToResult(hit));
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    await this.initialize();
    const knnQuery = {
      knn: {
        vector_field: {
          vector: query,
          k: topK * 2,
        },
      },
    };

    const filter = this.buildFilterClauses(filters);
    const searchQuery = filter.length
      ? {
          bool: {
            must: knnQuery,
            filter,
          },
        }
      : knnQuery;

    const response = responseBody<{ hits: { hits: OpenSearchHit[] } }>(
      (await this.client.search({
        index: this.collectionName,
        body: {
          size: topK * 2,
          query: searchQuery,
        },
      })) as any,
    );

    return response.hits.hits
      .slice(0, topK)
      .map((hit) => this.hitToResult(hit));
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    await this.initialize();
    try {
      const response = responseBody<{ _source?: OpenSearchHit["_source"] }>(
        await this.client.get({
          index: this.collectionName,
          id: vectorId,
        }),
      );

      if (!response._source) return null;

      return {
        id: response._source.id || vectorId,
        payload: response._source.payload || {},
      };
    } catch (error: any) {
      if (error?.statusCode === 404 || error?.meta?.statusCode === 404) {
        return null;
      }
      throw error;
    }
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.initialize();
    if (vector) {
      this.validateVector(vector, 0);
    }

    await this.client.update({
      index: this.collectionName,
      id: vectorId,
      body: {
        doc: {
          ...(vector && { vector_field: vector }),
          ...(payload && { payload }),
          id: vectorId,
        },
      },
      refresh: this.autoRefresh,
    });
  }

  async delete(vectorId: string): Promise<void> {
    await this.initialize();
    try {
      await this.client.delete({
        index: this.collectionName,
        id: vectorId,
        refresh: this.autoRefresh,
      });
    } catch (error: any) {
      if (error?.statusCode === 404 || error?.meta?.statusCode === 404) {
        return;
      }
      throw error;
    }
  }

  async deleteCol(): Promise<void> {
    await this.initialize();
    if (!(await this.indexExists(this.collectionName))) return;
    await this.client.indices.delete({ index: this.collectionName });
  }

  async list(
    filters?: SearchFilters,
    topK: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    await this.initialize();
    const filter = this.buildFilterClauses(filters);
    const query = filter.length ? { bool: { filter } } : { match_all: {} };

    const response = responseBody<{
      hits: {
        total?: number | { value: number };
        hits: OpenSearchHit[];
      };
    }>(
      (await this.client.search({
        index: this.collectionName,
        body: {
          size: topK,
          query,
        },
      })) as any,
    );

    const results = response.hits.hits.map((hit) => this.hitToResult(hit));
    const total =
      typeof response.hits.total === "number"
        ? response.hits.total
        : response.hits.total?.value || results.length;

    return [results, total];
  }

  async reset(): Promise<void> {
    await this.initialize();
    await this.deleteCol();
    await this.createCol(this.collectionName, this.embeddingModelDims);
  }

  async getUserId(): Promise<string> {
    await this.initialize();
    await this.ensureMigrationIndex();

    const response = responseBody<{ hits: { hits: OpenSearchHit[] } }>(
      (await this.client.search({
        index: "memory_migrations",
        body: {
          size: 1,
          query: { match_all: {} },
        },
      })) as any,
    );

    const existing = response.hits.hits[0]?._source?.payload?.user_id;
    if (existing) return String(existing);

    const userId =
      Math.random().toString(36).substring(2, 15) +
      Math.random().toString(36).substring(2, 15);

    await this.setUserId(userId);
    return userId;
  }

  async setUserId(userId: string): Promise<void> {
    await this.initialize();
    await this.ensureMigrationIndex();
    await this.client.index({
      index: "memory_migrations",
      id: "user_id",
      body: {
        user_id: userId,
        payload: { user_id: userId },
      },
      refresh: this.autoRefresh,
    });
  }

  private hitToResult(hit: OpenSearchHit): VectorStoreResult {
    return {
      id: hit._source?.id || hit._id || "",
      payload: hit._source?.payload || {},
      score: hit._score,
    };
  }

  private buildFilterClauses(filters?: SearchFilters): any[] {
    if (!filters || Object.keys(filters).length === 0) return [];

    const normalized: Record<string, any> = {};
    for (const [key, value] of Object.entries(filters)) {
      normalized[KEY_MAP[key] || key] = value;
    }

    return Object.entries(normalized)
      .map(([key, value]) => this.buildFilterClause(key, value))
      .filter((clause): clause is Record<string, any> => Boolean(clause));
  }

  private buildFilterClause(
    key: string,
    value: any,
  ): Record<string, any> | null {
    if (value === null || value === undefined) return null;

    if (key === "AND" || key === "OR" || key === "NOT") {
      if (!Array.isArray(value)) {
        throw new Error(`${key} filter value must be an array.`);
      }

      const clauses = value
        .flatMap((filter) => this.buildFilterClauses(filter))
        .filter(Boolean);

      if (clauses.length === 0) return null;

      if (key === "AND") {
        return { bool: { filter: clauses } };
      }
      if (key === "OR") {
        return { bool: { should: clauses, minimum_should_match: 1 } };
      }
      return { bool: { must_not: clauses } };
    }

    if (value === "*") {
      return { exists: { field: this.payloadField(key, false) } };
    }

    if (Array.isArray(value)) {
      value.forEach((item) => this.assertScalarValue(key, item));
      return { terms: { [this.payloadField(key, true)]: value } };
    }

    if (typeof value === "object") {
      return this.buildOperatorClause(key, value);
    }

    return {
      term: { [this.payloadField(key, typeof value === "string")]: value },
    };
  }

  private buildOperatorClause(
    key: string,
    value: Record<string, any>,
  ): Record<string, any> {
    const clauses = Object.entries(value).map(([operator, operatorValue]) => {
      switch (operator) {
        case "eq":
          this.assertScalarValue(key, operatorValue);
          return {
            term: {
              [this.payloadField(key, typeof operatorValue === "string")]:
                operatorValue,
            },
          };
        case "ne":
          this.assertScalarValue(key, operatorValue);
          return {
            bool: {
              must_not: [
                {
                  term: {
                    [this.payloadField(key, typeof operatorValue === "string")]:
                      operatorValue,
                  },
                },
              ],
            },
          };
        case "in":
          this.assertScalarArray(key, operatorValue);
          return { terms: { [this.payloadField(key, true)]: operatorValue } };
        case "nin":
          this.assertScalarArray(key, operatorValue);
          return {
            bool: {
              must_not: [
                { terms: { [this.payloadField(key, true)]: operatorValue } },
              ],
            },
          };
        case "gt":
        case "gte":
        case "lt":
        case "lte":
          this.assertScalarValue(key, operatorValue);
          return {
            range: {
              [this.payloadField(key, false)]: {
                [operator]: operatorValue,
              },
            },
          };
        case "contains":
        case "icontains":
          this.assertScalarValue(key, operatorValue);
          return {
            wildcard: {
              [this.payloadField(key, true)]: {
                value: `*${escapeWildcard(String(operatorValue))}*`,
                case_insensitive: operator === "icontains",
              },
            },
          };
        default:
          throw new Error(`Unsupported filter operator: ${operator}`);
      }
    });

    return clauses.length === 1 ? clauses[0] : { bool: { filter: clauses } };
  }

  private payloadField(key: string, keyword: boolean): string {
    if (key.startsWith("payload.")) {
      return keyword && !key.endsWith(".keyword") ? `${key}.keyword` : key;
    }

    const field = `payload.${key}`;
    return keyword ? `${field}.keyword` : field;
  }

  // Filter values become OpenSearch term/terms/range/wildcard leaves. Allowing
  // an object here lets a caller inject raw query parameters (e.g. a `term`
  // object form with `boost`/`case_insensitive`), so reject non-scalar leaves.
  // Mirrors the Python SDK's `_validate_filter` scalar allow-list (PR #5986).
  private assertScalarValue(key: string, value: any): void {
    if (value !== null && typeof value === "object") {
      throw new Error(
        `Filter value for '${key}' must be a string, number, or boolean, got ` +
          `${Array.isArray(value) ? "an array" : "an object"}.`,
      );
    }
  }

  private assertScalarArray(key: string, value: any): void {
    if (!Array.isArray(value)) {
      throw new Error(`Filter value for '${key}' must be an array.`);
    }
    value.forEach((item) => this.assertScalarValue(key, item));
  }
}
