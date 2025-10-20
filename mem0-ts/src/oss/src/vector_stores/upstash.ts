import { Index } from "@upstash/vector";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface UpstashConfig extends VectorStoreConfig {
  url?: string;
  token: string;
  email?: string;
  indexName: string;
  embeddingModel?: // these are the models supported by Upstash as of now
  | "BGE_SMALL_EN_V1_5"
    | "BGE_BASE_EN_V1_5"
    | "BGE_LARGE_EN_V1_5"
    | "BGE_M3"
    | "BERT_BASE_UNCASED"
    | "UAE_LARGE_V1"
    | "ALL_MINILM_L6_V2"
    | "MXBAI_EMBED_LARGE_V1"
    | "BM25";
}

export class UpstashVectorStore implements VectorStore {
  private client: Index | null = null;
  private indexName: string;
  private dimensions: number;
  private token: string;
  private embeddingModel?: string;
  private email?: string;

  constructor(config: UpstashConfig) {
    if (config.url) {
      this.client = new Index({
        url: config.url,
        token: config.token,
      });
    }
    this.dimensions = config.dimension || 1536;
    this.token = config.token;
    this.indexName = config.indexName;
    this.embeddingModel = config.embeddingModel || "BGE_LARGE_EN_V1_5";
    this.email = config.email;
    this.initialize().catch(console.error);
  }
  async insert(
    vectors: number[][],
    ids: string[],
    payloads: Record<string, any>[]
  ): Promise<void> {
    try {
      const vectorObjects = vectors.map((vector, index) => ({
        id: ids[index],
        vector: vector,
        metadata: payloads[index] || {},
      }));
      await this.client!.upsert(vectorObjects);
    } catch (err) {
      console.error("Error inserting vectors into Upstash:", err);
    }
  }

  async search(
    query: number[],
    limit?: number,
    filters?: SearchFilters
  ): Promise<VectorStoreResult[]> {
    try {
      // Convert SearchFilters to Upstash filter string format
      let filterString: string | undefined;
      if (filters) {
        const filterConditions: string[] = [];
        for (const [key, value] of Object.entries(filters)) {
          if (value !== undefined) {
            filterConditions.push(`${key} = '${value}'`);
          }
        }
        filterString =
          filterConditions.length > 0
            ? filterConditions.join(" and ")
            : undefined;
      }

      const result = await this.client!.query({
        topK: limit || 5,
        vector: query,
        filter: filterString,
        includeMetadata: true,
      });

      return (
        (result.map((item) => ({
          id: item.id,
          score: item.score,
          payload: item.metadata || {},
        })) as VectorStoreResult[]) || []
      );
    } catch (err) {
      console.error("Error searching vectors in Upstash:", err);
      return [];
    }
  }

  async initialize(): Promise<void> {
    try {
      if (this.client) return; // Already initialized
      // Check if the index already exists
      let indexFound = false;
      const url = "https://api.upstash.com/v2/vector/index";
      const encodedCredentials = Buffer.from(
        `${this.email}:${this.token}`
      ).toString("base64");

      const options = {
        method: "GET",
        headers: { Authorization: `Basic ${encodedCredentials}` },
        body: undefined,
      };

      const response = await fetch(url, options);
      const data = await response.json();

      for (const idx of data as any[]) {
        if (idx.name === this.indexName) {
          indexFound = true;
          break;
        }
      }
      // If the index does not exist, create it
      if (!indexFound) {
        try {
          const options = {
            method: "POST",
            headers: {
              Authorization: `Basic ${encodedCredentials}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              name: this.indexName,
              region: "us-east-1",
              similarity_function: "COSINE",
              dimension_count: this.dimensions,
              type: "free",
              embedding_model: this.embeddingModel,
            }),
          };

          await fetch(url, options);
        } catch (err: any) {
          throw new Error(`Error creating index: ${err.message || err}`);
        }
      }
    } catch (error) {
      console.error("Error initializing Upstash Vector Store:", error);
    }
  }
}
