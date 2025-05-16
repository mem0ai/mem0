import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

// Default OpenAI API base URL
const DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1";

export class OpenAIEmbedder implements Embedder {
  private openai: OpenAI;
  private model: string;

  constructor(config: EmbeddingConfig) {
    // Get baseUrl from config, environment variables, or use default
    const baseUrl =
      config.openai_base_url ||
      process.env.OPENAI_BASE_URL ||
      process.env.OPENAI_API_BASE ||
      DEFAULT_OPENAI_BASE_URL;

    // Initialize OpenAI client with apiKey and baseUrl
    this.openai = new OpenAI({
      apiKey: config.apiKey,
      baseURL: baseUrl
    });

    this.model = config.model || "text-embedding-3-small";
  }

  async embed(text: string): Promise<number[]> {
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: text,
    });
    return response.data[0].embedding;
  }

  async embedBatch(texts: string[]): Promise<number[][]> {
    const response = await this.openai.embeddings.create({
      model: this.model,
      input: texts,
    });
    return response.data.map((item) => item.embedding);
  }
}
