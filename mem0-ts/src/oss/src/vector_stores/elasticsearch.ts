import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

/**
 * Try to import Elasticsearch client.
 * This is a peer dependency - users must install @elastic/elasticsearch.
 */
let Client: any;

try {
  const elasticsearch = require("@elastic/elasticsearch");
  Client = elasticsearch.Client;
} catch {
  // Will throw at runtime if Elasticsearch is used without the SDK installed
}

/**
 * Configuration options for Elasticsearch vector store.
 */
export interface ElasticsearchConfig extends VectorStoreConfig {
  /** Elasticsearch host URL (e.g., "http://localhost:9200") */
  host?: string;
  /** Elasticsearch port. If provided with host, will be appended to host */
  port?: number;
  /** Cloud ID for Elastic Cloud deployment */
  cloudId?: string;
  /** API key for authentication */
  apiKey?: string;
  /** Username for basic authentication */
  user?: string;
  /** Password for basic authentication */
  password?: string;
  /** Name of the index. Defaults to "mem0" */
  collectionName?: string;
  /** Dimension of the embedding vectors */
  embeddingModelDims: number;
  /** Verify SSL certificates. Defaults to true */
  verifyCerts?: boolean;
  /** Custom headers to include in requests */
  headers?: Record<string, string>;
  /** Automatically create index during initialization. Defaults to true */
  autoCreateIndex?: boolean;
}

/**
 * Elasticsearch vector store implementation using dense_vector and kNN search.
 *
 * Requires @elastic/elasticsearch as a peer dependency.
 *
 * @example
 * ```typescript
 * // Using Elastic Cloud
 * const store = new Elasticsearch({
 *   cloudId: "my-deployment:...",
 *   apiKey: "your-api-key",
 *   collectionName: "memories",
 *   embeddingModelDims: 1536,
 * });
 *
 * // Using self-hosted
 * const store = new Elasticsearch({
 *   host: "http://localhost",
 *   port: 9200,
 *   user: "elastic",
 *   password: "password",
 *   collectionName: "memories",
 *   embeddingModelDims: 1536,
 * });
 *
 * await store.initialize();
 * ```
 */
export class Elasticsearch implements VectorStore {
  private client: any;
  private collectionName: string;
  private embeddingModelDims: number;
  private autoCreateIndex: boolean;
  private userId: string = "";

  constructor(config: ElasticsearchConfig) {
    if (!Client) {
      throw new Error(
        "The '@elastic/elasticsearch' package is required. " +
          "Please install it using 'npm install @elastic/elasticsearch'.",
      );
    }

    if (!config.embeddingModelDims) {
      throw new Error("embeddingModelDims is required for Elasticsearch");
    }

    // Validate authentication
    const hasCloudId = !!config.cloudId;
    const hasHost = !!config.host;
    const hasApiKey = !!config.apiKey;
    const hasBasicAuth = !!(config.user && config.password);

    if (!hasCloudId && !hasHost) {
      throw new Error(
        "Either cloudId or host must be provided for Elasticsearch",
      );
    }

    if (!hasApiKey && !hasBasicAuth) {
      throw new Error(
        "Either apiKey or user/password must be provided for Elasticsearch",
      );
    }

    this.collectionName = config.collectionName || "mem0";
    this.embeddingModelDims = config.embeddingModelDims;
    this.autoCreateIndex = config.autoCreateIndex !== false;

    // Build client configuration
    const clientConfig: Record<string, any> = {};

    if (config.cloudId) {
      clientConfig.cloud = { id: config.cloudId };
    } else {
      // Build host URL
      let hostUrl = config.host!;
      if (config.port && !hostUrl.includes(`:${config.port}`)) {
        // Remove trailing slash if present before adding port
        hostUrl = hostUrl.replace(/\/$/, "");
        hostUrl = `${hostUrl}:${config.port}`;
      }
      clientConfig.node = hostUrl;
    }

    // Authentication
    if (config.apiKey) {
      clientConfig.auth = { apiKey: config.apiKey };
    } else if (config.user && config.password) {
      clientConfig.auth = {
        username: config.user,
        password: config.password,
      };
    }

    // TLS configuration
    if (config.verifyCerts === false) {
      clientConfig.tls = { rejectUnauthorized: false };
    }

    // Custom headers
    if (config.headers) {
      clientConfig.headers = config.headers;
    }

    this.client = new Client(clientConfig);
  }

  /**
   * Initialize the vector store by creating the index if needed.
   */
  async initialize(): Promise<void> {
    if (this.autoCreateIndex) {
      await this.createIndex();
    }
  }

  /**
   * Create the index with dense_vector mapping if it doesn't exist.
   */
  private async createIndex(): Promise<void> {
    const indexExists = await this.client.indices.exists({
      index: this.collectionName,
    });

    if (!indexExists) {
      await this.client.indices.create({
        index: this.collectionName,
        settings: {
          index: {
            number_of_replicas: 1,
            number_of_shards: 5,
            refresh_interval: "1s",
          },
        },
        mappings: {
          properties: {
            vector: {
              type: "dense_vector",
              dims: this.embeddingModelDims,
              index: true,
              similarity: "cosine",
            },
            metadata: {
              type: "object",
              properties: {
                user_id: { type: "keyword" },
              },
            },
          },
        },
      });
      console.log(`Created index '${this.collectionName}'`);
    }
  }

  /**
   * Insert vectors into the index using bulk operations.
   */
  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[],
  ): Promise<void> {
    const operations: any[] = [];

    for (let i = 0; i < vectors.length; i++) {
      // Bulk operation: index action
      operations.push({
        index: {
          _index: this.collectionName,
          _id: ids[i],
        },
      });
      // Document body
      operations.push({
        vector: vectors[i],
        metadata: payloads[i] || {},
      });
    }

    const response = await this.client.bulk({
      operations,
      refresh: true,
    });

    if (response.errors) {
      const errorItems = response.items.filter(
        (item: any) => item.index?.error,
      );
      const errorMessages = errorItems
        .map((item: any) => item.index?.error?.reason)
        .join(", ");
      throw new Error(`Bulk insert failed: ${errorMessages}`);
    }
  }

  /**
   * Search for similar vectors using kNN query.
   *
   * @param query - Query vector
   * @param limit - Maximum number of results to return
   * @param filters - Optional metadata filters
   * @returns Array of results sorted by similarity score (descending)
   */
  async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters,
  ): Promise<VectorStoreResult[]> {
    const searchParams: any = {
      index: this.collectionName,
      knn: {
        field: "vector",
        query_vector: query,
        k: limit,
        num_candidates: limit * 2,
      },
    };

    // Apply filters if provided
    if (filters && Object.keys(filters).length > 0) {
      const filterConditions: any[] = [];
      for (const [key, value] of Object.entries(filters)) {
        if (value !== undefined && value !== null) {
          filterConditions.push({
            term: { [`metadata.${key}`]: value },
          });
        }
      }

      if (filterConditions.length > 0) {
        searchParams.knn.filter = {
          bool: { must: filterConditions },
        };
      }
    }

    const response = await this.client.search(searchParams);
    const hits = response.hits?.hits || [];

    return hits.map((hit: any) => ({
      id: hit._id,
      payload: hit._source?.metadata || {},
      score: hit._score ?? 0,
    }));
  }

  /**
   * Get a vector by ID.
   */
  async get(vectorId: string): Promise<VectorStoreResult | null> {
    try {
      const response = await this.client.get({
        index: this.collectionName,
        id: vectorId,
      });

      return {
        id: response._id,
        payload: response._source?.metadata || {},
      };
    } catch (error: any) {
      // Handle not found error
      if (error?.meta?.statusCode === 404) {
        return null;
      }
      throw error;
    }
  }

  /**
   * Update a vector and its payload.
   */
  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>,
  ): Promise<void> {
    await this.client.update({
      index: this.collectionName,
      id: vectorId,
      doc: {
        vector,
        metadata: payload,
      },
      refresh: true,
    });
  }

  /**
   * Delete a vector by ID.
   */
  async delete(vectorId: string): Promise<void> {
    await this.client.delete({
      index: this.collectionName,
      id: vectorId,
      refresh: true,
    });
  }

  /**
   * Delete the entire index.
   */
  async deleteCol(): Promise<void> {
    await this.client.indices.delete({
      index: this.collectionName,
    });
  }

  /**
   * List vectors in the index with optional filtering.
   *
   * @param filters - Optional metadata filters
   * @param limit - Maximum number of results to return
   * @returns Tuple of [results, count]
   */
  async list(
    filters?: SearchFilters,
    limit: number = 100,
  ): Promise<[VectorStoreResult[], number]> {
    const searchParams: any = {
      index: this.collectionName,
      size: limit,
    };

    if (filters && Object.keys(filters).length > 0) {
      const filterConditions: any[] = [];
      for (const [key, value] of Object.entries(filters)) {
        if (value !== undefined && value !== null) {
          filterConditions.push({
            term: { [`metadata.${key}`]: value },
          });
        }
      }

      searchParams.query = {
        bool: { must: filterConditions },
      };
    } else {
      searchParams.query = { match_all: {} };
    }

    const response = await this.client.search(searchParams);
    const hits = response.hits?.hits || [];

    const results = hits.map((hit: any) => ({
      id: hit._id,
      payload: hit._source?.metadata || {},
    }));

    return [results, results.length];
  }

  /**
   * Get the current user ID.
   */
  async getUserId(): Promise<string> {
    return this.userId;
  }

  /**
   * Set the user ID.
   */
  async setUserId(userId: string): Promise<void> {
    this.userId = userId;
  }

  /**
   * Close the client connection.
   */
  async close(): Promise<void> {
    if (this.client?.close) {
      await this.client.close();
    }
  }
}
