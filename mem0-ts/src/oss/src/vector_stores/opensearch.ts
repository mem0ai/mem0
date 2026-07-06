import { Client as OpenSearchClient } from "@opensearch-project/opensearch";
import { AwsSigv4Signer } from "@opensearch-project/opensearch/aws";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface OpenSearchConfig extends VectorStoreConfig {
  /** OpenSearch host (default: "localhost"). */
  host?: string;
  /** OpenSearch port (default: 9200). */
  port?: number;
  /** Full connection URL (overrides host/port). */
  url?: string;
  /** HTTP auth credentials `[username, password]`. */
  httpAuth?: [string, string];
  /** AWS region — when set, requests are signed with Sigv4. */
  awsRegion?: string;
  /** AWS service name for Sigv4 signing (default: "es"). */
  awsService?: string;
  /** Whether to use SSL (default: true). */
  useSSL?: boolean;
  /** Whether to verify SSL certificates (default: true). */
  verifyCerts?: boolean;
  /** Index / collection name. */
  collectionName: string;
  /** Dimension of embedding vectors. */
  embeddingModelDims: number;
  /** Refresh after insert (default: false — see Python impl for why). */
  autoRefresh?: boolean;
}

interface OpenSearchHit {
  _id: string;
  _score: number;
  _source: {
    id: string;
    vector_field: number[];
    payload: Record<string, any>;
  };
}

const SAFE_FILTER_KEY = /^[a-zA-Z_][a-zA-Z0-9_.]*$/;

function validateFilter(key: string, value: unknown): void {
  if (typeof key !== "string" || !SAFE_FILTER_KEY.test(key)) {
    throw new Error(`Invalid filter key: ${JSON.stringify(key)}`);
  }
  if (
    typeof value !== "string" &&
    typeof value !== "number" &&
    typeof value !== "boolean"
  ) {
    throw new Error(
      `Filter value for ${JSON.stringify(key)} must be string, number, or boolean, ` +
        `got ${typeof value}`,
    );
  }
}

export class OpenSearch implements VectorStore {
  private client: OpenSearchClient;
  private readonly collectionName: string;
  private readonly embeddingModelDims: number;
  private readonly autoRefresh: boolean;

  constructor(config: OpenSearchConfig) {
    this.collectionName = config.collectionName;
    this.embeddingModelDims = config.embeddingModelDims;
    this.autoRefresh = config.autoRefresh ?? false;

    const host = config.host ?? "localhost";
    const port = config.port ?? 9200;
    const useSSL = config.useSSL ?? true;
    const verifyCerts = config.verifyCerts ?? true;

    // Build connection node
    const node: Record<string, any> = {
      url: config.url ?? `${useSSL ? "https" : "http"}://${host}:${port}`,
    };

    // AWS Sigv4 signing
    if (config.awsRegion) {
      const region = config.awsRegion;
      const service = config.awsService ?? "es";
      const signer = AwsSigv4Signer({
        region,
        service,
        // Access credentials are picked up from the environment
        // (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN)
        // or from the default credential provider chain.
      });
      Object.assign(node, signer);
    }

    const clientOptions: Record<string, any> = {
      node,
      ssl: {
        rejectUnauthorized: verifyCerts,
      },
    };

    if (config.httpAuth) {
      clientOptions.auth = {
        username: config.httpAuth[0],
        password: config.httpAuth[1],
      };
    }

    this.client = new OpenSearchClient(clientOptions);
  }

  /** Ensure the index exists with the correct k-NN mapping. */
  async initialize(): Promise<void> {
    const { body: exists } = await this.client.indices.exists({
      index: this.collectionName,
    });

    if (!exists) {
      await this.client.indices.create({
        index: this.collectionName,
        body: {
          settings: {
            index: { knn: true },
          },
          mappings: {
            properties: {
              vector_field: {
                type: "knn_vector",
                dimension: this.embeddingModelDims,
                method: {
                  engine: "nmslib",
                  name: "hnsw",
                  space_type: "cosinesimil",
                },
              },
              id: { type: "keyword" },
              payload: { type: "object" },
            },
          },
        },
      });
    }
  }

  // ── VectorStore interface ─────────────────────────────────────────────

  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    for (let i = 0; i < vectors.length; i++) {
      const vec = vectors[i];
      if (!vec || vec.length === 0) {
        throw new Error(
          `Vector at index ${i} is empty. Expected dimension ${this.embeddingModelDims}.`,
        );
      }
      if (vec.length !== this.embeddingModelDims) {
        throw new Error(
          `Vector at index ${i} has dimension ${vec.length}, ` +
            `but expected ${this.embeddingModelDims}.`,
        );
      }

      await this.client.index({
        index: this.collectionName,
        body: {
          vector_field: vec,
          id: ids[i],
          payload: payloads[i] ?? {},
        },
      });
    }

    if (this.autoRefresh) {
      await this.client.indices.refresh({ index: this.collectionName });
    }
  }

  async search(
    query: number[],
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const knnQuery: Record<string, any> = {
      knn: {
        vector_field: {
          vector: query,
          k: topK * 2,
        },
      },
    };

    const filterClauses = this.buildFilterClauses(filters);
    const body: Record<string, any> = { size: topK * 2 };

    if (filterClauses.length > 0) {
      body.query = { bool: { must: knnQuery, filter: filterClauses } };
    } else {
      body.query = knnQuery;
    }

    try {
      const { body: response } = await this.client.search({
        index: this.collectionName,
        body,
      });

      const hits: OpenSearchHit[] = response.hits?.hits ?? [];
      return hits.slice(0, topK).map((hit) => ({
        id: hit._source.id,
        score: hit._score,
        payload: hit._source.payload ?? {},
      }));
    } catch {
      return [];
    }
  }

  async keywordSearch?(
    query: string,
    topK: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[] | null> {
    const boolQuery: Record<string, any> = {
      should: [
        { match: { "payload.data": query } },
        { match: { "payload.text_lemmatized": query } },
      ],
      minimum_should_match: 1,
    };

    const filterClauses = this.buildFilterClauses(filters);
    if (filterClauses.length > 0) {
      boolQuery.filter = filterClauses;
    }

    try {
      const { body: response } = await this.client.search({
        index: this.collectionName,
        body: { size: topK, query: { bool: boolQuery } },
      });

      const hits: OpenSearchHit[] = response.hits?.hits ?? [];
      return hits.slice(0, topK).map((hit) => ({
        id: hit._source.id,
        score: hit._score,
        payload: hit._source.payload ?? {},
      }));
    } catch {
      return null;
    }
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    try {
      const { body: response } = await this.client.search({
        index: this.collectionName,
        body: { query: { term: { id: vectorId } } },
      });

      const hits: OpenSearchHit[] = response.hits?.hits ?? [];
      if (hits.length === 0) return null;

      return {
        id: hits[0]._source.id,
        score: 1.0,
        payload: hits[0]._source.payload ?? {},
      };
    } catch {
      return null;
    }
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    if (vector.length !== this.embeddingModelDims) {
      throw new Error(
        `Update vector has dimension ${vector.length}, ` +
          `but expected ${this.embeddingModelDims}.`,
      );
    }

    // Find document by custom ID
    const { body: response } = await this.client.search({
      index: this.collectionName,
      body: { query: { term: { id: vectorId } } },
    });

    const hits: OpenSearchHit[] = response.hits?.hits ?? [];
    if (hits.length === 0) return;

    await this.client.update({
      index: this.collectionName,
      id: hits[0]._id,
      body: {
        doc: {
          vector_field: vector,
          payload,
        },
      },
    });
  }

  async delete(vectorId: string): Promise<void> {
    const { body: response } = await this.client.search({
      index: this.collectionName,
      body: { query: { term: { id: vectorId } } },
    });

    const hits: OpenSearchHit[] = response.hits?.hits ?? [];
    if (hits.length === 0) return;

    await this.client.delete({
      index: this.collectionName,
      id: hits[0]._id,
    });
  }

  async deleteCol(): Promise<void> {
    await this.client.indices.delete({ index: this.collectionName });
  }

  async list(
    filters?: SearchFilters,
    topK?: number,
  ): Promise<[VectorStoreResult[], number]> {
    const body: Record<string, any> = { query: { match_all: {} } };

    const filterClauses = this.buildFilterClauses(filters);
    if (filterClauses.length > 0) {
      body.query = { bool: { filter: filterClauses } };
    }

    if (topK) {
      body.size = topK;
    }

    try {
      const { body: response } = await this.client.search({
        index: this.collectionName,
        body,
      });

      const hits: OpenSearchHit[] = response.hits?.hits ?? [];
      const results: VectorStoreResult[] = hits.map((hit) => ({
        id: hit._source.id,
        score: 1.0,
        payload: hit._source.payload ?? {},
      }));

      return [results, results.length];
    } catch {
      return [[], 0];
    }
  }

  async getUserId(): Promise<string> {
    throw new Error("getUserId is not supported by OpenSearch vector store");
  }

  async setUserId(_userId: string): Promise<void> {
    throw new Error("setUserId is not supported by OpenSearch vector store");
  }

  // ── Helpers ───────────────────────────────────────────────────────────

  private buildFilterClauses(filters?: SearchFilters): any[] {
    if (!filters) return [];

    const clauses: any[] = [];
    for (const [key, value] of Object.entries(filters)) {
      if (value !== undefined && value !== null) {
        validateFilter(key, value);
        clauses.push({ term: { [`payload.${key}.keyword`]: value } });
      }
    }
    return clauses;
  }
}
