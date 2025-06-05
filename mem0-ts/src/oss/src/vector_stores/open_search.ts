import { Client as OpenSearchClient } from "@opensearch-project/opensearch";
import { SearchFilters, VectorStoreResult } from "../types";
import { VectorStore } from "./base";

interface OpenSearchConfig {
  host: string;
  port?: number;
  user?: string;
  password?: string;
  useSSL?: boolean;
  verifyCerts?: boolean;
  collectionName: string;
  embeddingModelDims: number;
}

export class OpenSearchVectorStore implements VectorStore {
  private client: OpenSearchClient;
  private collectionName: string;
  private embeddingModelDims: number;
  private userId: string | null = null;

  constructor(config: OpenSearchConfig) {
    const protocol = config.useSSL ? "https" : "http";
    const port = config.port || 9200;
    const node = `${protocol}://${config.host}:${port}`;

    const auth =
      config.user && config.password
        ? { username: config.user, password: config.password }
        : undefined;

    this.client = new OpenSearchClient({
      node,
      auth,
      ssl: {
        rejectUnauthorized: config.verifyCerts ?? true,
      },
      maxRetries: 3,
      requestTimeout: 30000,
      // Optional: set connection pool size or other client options here
    });

    this.collectionName = config.collectionName;
    this.embeddingModelDims = config.embeddingModelDims;

    this.init().catch(console.error);
  }

  /** Initialize the OpenSearch index (create if not exist) */
  public async initialize(): Promise<void> {
    return this.init()
  }

  public async init(): Promise<void> {
    console.log('*initialize*',)
    await this.createCol(this.collectionName, this.embeddingModelDims);
  }

  /** Create index with k-NN mapping if it doesn't exist */
  private async createCol(name: string, vectorSize: number): Promise<void> {
    const indexExists = await this.client.indices.exists({ index: name }).catch(() => { return {body: false}})
    if (indexExists.body === false) {
      const indexSettings = {
        settings: { "index.knn": true },
        mappings: {
          properties: {
            vector_field: {
              type: "knn_vector",
              dimension: vectorSize,
              method: { engine: "nmslib", name: "hnsw", space_type: "cosinesimil" },
            },
            payload: { type: "object" },
            id: { type: "keyword" },
          },
        },
      };

      await this.client.indices.create({ index: name, body: indexSettings });
      console.info(`Created index ${name}`);

      // Wait for index to be searchable
      const maxRetries = 60;
      let retryCount = 0;
      while (retryCount < maxRetries) {
        try {
          await this.client.search({
            index: name,
            body: { query: { match_all: {} }, size: 1 },
          });
          console.info(`Index ${name} is ready`);
          return;
        } catch {
          retryCount += 1;
          if (retryCount === maxRetries) {
            throw new Error(`Index ${name} creation timed out after ${maxRetries} seconds`);
          }
          await this.sleep(500);
        }
      }
    } else {
      console.info(`Index ${name} already exists`);
    }
  }

  /** Helper to pause execution */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  public async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[]
  ): Promise<void> {
    if (ids.length !== vectors.length) {
      throw new Error("IDs length must match vectors length");
    }
    if (payloads.length !== vectors.length) {
      throw new Error("Payloads length must match vectors length");
    }

    const bodyBulk: any[] = [];
    for (let i = 0; i < vectors.length; i++) {
      bodyBulk.push({ index: { _index: this.collectionName } });
      bodyBulk.push({
        vector_field: vectors[i],
        payload: payloads[i],
        id: ids[i],
      });
    }

    await this.client.bulk({ body: bodyBulk, refresh: true });
  }

  public async search(
    query: number[],
    limit: number = 5,
    filters?: SearchFilters
  ): Promise<VectorStoreResult[]> {
    const knnQuery = {
      knn: {
        vector_field: {
          vector: query,
          k: limit * 2,
        },
      },
    };

    const filterClauses: any[] = [];
    if (filters) {
      for (const key of ["userId", "runId", "agentId"] as Array<keyof SearchFilters>) {
        const value = filters[key];
        if (value) {
          filterClauses.push({ term: { [`payload.${key}.keyword`]: value } });
        }
      }
    }

    const queryBody: any = {
      size: limit * 2,
      query: filterClauses.length
        ? { bool: { must: knnQuery, filter: filterClauses } }
        : knnQuery,
    };

    const response = await this.client.search({
      index: this.collectionName,
      body: queryBody,
    });

    const hits = response.body.hits.hits;
    return hits.map((hit: any) => ({
      id: hit._source.id,
      score: hit._score,
      payload: hit._source.payload ?? {},
    }));
  }

  public async get(vectorId: string): Promise<VectorStoreResult | null> {
    // Ensure index exists
    const indexExists = await this.client.indices.exists({ index: this.collectionName });
    if (indexExists.body === false) {
      await this.createCol(this.collectionName, this.embeddingModelDims);
      return null;
    }

    const searchQuery = { query: { term: { id: vectorId } }, size: 1 };
    const response = await this.client.search({
      index: this.collectionName,
      body: searchQuery,
    });

    const hits = response.body.hits.hits;
    if (hits.length === 0) {
      return null;
    }

    const hit = hits[0];
    return {
      id: hit._source.id,
      score: 1.0,
      payload: hit._source.payload ?? {},
    };
  }

  public async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>
  ): Promise<void> {
    const searchQuery = { query: { term: { id: vectorId } }, size: 1 };
    const response = await this.client.search({
      index: this.collectionName,
      body: searchQuery,
    });

    const hits = response.body.hits.hits;
    if (hits.length === 0) {
      return;
    }

    const opensearchId = hits[0]._id;
    const doc: any = {};
    if (vector) {
      doc.vector_field = vector;
    }
    if (payload) {
      doc.payload = payload;
    }

    if (Object.keys(doc).length > 0) {
      try {
        await this.client.update({
          index: this.collectionName,
          id: opensearchId,
          body: { doc },
        });
      } catch (err) {
        console.error(`Error updating document ${vectorId}:`, err);
      }
    }
  }

  public async delete(vectorId: string): Promise<void> {
    const searchQuery = { query: { term: { id: vectorId } }, size: 1 };
    const response = await this.client.search({
      index: this.collectionName,
      body: searchQuery,
    });

    const hits = response.body.hits.hits;
    if (hits.length === 0) {
      return;
    }

    const opensearchId = hits[0]._id;
    await this.client.delete({ index: this.collectionName, id: opensearchId });
  }

  public async deleteCol(): Promise<void> {
    const indexExists = await this.client.indices.exists({ index: this.collectionName });
    if (indexExists.body) {
      await this.client.indices.delete({ index: this.collectionName });
    }
  }

  public async list(
    filters?: SearchFilters,
    limit?: number
  ): Promise<[VectorStoreResult[], number]> {
    const filterClauses: any[] = [];
    if (filters) {
      for (const key of ["userId", "runId", "agentId"] as Array<keyof SearchFilters>) {
        const value = filters[key];
        if (value) {
          filterClauses.push({ term: { [`payload.${key}.keyword`]: value } });
        }
      }
    }

    const queryBody: any = filterClauses.length
      ? { query: { bool: { filter: filterClauses } } }
      : { query: { match_all: {} } };

    if (limit) {
      queryBody.size = limit;
    }

    const response = await this.client.search({
      index: this.collectionName,
      body: queryBody,
    });

    const hits = response.body.hits.hits;
    const total = response.body.hits.total?.value ?? hits.length;

    const results: VectorStoreResult[] = hits.map((hit: any) => ({
      id: hit._source.id,
      score: 1.0,
      payload: hit._source.payload ?? {},
    }));

    return [results, total];
  }

  public async getUserId(): Promise<string> {
    return this.userId!;
  }

  public async setUserId(userId: string): Promise<void> {
    this.userId = userId;
  }
}
