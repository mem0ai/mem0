import { Index } from "@upstash/vector";
import { VectorStore } from "./base";
import { SearchFilters, VectorStoreConfig, VectorStoreResult } from "../types";

interface UpstashConfig extends VectorStoreConfig {
  url: string;
  token: string;
  indexName: string;
}

export class UpstashVectorStore implements VectorStore {
  private client: Index;
  private indexName: string;
  private dimensions: number;
  private token: string;

  constructor(config: UpstashConfig) {
    this.client = new Index({
      url: config.url,
      token: config.token,
    });
    this.dimensions = config.dimension || 1536;
    this.token = config.token;
    this.indexName = config.indexName;
  }

  async initialize(): Promise<void> {
    try {
      // Check if the index already exists
      let indexFound = false;
      const url = "https://api.upstash.com/v2/vector/index";
      const options = {
        method: "GET",
        headers: { Authorization: `Basic ${this.token}` },
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
      }
    } catch (error) {
      console.error("Error initializing Upstash Vector Store:", error);
    }
  }
}
