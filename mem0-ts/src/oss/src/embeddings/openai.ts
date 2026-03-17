import OpenAI from "openai";
import { Embedder } from "./base";
import { EmbeddingConfig } from "../types";

function validateOpenAIEmbedderConfig(config: EmbeddingConfig): void {
  if (!config.apiKey) {
    const hasWrongApiKey = "openaiApiKey" in config;
    const errorMsg = "OpenAI Embedder config validation failed: 'apiKey' is required." +
      (hasWrongApiKey ? " Did you mean 'apiKey' (not 'openaiApiKey')?" : "");
    throw new Error(errorMsg);
  }

  if ("openaiApiKey" in config) {
    console.warn("Warning: 'openaiApiKey' is not a valid config key. Use 'apiKey' instead.");
  }
  if ("baseUrl" in config) {
    console.warn("Warning: 'baseUrl' is not a valid config key. Use 'baseURL' instead.");
  }
}

export class OpenAIEmbedder implements Embedder {
  private openai: OpenAI;
  private model: string;
  private embeddingDims?: number;

  constructor(config: EmbeddingConfig) {
    validateOpenAIEmbedderConfig(config);
    this.openai = new OpenAI({
      apiKey: config.apiKey,
      baseURL: config.baseURL || config.url,
    });
    this.model = config.model || "text-embedding-3-small";
    this.embeddingDims = config.embeddingDims || 1536;
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
