import { Index } from "@upstash/vector";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface UpstashConfig extends VectorStoreConfig {
  restUrl?: string;
  restToken: string;
  apiKey?: string;
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
  private apiKey?: string;
  private embeddingModel?: string;
  private email?: string;

  constructor(config: UpstashConfig) {
    if (config.restUrl && config.restToken) {
      this.client = new Index({
        url: config.restUrl,
        token: config.restToken,
      });
    }
    this.dimensions = config.dimension || 1536;
    this.apiKey = config.apiKey;
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

  async delete(vectorId: string): Promise<void> {
    try {
      await this.client!.delete(vectorId);
    } catch (err) {
      console.error("Error deleting vector from Upstash:", err);
    }
  }

  async deleteCol(): Promise<void> {
    try {
      const id = async () => {
        const url = "https://api.upstash.com/v2/vector/index";
        const encodedCredentials = Buffer.from(
          `${this.email}:${this.apiKey}`
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
            return idx.id;
          }
        }
      };

      const url = `https://api.upstash.com/v2/vector/index/${await id()}`;
      const encodedCredentials = Buffer.from(
        `${this.email}:${this.apiKey}`
      ).toString("base64");

      const options = {
        method: "DELETE",
        headers: { Authorization: `Basic ${encodedCredentials}` },
        body: undefined,
      };

      const response = await fetch(url, options);
    } catch (err) {
      throw new Error("Failed to delete vector: " + (err as Error).message);
    }
  }

  async update(
    vectorId: string,
    vector: number[],
    payload: Record<string, any>
  ): Promise<void> {
    try {
      const data = {
        id: vectorId,
        vector: vector,
        metadata: payload || {},
      };

      await this.client!.update(data);
    } catch (err) {
      throw new Error("Failed to update vector: " + (err as Error).message);
    }
  }

  async get(vectorId: string): Promise<VectorStoreResult | null> {
    try {
      const result = await this.client!.fetch([vectorId], {
        includeMetadata: true,
      });
      if (result.length === 0) {
        return null;
      }
      return {
        id: vectorId,
        payload: result[0]!.metadata || {},
      };
    } catch (err) {
      throw new Error("Failed to get vector: " + (err as Error).message);
    }
  }

  async list(
    filters?: SearchFilters,
    limit?: number
  ): Promise<[VectorStoreResult[], number]> {
    return [[], 0];
  }

  async setUserId(userId: string): Promise<void> {}

  async getUserId(): Promise<string> {
    return "";
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
        `${this.email}:${this.apiKey}`
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
